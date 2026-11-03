"""Model-provider definitions and derived lookup tables.

The provider tables in this module are derived from
``resources/models/model-provider-definitions.json`` at import time. That JSON
file is the single source of truth for provider metadata (adapter mapping,
default model id, env var names, config/credential requirements); there are no
hand-maintained parallel copies to drift out of sync.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from importlib import resources

from kontext.common.utils.enum_utils import enum_value
from kontext.schema import (
    FoundationModel,
    ModelConnectionCredentialRefs,
    ModelConnectionKind,
    ModelConnectionProviderConfig,
    ModelProviderDefinition,
)

logger = logging.getLogger(__name__)


def parse_json_array(data: str) -> list[object]:
    """Parse a JSON array into a list of items."""
    raw = json.loads(data)
    if not isinstance(raw, list):
        raise ValueError("Expected a JSON array of objects")
    return raw


@lru_cache(maxsize=1)
def load_model_provider_definitions() -> tuple[ModelProviderDefinition, ...]:
    """Load and validate the packaged provider definitions.

    Package-owned data must be correct at release time, so parse/validation
    failures raise instead of silently disabling every provider.
    """
    resource_path = (
        resources.files("kontext.llm.resources.models") / "model-provider-definitions.json"
    )
    with resource_path.open("r") as handle:
        data = handle.read()

    definitions = tuple(
        ModelProviderDefinition.model_validate(item) for item in parse_json_array(data)
    )

    kinds = [enum_value(definition.connection_kind) or "" for definition in definitions]
    duplicates = sorted({kind for kind in kinds if kinds.count(kind) > 1})
    if duplicates:
        raise ValueError(
            f"Duplicate connection kinds in model-provider-definitions.json: {duplicates}"
        )

    return definitions


def list_model_provider_definitions() -> list[ModelProviderDefinition]:
    return list(load_model_provider_definitions())


def _get_model_provider_definition(
    connection_kind: str | ModelConnectionKind | None,
) -> ModelProviderDefinition | None:
    kind_value = enum_value(connection_kind)
    if not kind_value:
        return None
    for definition in load_model_provider_definitions():
        if enum_value(definition.connection_kind) == kind_value:
            return definition
    return None


def _definition_attribute(
    connection_kind: str | ModelConnectionKind | None,
    attribute: str,
) -> str | None:
    definition = _get_model_provider_definition(connection_kind)
    if definition is None:
        return None
    value = getattr(definition, attribute, None)
    return value if isinstance(value, str) and value else None


# Derived provider tables. `platform` is intentionally absent: it is an
# internal pseudo-provider with no runtime adapter.
CONNECTION_KIND_TO_ADAPTER_TYPE: dict[str, str] = {
    kind: adapter
    for definition in load_model_provider_definitions()
    if (kind := enum_value(definition.connection_kind))
    and (adapter := enum_value(definition.adapter_type))
}

SUPPORTED_PROVIDERS = frozenset(CONNECTION_KIND_TO_ADAPTER_TYPE)

PROVIDER_MODEL_ENV_VARS: dict[str, str] = {
    kind: env_var
    for definition in load_model_provider_definitions()
    if (kind := enum_value(definition.connection_kind)) and (env_var := definition.model_env_var)
}

DEFAULT_MODEL_IDS: dict[str, str] = {
    kind: model_id
    for definition in load_model_provider_definitions()
    if (kind := enum_value(definition.connection_kind))
    and (model_id := definition.default_model_id)
}

# Adapter -> provider fallback for the internal `platform` pseudo-provider
# (a resolved selection with no explicit connection kind). First definition
# wins per adapter type; shared adapters (e.g. ``openai_compatible``) resolve
# to their first registered provider.
ADAPTER_DEFAULT_PROVIDER: dict[str, str] = {}
for _definition in load_model_provider_definitions():
    _kind = enum_value(_definition.connection_kind)
    _adapter = enum_value(_definition.adapter_type)
    if _kind and _adapter and _adapter not in ADAPTER_DEFAULT_PROVIDER:
        ADAPTER_DEFAULT_PROVIDER[_adapter] = _kind
del _definition, _kind, _adapter


def get_provider_display_names() -> dict[str, str]:
    return {
        kind: display_name
        for definition in load_model_provider_definitions()
        if (kind := enum_value(definition.connection_kind))
        and (display_name := definition.display_name)
    }


def get_connection_adapter_type(
    connection_kind: str | ModelConnectionKind | None,
) -> str | None:
    definition = _get_model_provider_definition(connection_kind)
    if definition is not None:
        return enum_value(definition.adapter_type)
    kind_value = enum_value(connection_kind)
    if not kind_value:
        return None
    return CONNECTION_KIND_TO_ADAPTER_TYPE.get(kind_value)


def get_default_endpoint_base_url(
    connection_kind: str | ModelConnectionKind | None,
) -> str | None:
    """Return the provider's default endpoint base URL from its definition."""
    definition = _get_model_provider_definition(connection_kind)
    if definition is None:
        return None
    return definition.default_endpoint_base_url


def get_model_env_var(connection_kind: str | ModelConnectionKind | None) -> str | None:
    return _definition_attribute(connection_kind, "model_env_var")


def get_api_key_env_var(connection_kind: str | ModelConnectionKind | None) -> str | None:
    return _definition_attribute(connection_kind, "api_key_env_var")


def get_api_base_env_var(connection_kind: str | ModelConnectionKind | None) -> str | None:
    return _definition_attribute(connection_kind, "api_base_env_var")


def get_api_version_env_var(connection_kind: str | ModelConnectionKind | None) -> str | None:
    return _definition_attribute(connection_kind, "api_version_env_var")


def get_project_id_env_var(connection_kind: str | ModelConnectionKind | None) -> str | None:
    return _definition_attribute(connection_kind, "project_id_env_var")


def get_region_env_var(connection_kind: str | ModelConnectionKind | None) -> str | None:
    return _definition_attribute(connection_kind, "region_env_var")


def normalize_foundation_model_id(model_id: str | None) -> str | None:
    if model_id is None:
        return None
    return model_id.strip()


def strip_known_provider_prefix(model_id: str | None) -> str | None:
    """Drop a leading ``<provider>/`` when ``provider`` is a known connection kind.

    Curated ids are namespaced by vendor namespace, not provider (e.g.
    ``google/gemini-2.5-flash`` on Gemini, ``deepseek/deepseek-chat`` on
    DeepSeek), so only an actual provider name is stripped. Unrelated namespaces
    (OpenRouter vendor ids) are preserved.
    """
    if not model_id or "/" not in model_id:
        return model_id
    prefix, remainder = model_id.split("/", 1)
    return remainder if prefix in SUPPORTED_PROVIDERS else model_id


def split_provider_prefix(model_id: str | None) -> str | None:
    """Return the well-known provider prefix of a model id, if it has one.

    ``"openai/gpt-4.1"`` -> ``"openai"``; vendor-namespaced ids (OpenRouter,
    shared OpenAI-compatible endpoints) yield ``None``.
    """
    if not model_id or "/" not in model_id:
        return None
    prefix, _ = model_id.split("/", 1)
    return prefix if prefix in SUPPORTED_PROVIDERS else None


def resolve_default_model_id(provider: str) -> str:
    """Resolve a provider's default model id from env or the derived table."""
    env_var = get_model_env_var(provider)
    if env_var and (env_value := os.getenv(env_var)):
        return env_value
    return DEFAULT_MODEL_IDS.get(provider, DEFAULT_MODEL_IDS["lm_studio"])


def strip_own_provider_prefix(model_id: str, provider: str) -> str:
    """Drop a leading prefix that equals the provider's own connection kind.

    Distinct from :func:`strip_known_provider_prefix`: aggregators (OpenRouter)
    and generic OpenAI-compatible endpoints use vendor-namespaced ids, so a
    prefix that is not exactly ``provider`` is part of the model name.
    """
    if "/" in model_id:
        prefix, remainder = model_id.split("/", 1)
        if prefix == provider:
            return remainder
    return model_id


def get_required_config_fields(
    connection_kind: str | ModelConnectionKind | None,
) -> set[str]:
    definition = _get_model_provider_definition(connection_kind)
    if definition is None:
        return set()
    return {value for field in definition.required_config_fields if (value := enum_value(field))}


def get_required_credential_fields(
    connection_kind: str | ModelConnectionKind | None,
) -> set[str]:
    definition = _get_model_provider_definition(connection_kind)
    if definition is None:
        return set()
    return {
        value for field in definition.required_credential_fields if (value := enum_value(field))
    }


def infer_model_connection_validation_state(
    *,
    connection_kind: str | ModelConnectionKind,
    provider_config: ModelConnectionProviderConfig | None,
    credential_refs: ModelConnectionCredentialRefs | None,
) -> str:
    kind_value = enum_value(connection_kind)
    if kind_value == "platform":
        return "valid"

    definition = _get_model_provider_definition(kind_value)
    if definition is None:
        return "unknown"

    config_values = (
        provider_config.model_dump(by_alias=True, exclude_none=True) if provider_config else {}
    )
    credential_values = (
        credential_refs.model_dump(by_alias=True, exclude_none=True) if credential_refs else {}
    )

    required_config_fields = get_required_config_fields(kind_value)
    required_credential_fields = get_required_credential_fields(kind_value)

    has_required_config = all(
        isinstance(config_values.get(field_name), str) and str(config_values[field_name]).strip()
        for field_name in required_config_fields
    )
    has_required_credentials = all(
        isinstance(credential_values.get(field_name), str)
        and str(credential_values[field_name]).strip()
        for field_name in required_credential_fields
    )

    return "valid" if has_required_config and has_required_credentials else "pending"


def get_default_provider_model_name(
    model: FoundationModel,
    connection_kind: str | ModelConnectionKind,
) -> str:
    kind_value = enum_value(connection_kind)
    aliases = model.provider_model_aliases or {}
    if kind_value and kind_value in aliases:
        return aliases[kind_value]
    return model.canonical_model_id


def model_supports_connection_kind(
    model: FoundationModel,
    connection_kind: str | ModelConnectionKind | None,
) -> bool:
    """Whether a curated model can be served by a connection kind.

    Membership in ``supported_connection_kinds`` is the primary signal. As a
    fallback, a connection kind whose adapter type matches the model's adapter
    is accepted: generic OpenAI-compatible providers (``openai_compatible``,
    ``lm_studio``, ``ollama``, ``deepseek``, ``mistral``, ``openrouter``) all
    share the ``openai_compatible`` adapter, so a curated model that only lists
    its first-class kind (e.g. ``deepseek/deepseek-chat`` -> ``["deepseek"]``)
    stays usable through a legacy generic endpoint. The catalog is advisory, so
    this leniency is intentional and keeps pre-existing connections valid.
    """
    kind_value = enum_value(connection_kind)
    if not kind_value:
        return True

    supported_kinds = {enum_value(item) for item in model.supported_connection_kinds}
    supported_kinds.discard(None)

    if kind_value in supported_kinds:
        return True

    connection_adapter_type = CONNECTION_KIND_TO_ADAPTER_TYPE.get(kind_value)
    if connection_adapter_type is None:
        return not supported_kinds
    return model.adapter_type == connection_adapter_type
