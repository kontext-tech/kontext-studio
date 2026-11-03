"""Language model services, resources, and model-construction helpers."""

from kontext.common.contracts import ResolvedModelConfig

from .model_connection_store import (
    ModelConnectionStore,
    register_local_model_store,
    reset_model_resolution_hooks,
)
from .model_selection import (
    resolve_model_selection,
    resolve_runtime_credentials,
)
from .provider_definitions import (
    get_connection_adapter_type,
    get_default_provider_model_name,
    infer_model_connection_validation_state,
    list_model_provider_definitions,
    model_supports_connection_kind,
    normalize_foundation_model_id,
    resolve_default_model_id,
    split_provider_prefix,
    strip_known_provider_prefix,
)
from .service import LanguageModelService

__all__ = [
    "LanguageModelService",
    "ModelConnectionStore",
    "ResolvedModelConfig",
    "get_connection_adapter_type",
    "get_default_provider_model_name",
    "infer_model_connection_validation_state",
    "list_model_provider_definitions",
    "model_supports_connection_kind",
    "normalize_foundation_model_id",
    "register_local_model_store",
    "reset_model_resolution_hooks",
    "resolve_default_model_id",
    "resolve_model_selection",
    "resolve_runtime_credentials",
    "split_provider_prefix",
    "strip_known_provider_prefix",
]
