"""Local model-connection persistence and validation for local Kontext mode."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from kontext.common.utils.enum_utils import enum_value
from kontext.common.utils.json_compat import model_validate_stored
from kontext.data.database import Base, get_sync_db_session
from kontext.llm import (
    LanguageModelService,
    get_connection_adapter_type,
    infer_model_connection_validation_state,
    model_supports_connection_kind,
)
from kontext.schema import (
    ModelAdapterType,
    ModelConnection,
    ModelConnectionCredentialRefs,
    ModelConnectionKind,
    ModelConnectionProviderConfig,
    ModelConnectionSourceType,
    ModelReasoningEffort,
    ModelValidationState,
)


class _LocalModelConnectionDB(Base):
    """User-configured executable model connections for local mode."""

    __tablename__ = "local_model_connections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="user_managed")
    adapter_type: Mapped[str] = mapped_column(String(64), nullable=False)
    connection_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_model_id: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    connection_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_value: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    secret_values_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_sampling_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    secret_configured: Mapped[bool] = mapped_column(default=False)
    is_default: Mapped[bool] = mapped_column(default=False)
    enabled: Mapped[bool] = mapped_column(default=True)
    validation_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    owner_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ModelConnectionValidationError(ValueError):
    """Raised when a local model connection request violates shared registry rules."""

    def __init__(self, errors: dict[str, str | list[str]]) -> None:
        normalized_errors = {
            key: value if isinstance(value, list) else [value] for key, value in errors.items()
        }
        self.errors = normalized_errors
        super().__init__("Invalid model connection configuration")


_SECRET_FIELD_SUFFIXES = {
    "apiKeyRef": "api-key",
    "accessKeyIdRef": "access-key-id",
    "secretAccessKeyRef": "secret-access-key",
    "sessionTokenRef": "session-token",
}

_CREDENTIAL_REF_ATTRS = {
    "apiKeyRef": "api_key_ref",
    "accessKeyIdRef": "access_key_id_ref",
    "secretAccessKeyRef": "secret_access_key_ref",
    "sessionTokenRef": "session_token_ref",
}

_SECRET_VALUE_KEYS = {
    "apiKeyRef": "apiKey",
    "accessKeyIdRef": "accessKeyId",
    "secretAccessKeyRef": "secretAccessKey",
    "sessionTokenRef": "sessionToken",
}


def _get_language_model_service() -> LanguageModelService:
    return LanguageModelService()


def _require_enum_value(value: Any, *, field_name: str) -> str:
    resolved = enum_value(value)
    if resolved is None:
        raise ValueError(f"{field_name} is required")
    return resolved


def _resolve_adapter_type(connection_kind: str, fallback_value: Any) -> str:
    resolved_adapter_type = get_connection_adapter_type(connection_kind)
    if resolved_adapter_type:
        return resolved_adapter_type
    return _require_enum_value(fallback_value, field_name="adapter_type")


def _validate_and_normalize_model_selection(
    *,
    connection_kind: str,
    canonical_model_id: str,
    provider_config: ModelConnectionProviderConfig | None,
) -> tuple[str, Any]:
    errors: dict[str, str | list[str]] = {}

    language_model_service = _get_language_model_service()
    normalized_canonical_model_id = (
        language_model_service.normalize_model_id(canonical_model_id) or canonical_model_id
    )
    model_definition = language_model_service.get_model_definition(normalized_canonical_model_id)
    # The curated catalog is advisory: it supplies defaults and reasoning
    # metadata. A curated model that is not supported by the chosen provider is
    # still rejected, but unknown/custom model ids are accepted so users can
    # configure new models without a code change.
    if model_definition is not None and not model_supports_connection_kind(
        model_definition, connection_kind
    ):
        errors["canonicalModelId"] = ["This model is not supported by the selected provider."]

    if errors:
        raise ModelConnectionValidationError(errors)

    return normalized_canonical_model_id, model_definition


def _compute_effective_validation_state(
    *,
    connection_kind: str,
    canonical_model_id: str,
    provider_config: ModelConnectionProviderConfig | None,
    credential_refs: ModelConnectionCredentialRefs | None,
    model_definition: Any | None = None,
) -> str:
    provider_validation_state = infer_model_connection_validation_state(
        connection_kind=connection_kind,
        provider_config=provider_config,
        credential_refs=credential_refs,
    )
    if provider_validation_state == "invalid":
        return provider_validation_state

    resolved_model_definition = (
        model_definition or _get_language_model_service().get_model_definition(canonical_model_id)
    )
    # Unknown/custom models have no catalog metadata; they are valid as long as
    # the provider config and credentials satisfy the provider requirements. A
    # known model that the provider cannot serve is still invalid.
    if resolved_model_definition is not None and not model_supports_connection_kind(
        resolved_model_definition,
        connection_kind,
    ):
        return "invalid"

    return provider_validation_state


def _normalize_secret_ref(
    secret_ref: str | None,
    row_id: str,
    field_name: str = "apiKeyRef",
) -> str | None:
    if not secret_ref:
        return None
    if secret_ref.startswith("local-secret://"):
        return secret_ref
    suffix = _SECRET_FIELD_SUFFIXES.get(field_name, "credential")
    return f"local-secret://model-connections/{row_id}/{suffix}"


def _extract_secret_value(secret_ref: str | None, preserved_value: str | None = None) -> str | None:
    if not secret_ref:
        return preserved_value
    if secret_ref.startswith("local-secret://"):
        return preserved_value
    return secret_ref


def _loads_json_blob(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _dumps_json_blob(value: dict[str, Any] | None) -> str | None:
    if not value:
        return None
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _read_connection_config(row: _LocalModelConnectionDB) -> dict[str, Any]:
    return _loads_json_blob(row.connection_config_json) or {}


def _read_secret_values(row: _LocalModelConnectionDB) -> dict[str, str]:
    secret_values = _loads_json_blob(row.secret_values_json) or {}
    if row.secret_value and "apiKey" not in secret_values:
        secret_values["apiKey"] = row.secret_value
    return {
        key: str(value)
        for key, value in secret_values.items()
        if isinstance(value, str) and value.strip()
    }


def _serialize_reasoning_effort(effort: object | None) -> str | None:
    """Serialize a reasoning effort for the legacy `default_sampling_json` column."""
    value = enum_value(effort)
    if not value:
        return None
    return _dumps_json_blob({"reasoningEffort": value})


def _read_reasoning_effort(row: _LocalModelConnectionDB) -> ModelReasoningEffort | None:
    """Return the persisted reasoning effort, tolerating legacy sampling blobs.

    Older rows stored a `default_sampling_json` blob that may also contain
    removed fields (temperature, topP, maxTokens). Only the reasoning effort is
    still meaningful.
    """
    payload = _loads_json_blob(row.default_sampling_json)
    if not payload:
        return None
    effort = payload.get("reasoningEffort") or payload.get("reasoning_effort")
    if not isinstance(effort, str) or not effort:
        return None
    try:
        return ModelReasoningEffort(effort)
    except ValueError:
        return None


def _has_provider_config_values(
    provider_config: ModelConnectionProviderConfig | None,
) -> bool:
    return bool(
        provider_config
        and (
            provider_config.endpoint_base_url
            or provider_config.provider_model_name
            or provider_config.region
            or provider_config.project_id
            or provider_config.location
            or provider_config.api_version
        )
    )


def _has_credential_refs(
    credential_refs: ModelConnectionCredentialRefs | None,
) -> bool:
    return bool(
        credential_refs
        and (
            credential_refs.api_key_ref
            or credential_refs.access_key_id_ref
            or credential_refs.secret_access_key_ref
            or credential_refs.session_token_ref
        )
    )


def _has_any_credential_input(connection: ModelConnection) -> bool:
    return bool(
        connection.secret_ref
        or (
            connection.credential_refs
            and (
                connection.credential_refs.api_key_ref
                or connection.credential_refs.access_key_id_ref
                or connection.credential_refs.secret_access_key_ref
                or connection.credential_refs.session_token_ref
            )
        )
    )


def _build_provider_config(
    *,
    provider_config: ModelConnectionProviderConfig | None,
    provider_model_name: str | None,
    endpoint_base_url: str | None,
) -> ModelConnectionProviderConfig | None:
    resolved = (
        provider_config.model_copy(deep=True)
        if provider_config is not None
        else ModelConnectionProviderConfig()
    )

    if not resolved.provider_model_name and provider_model_name:
        resolved.provider_model_name = provider_model_name
    if not resolved.endpoint_base_url and endpoint_base_url:
        resolved.endpoint_base_url = endpoint_base_url

    return resolved if _has_provider_config_values(resolved) else None


def _read_provider_config(
    connection_config: dict[str, Any],
) -> ModelConnectionProviderConfig | None:
    raw_provider_config = connection_config.get("providerConfig")
    provider_config = (
        model_validate_stored(ModelConnectionProviderConfig, raw_provider_config)
        if isinstance(raw_provider_config, dict)
        else None
    )
    return _build_provider_config(
        provider_config=provider_config,
        provider_model_name=connection_config.get("providerModelName"),
        endpoint_base_url=connection_config.get("endpointBaseUrl"),
    )


def _normalize_credential_ref(
    value: str | None,
    *,
    row_id: str,
    field_name: str,
    preserved_value: str | None = None,
) -> str | None:
    if not value:
        return preserved_value
    return _normalize_secret_ref(value, row_id, field_name)


def _build_credential_refs(
    *,
    credential_refs: ModelConnectionCredentialRefs | None,
    secret_ref: str | None,
    row_id: str,
    existing_credential_refs: ModelConnectionCredentialRefs | None = None,
    preserve_existing: bool = False,
) -> ModelConnectionCredentialRefs | None:
    api_key_input = (
        credential_refs.api_key_ref if credential_refs is not None else None
    ) or secret_ref

    resolved = ModelConnectionCredentialRefs(
        api_key_ref=_normalize_credential_ref(
            api_key_input,
            row_id=row_id,
            field_name="apiKeyRef",
            preserved_value=(
                existing_credential_refs.api_key_ref
                if preserve_existing and existing_credential_refs
                else None
            ),
        ),
        access_key_id_ref=_normalize_credential_ref(
            credential_refs.access_key_id_ref if credential_refs else None,
            row_id=row_id,
            field_name="accessKeyIdRef",
            preserved_value=(
                existing_credential_refs.access_key_id_ref
                if preserve_existing and existing_credential_refs
                else None
            ),
        ),
        secret_access_key_ref=_normalize_credential_ref(
            credential_refs.secret_access_key_ref if credential_refs else None,
            row_id=row_id,
            field_name="secretAccessKeyRef",
            preserved_value=(
                existing_credential_refs.secret_access_key_ref
                if preserve_existing and existing_credential_refs
                else None
            ),
        ),
        session_token_ref=_normalize_credential_ref(
            credential_refs.session_token_ref if credential_refs else None,
            row_id=row_id,
            field_name="sessionTokenRef",
            preserved_value=(
                existing_credential_refs.session_token_ref
                if preserve_existing and existing_credential_refs
                else None
            ),
        ),
    )

    return resolved if _has_credential_refs(resolved) else None


def _read_credential_refs(
    row: _LocalModelConnectionDB,
    connection_config: dict[str, Any],
) -> ModelConnectionCredentialRefs | None:
    raw_credential_refs = connection_config.get("credentialRefs")
    credential_refs = (
        ModelConnectionCredentialRefs.model_validate(raw_credential_refs)
        if isinstance(raw_credential_refs, dict)
        else ModelConnectionCredentialRefs()
    )
    secret_values = _read_secret_values(row)

    if not credential_refs.api_key_ref and connection_config.get("secretRef"):
        credential_refs.api_key_ref = str(connection_config["secretRef"])

    for field_name, value_key in _SECRET_VALUE_KEYS.items():
        attribute_name = _CREDENTIAL_REF_ATTRS[field_name]
        if getattr(credential_refs, attribute_name, None):
            continue
        if secret_values.get(value_key):
            setattr(
                credential_refs,
                attribute_name,
                _normalize_secret_ref("configured", row.id, field_name),
            )

    return credential_refs if _has_credential_refs(credential_refs) else None


def _build_secret_values(
    *,
    credential_refs: ModelConnectionCredentialRefs | None,
    secret_ref: str | None,
    existing_secret_values: dict[str, str] | None = None,
    preserve_existing: bool = False,
) -> dict[str, str]:
    preserved = existing_secret_values if preserve_existing else {}
    api_key_input = (
        credential_refs.api_key_ref if credential_refs is not None else None
    ) or secret_ref
    secret_values = {
        "apiKey": _extract_secret_value(
            api_key_input, preserved.get("apiKey") if preserved else None
        ),
        "accessKeyId": _extract_secret_value(
            credential_refs.access_key_id_ref if credential_refs else None,
            preserved.get("accessKeyId") if preserved else None,
        ),
        "secretAccessKey": _extract_secret_value(
            credential_refs.secret_access_key_ref if credential_refs else None,
            preserved.get("secretAccessKey") if preserved else None,
        ),
        "sessionToken": _extract_secret_value(
            credential_refs.session_token_ref if credential_refs else None,
            preserved.get("sessionToken") if preserved else None,
        ),
    }
    return {
        key: value
        for key, value in secret_values.items()
        if isinstance(value, str) and value.strip()
    }


def _serialize_secret_values(
    secret_values: dict[str, str],
) -> tuple[str | None, str | None]:
    if not secret_values:
        return None, None
    if set(secret_values) == {"apiKey"}:
        return secret_values["apiKey"], None
    return None, _dumps_json_blob(secret_values)


def _build_connection_config(
    *,
    provider_config: ModelConnectionProviderConfig | None,
    credential_refs: ModelConnectionCredentialRefs | None,
) -> dict[str, Any] | None:
    config: dict[str, Any] = {}
    if provider_config:
        config["providerConfig"] = provider_config.model_dump(by_alias=True, exclude_none=True)
        if provider_config.provider_model_name:
            config["providerModelName"] = provider_config.provider_model_name
        if provider_config.endpoint_base_url:
            config["endpointBaseUrl"] = provider_config.endpoint_base_url
    if credential_refs:
        config["credentialRefs"] = credential_refs.model_dump(by_alias=True, exclude_none=True)
        if credential_refs.api_key_ref:
            config["secretRef"] = credential_refs.api_key_ref
    return config or None


def _row_to_model_connection(row: _LocalModelConnectionDB) -> ModelConnection:
    connection_config = _read_connection_config(row)
    provider_config = _read_provider_config(connection_config)
    credential_refs = _read_credential_refs(row, connection_config)
    secret_values = _read_secret_values(row)
    language_model_service = _get_language_model_service()
    normalized_canonical_model_id = (
        language_model_service.normalize_model_id(row.canonical_model_id) or row.canonical_model_id
    )
    model_definition = language_model_service.get_model_definition(normalized_canonical_model_id)
    effective_validation_state = _compute_effective_validation_state(
        connection_kind=row.connection_kind,
        canonical_model_id=normalized_canonical_model_id,
        provider_config=provider_config,
        credential_refs=credential_refs,
        model_definition=model_definition,
    )
    return ModelConnection(
        id=row.id,
        source_type=ModelConnectionSourceType(row.source_type),
        adapter_type=ModelAdapterType(_resolve_adapter_type(row.connection_kind, row.adapter_type)),
        connection_kind=ModelConnectionKind(row.connection_kind),
        canonical_model_id=normalized_canonical_model_id,
        display_name=row.display_name,
        provider_config=provider_config,
        credential_refs=credential_refs,
        provider_model_name=(provider_config.provider_model_name if provider_config else None),
        endpoint_base_url=(provider_config.endpoint_base_url if provider_config else None),
        secret_ref=credential_refs.api_key_ref if credential_refs else None,
        secret_configured=bool(
            row.secret_configured or _has_credential_refs(credential_refs) or secret_values
        ),
        reasoning_effort=_read_reasoning_effort(row),
        is_default=bool(row.is_default),
        enabled=bool(row.enabled),
        validation_state=ModelValidationState(effective_validation_state),
        owner_id=row.owner_id,
    )


def list_model_connections() -> list[ModelConnection]:
    """Return all local model connection entries."""
    with get_sync_db_session() as session:
        rows = (
            session.execute(
                select(_LocalModelConnectionDB).order_by(_LocalModelConnectionDB.display_name)
            )
            .scalars()
            .all()
        )
        return [_row_to_model_connection(row) for row in rows]


def get_model_connection(connection_id: str) -> ModelConnection | None:
    """Return the model connection with *connection_id*, or None."""
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalModelConnectionDB).where(_LocalModelConnectionDB.id == connection_id)
        ).scalar_one_or_none()
        return _row_to_model_connection(row) if row else None


def create_model_connection(data: ModelConnection) -> ModelConnection:
    """Persist a new model connection; raw secrets are masked on reads."""
    with get_sync_db_session() as session:
        new_id = data.id if data.id else str(uuid4())
        source_type = _require_enum_value(data.source_type, field_name="source_type")
        connection_kind = _require_enum_value(data.connection_kind, field_name="connection_kind")
        adapter_type = _resolve_adapter_type(connection_kind, data.adapter_type)
        provider_config = _build_provider_config(
            provider_config=data.provider_config,
            provider_model_name=data.provider_model_name,
            endpoint_base_url=data.endpoint_base_url,
        )
        canonical_model_id, model_definition = _validate_and_normalize_model_selection(
            connection_kind=connection_kind,
            canonical_model_id=data.canonical_model_id,
            provider_config=provider_config,
        )
        credential_refs = _build_credential_refs(
            credential_refs=data.credential_refs,
            secret_ref=data.secret_ref,
            row_id=new_id,
        )
        secret_values = _build_secret_values(
            credential_refs=data.credential_refs,
            secret_ref=data.secret_ref,
        )
        secret_value, secret_values_json = _serialize_secret_values(secret_values)
        row = _LocalModelConnectionDB(
            id=new_id,
            source_type=source_type,
            adapter_type=adapter_type,
            connection_kind=connection_kind,
            canonical_model_id=canonical_model_id,
            display_name=data.display_name,
            connection_config_json=_dumps_json_blob(
                _build_connection_config(
                    provider_config=provider_config,
                    credential_refs=credential_refs,
                )
            ),
            secret_value=secret_value,
            secret_values_json=secret_values_json,
            secret_configured=bool(_has_credential_refs(credential_refs) or secret_values),
            default_sampling_json=_serialize_reasoning_effort(data.reasoning_effort),
            is_default=bool(data.is_default),
            enabled=bool(data.enabled),
            validation_state=_compute_effective_validation_state(
                connection_kind=connection_kind,
                canonical_model_id=canonical_model_id,
                provider_config=provider_config,
                credential_refs=credential_refs,
                model_definition=model_definition,
            ),
            owner_id=data.owner_id,
        )
        if row.is_default:
            for other in session.execute(select(_LocalModelConnectionDB)).scalars():
                other.is_default = False
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_model_connection(row)


def update_model_connection(connection_id: str, data: ModelConnection) -> ModelConnection | None:
    """Update an existing model connection; returns None if not found."""
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalModelConnectionDB).where(_LocalModelConnectionDB.id == connection_id)
        ).scalar_one_or_none()
        if row is None:
            return None

        preserve_existing_secret = bool(
            data.secret_configured and not _has_any_credential_input(data)
        )
        source_type = _require_enum_value(data.source_type, field_name="source_type")
        connection_kind = _require_enum_value(data.connection_kind, field_name="connection_kind")
        adapter_type = _resolve_adapter_type(connection_kind, data.adapter_type)
        existing_config = _read_connection_config(row)
        existing_credential_refs = _read_credential_refs(row, existing_config)
        existing_secret_values = _read_secret_values(row)
        provider_config = _build_provider_config(
            provider_config=data.provider_config,
            provider_model_name=data.provider_model_name,
            endpoint_base_url=data.endpoint_base_url,
        )
        canonical_model_id, model_definition = _validate_and_normalize_model_selection(
            connection_kind=connection_kind,
            canonical_model_id=data.canonical_model_id,
            provider_config=provider_config,
        )
        credential_refs = _build_credential_refs(
            credential_refs=data.credential_refs,
            secret_ref=data.secret_ref,
            row_id=row.id,
            existing_credential_refs=existing_credential_refs,
            preserve_existing=preserve_existing_secret,
        )
        secret_values = _build_secret_values(
            credential_refs=data.credential_refs,
            secret_ref=data.secret_ref,
            existing_secret_values=existing_secret_values,
            preserve_existing=preserve_existing_secret,
        )
        secret_value, secret_values_json = _serialize_secret_values(secret_values)
        row.source_type = source_type
        row.adapter_type = adapter_type
        row.connection_kind = connection_kind
        row.canonical_model_id = canonical_model_id
        row.display_name = data.display_name
        row.secret_value = secret_value
        row.secret_values_json = secret_values_json
        row.secret_configured = bool(_has_credential_refs(credential_refs) or secret_values)
        row.connection_config_json = _dumps_json_blob(
            _build_connection_config(
                provider_config=provider_config,
                credential_refs=credential_refs,
            )
        )
        row.default_sampling_json = _serialize_reasoning_effort(data.reasoning_effort)
        row.is_default = bool(data.is_default)
        row.enabled = bool(data.enabled)
        row.validation_state = _compute_effective_validation_state(
            connection_kind=connection_kind,
            canonical_model_id=canonical_model_id,
            provider_config=provider_config,
            credential_refs=credential_refs,
            model_definition=model_definition,
        )
        row.owner_id = data.owner_id
        if row.is_default:
            for other in session.execute(
                select(_LocalModelConnectionDB).where(_LocalModelConnectionDB.id != connection_id)
            ).scalars():
                other.is_default = False
        session.commit()
        session.refresh(row)
        return _row_to_model_connection(row)


def delete_model_connection(connection_id: str) -> bool:
    """Delete a model connection entry; returns True if deleted."""
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalModelConnectionDB).where(_LocalModelConnectionDB.id == connection_id)
        ).scalar_one_or_none()
        if row is None:
            return False
        session.delete(row)
        session.commit()
        return True


def resolve_model_connection_credentials(connection_id: str) -> dict[str, str]:
    """Return raw stored credential values for internal runtime resolution."""
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalModelConnectionDB).where(_LocalModelConnectionDB.id == connection_id)
        ).scalar_one_or_none()
        if row is None:
            return {}
        return _read_secret_values(row)


def resolve_model_connection_secret(connection_id: str) -> str | None:
    """Return the API key secret for internal runtime resolution when present."""
    return resolve_model_connection_credentials(connection_id).get("apiKey")
