"""Model selection resolution for executable model connections.

This module resolves a model *selection* to a secret-safe runtime snapshot. It
is deliberately free of deployment concerns: local-store access is supplied
through the port in :mod:`.model_connection_store`, so this package never imports
``kontext-account`` or ``kontext-runtime``.
"""

from __future__ import annotations

from kontext.common.contracts import ResolvedModelConfig
from kontext.schema import (
    FoundationModel,
    ModelConnectionCredentialRefs,
    ModelConnectionProviderConfig,
    ModelReasoningEffort,
)

from .model_connection_store import get_local_model_store
from .provider_definitions import get_default_provider_model_name
from .service import LanguageModelService


def _build_resolved_config(
    *,
    selection_id: str,
    source_type: str,
    adapter_type: str,
    connection_kind: str,
    display_name: str,
    provider_config: ModelConnectionProviderConfig | None,
    credential_refs: ModelConnectionCredentialRefs | None,
    provider_model_name: str | None,
    endpoint_base_url: str | None,
    secret_ref: str | None,
    reasoning_effort: ModelReasoningEffort | None,
    model_meta: FoundationModel | None,
) -> ResolvedModelConfig:
    resolved_provider_model_name = (
        provider_model_name
        or (provider_config.provider_model_name if provider_config else None)
        or (
            get_default_provider_model_name(model_meta, connection_kind)
            if model_meta is not None
            else None
        )
    )
    resolved_endpoint_base_url = endpoint_base_url or (
        provider_config.endpoint_base_url if provider_config else None
    )
    resolved_secret_ref = secret_ref or (credential_refs.api_key_ref if credential_refs else None)

    return ResolvedModelConfig(
        selection_id=selection_id,
        canonical_model_id=(
            model_meta.canonical_model_id if model_meta else resolved_provider_model_name or ""
        ),
        source_type=source_type,
        adapter_type=adapter_type,
        connection_kind=connection_kind,
        display_name=display_name,
        provider_model_name=resolved_provider_model_name,
        endpoint_base_url=resolved_endpoint_base_url,
        secret_ref=resolved_secret_ref,
        region=provider_config.region if provider_config else None,
        project_id=provider_config.project_id if provider_config else None,
        location=provider_config.location if provider_config else None,
        api_version=provider_config.api_version if provider_config else None,
        reasoning_effort=reasoning_effort,
    )


async def resolve_model_selection(
    *,
    selection_id: str,
    project_id: str | None = None,
    auth_manager=None,
) -> ResolvedModelConfig:
    """Resolve a model selection to a secret-safe runtime snapshot.

    Kontext runs local-first, so selection is resolved from the locally
    registered model-connection store (supplied by composition via
    :mod:`.model_connection_store`).
    """
    model_service = LanguageModelService()
    local_store = get_local_model_store()

    if local_store is None:
        raise LookupError(
            "No local model store is registered. Call "
            "kontext.runtime.model_connection_store.configure_model_resolution() at startup."
        )

    connection = local_store.get_model_connection(selection_id)
    if connection is None:
        raise LookupError(f"Model connection '{selection_id}' was not found.")

    model_meta = model_service.get_model_definition(connection.canonical_model_id)
    return _build_resolved_config(
        selection_id=selection_id,
        source_type=connection.source_type,
        adapter_type=connection.adapter_type,
        connection_kind=connection.connection_kind,
        display_name=connection.display_name,
        provider_config=connection.provider_config,
        credential_refs=connection.credential_refs,
        provider_model_name=connection.provider_model_name,
        endpoint_base_url=connection.endpoint_base_url,
        secret_ref=connection.secret_ref,
        reasoning_effort=connection.reasoning_effort,
        model_meta=model_meta,
    )


def resolve_runtime_credentials(
    resolved_config: ResolvedModelConfig,
) -> dict[str, str]:
    """Resolve raw secret values for local runtime execution when available."""
    if not resolved_config.selection_id:
        # The app-default binding has no persisted connection record.
        return {}
    local_store = get_local_model_store()
    if local_store is None:
        return {}
    return local_store.resolve_model_connection_credentials(resolved_config.selection_id)
