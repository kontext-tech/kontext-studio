"""Harness-neutral model/provider catalog and resolution helpers.

This module owns the mapping from a resolved model selection (a
``ResolvedModelConfig``) to a *provider name*, plus the environment/credential
lookups needed to build a provider client. It deliberately contains no
framework SDK imports: the concrete model objects are constructed by the active
agent harness adapter (e.g. ``kontext.harness.agno.providers``).

Provider metadata (adapter, default model id, env var names) comes from
``resources/models/model-provider-definitions.json`` via
:mod:`.provider_definitions`; this module adds no parallel tables of its own.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from kontext.common.contracts import ResolvedModelConfig
from kontext.common.utils.enum_utils import enum_value

from .provider_definitions import (
    ADAPTER_DEFAULT_PROVIDER,
    get_api_base_env_var,
    get_api_key_env_var,
    get_default_endpoint_base_url,
    get_provider_display_names,
)

if TYPE_CHECKING:
    from kontext.schema import FoundationModel, ModelReasoningEffort


def get_provider_display_name(provider: str) -> str:
    return get_provider_display_names().get(provider, provider)


def normalize_reasoning_kwargs(
    provider: str,
    reasoning_effort: ModelReasoningEffort | None,
) -> dict[str, Any]:
    """Translate a neutral reasoning effort into provider-specific kwargs."""
    effort_value = enum_value(reasoning_effort)
    if effort_value is None:
        return {}

    if provider in {"lm_studio", "ollama", "openai", "openai_compatible", "openrouter"}:
        return {"reasoning_effort": effort_value}
    if provider == "gemini":
        # Gemini thinking controls are model-specific. Our shared service always
        # supplies a default reasoning effort, so avoid translating that generic
        # default into Gemini's provider-specific thinking_level by default.
        return {}
    return {}


def resolve_provider_from_resolved_config(resolved_config: ResolvedModelConfig) -> str | None:
    """Infer a provider name from a resolved model binding."""
    if resolved_config.connection_kind and resolved_config.connection_kind != "platform":
        return resolved_config.connection_kind
    return ADAPTER_DEFAULT_PROVIDER.get(resolved_config.adapter_type)


def resolve_provider_from_model_definition(model_definition: FoundationModel) -> str | None:
    """Infer a provider name from a foundation-model definition.

    Models may list several connection kinds. The catalog orders the primary
    provider first (aggregators such as ``openrouter`` and secondary backends
    follow), so the first non-``platform`` kind is the intended provider. This
    is deterministic for a given catalog and avoids over-eager adapter matching,
    which is ambiguous for shared adapter types like ``openai_compatible``.
    """
    supported_kinds = getattr(model_definition, "supported_connection_kinds", None) or []
    for connection_kind in supported_kinds:
        normalized = getattr(connection_kind, "value", connection_kind)
        if isinstance(normalized, str) and normalized != "platform":
            return normalized
    return None


def resolve_base_url(provider: str, resolved_config: ResolvedModelConfig) -> str | None:
    """Resolve an API base URL from the binding, env, or provider definition."""
    if resolved_config.endpoint_base_url:
        return resolved_config.endpoint_base_url
    env_var = get_api_base_env_var(provider)
    if env_var:
        env_value = os.getenv(env_var)
        if env_value:
            return env_value
    return get_default_endpoint_base_url(provider)


def resolve_api_key(
    provider: str,
    credentials: dict[str, str],
) -> str | None:
    """Resolve an API key from runtime credentials or env."""
    if credentials.get("apiKey"):
        return credentials["apiKey"]
    env_var = get_api_key_env_var(provider)
    if env_var:
        env_value = os.getenv(env_var)
        if env_value:
            return env_value
    return None
