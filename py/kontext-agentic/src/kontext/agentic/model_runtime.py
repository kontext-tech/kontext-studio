"""Resolve the model runtime (binding + credentials) for an agent run.

Composition owns this step: it turns a persisted chat-session selection into a
secret-free binding, falls back to the application default when the session has
no selection, and resolves the credentials for the current run. The harness
adapter receives the :class:`ModelRuntime` and never touches the global store.
"""

from __future__ import annotations

import os

from kontext.common.constants import ModelEnvVars
from kontext.common.contracts import ModelRuntime, ResolvedModelConfig
from kontext.llm import resolve_runtime_credentials
from kontext.llm.provider_definitions import (
    get_connection_adapter_type,
    normalize_foundation_model_id,
    resolve_default_model_id,
    strip_own_provider_prefix,
)


def default_model_binding() -> ResolvedModelConfig:
    """Build the application-default binding from environment settings."""
    provider = (os.getenv(ModelEnvVars.MODEL_PROVIDER) or "lm_studio").lower()
    model_id = resolve_default_model_id(provider)
    return ResolvedModelConfig(
        selection_id=None,
        canonical_model_id=normalize_foundation_model_id(model_id) or model_id,
        source_type="app_default",
        adapter_type=get_connection_adapter_type(provider) or provider,
        connection_kind=provider,
        display_name=provider,
        provider_model_name=strip_own_provider_prefix(model_id, provider),
    )


def build_model_runtime(binding: ResolvedModelConfig | None = None) -> ModelRuntime:
    """Resolve the run's model identity and credentials.

    Credentials are only looked up for a persisted selection; the app-default
    binding has no connection record, so it runs with environment credentials.
    """
    resolved = binding or default_model_binding()
    credentials = resolve_runtime_credentials(resolved) if resolved.selection_id else {}
    return ModelRuntime(binding=resolved, credentials=credentials)


__all__ = ["build_model_runtime", "default_model_binding"]
