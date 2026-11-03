"""Agno-native model construction from neutral resolved model selections.

This module is a thin dispatcher: provider resolution happens here, and the
concrete provider factories live in ``kontext.harness.agno.providers`` (one small
module per provider, selected through a connection-kind registry). The
provider/credential resolution helpers live in ``kontext.llm.provider_resolution``
so that package stays harness-neutral.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from kontext.common.contracts import ResolvedModelConfig
from kontext.llm import LanguageModelService
from kontext.llm.provider_definitions import (
    SUPPORTED_PROVIDERS,
    split_provider_prefix,
    strip_own_provider_prefix,
)
from kontext.llm.provider_resolution import (
    resolve_provider_from_model_definition,
    resolve_provider_from_resolved_config,
)
from kontext.schema import ModelReasoningEffort

from .providers import ModelRequest, get_provider_factory


def _runtime_model_id(
    model_id: str,
    provider: str,
    service: LanguageModelService,
) -> str:
    """Resolve the provider's runtime model name for a catalog/custom id.

    Local runtimes rename models (e.g. Ollama's ``gemma4:26b-a4b`` for the
    canonical ``google/gemma-4-26b-a4b``), so prefer the catalog's per-provider
    alias when one exists; otherwise fall back to the id with its own
    connection-kind prefix removed. Idempotent for ids that are already runtime
    names (custom ids, or aliases from a resolved selection).
    """
    definition = service.get_model_definition(model_id, provider)
    if definition is not None:
        alias = (definition.provider_model_aliases or {}).get(provider)
        if alias:
            return alias
    return strip_own_provider_prefix(model_id, provider)


def create_model(
    *,
    resolved_config: ResolvedModelConfig,
    credentials: Mapping[str, str] | None = None,
    reasoning_effort: ModelReasoningEffort | None = None,
) -> Any:
    """Create an Agno model instance from a resolved model runtime.

    Sampling knobs (temperature, top_p) are intentionally not user-configurable,
    and token limits come from curated model metadata at runtime rather than
    user input.

    Credentials are supplied by composition; this factory never reads the
    process-global model-connection store.
    """
    runtime_model_id = resolved_config.provider_model_name or resolved_config.canonical_model_id
    # The curated catalog is keyed by canonical ids, so resolve metadata from
    # the canonical id even when the runtime name is a provider alias.
    metadata_model_id = resolved_config.canonical_model_id or runtime_model_id
    provider = resolve_provider_from_resolved_config(resolved_config)
    runtime_credentials = dict(credentials or {})
    service = LanguageModelService()

    model_definition = (
        service.get_model_definition(metadata_model_id, provider) if metadata_model_id else None
    )
    max_tokens: int | None = model_definition.max_tokens if model_definition else None
    if model_definition:
        provider = provider or resolve_provider_from_model_definition(model_definition)

    if runtime_model_id:
        provider = provider or split_provider_prefix(runtime_model_id)

    if not provider:
        raise ValueError(
            "The resolved model binding has no provider. Resolve a model selection "
            "or a complete application default before materializing the agent."
        )
    provider = provider.lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported provider '{provider}'. Supported: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
        )

    if not runtime_model_id:
        raise ValueError(
            "The resolved model binding has no model id. Resolve a model selection "
            "or a complete application default before materializing the agent."
        )

    factory = get_provider_factory(provider)
    if factory is None:  # pragma: no cover - guarded by SUPPORTED_PROVIDERS
        raise ValueError(f"No Agno provider factory registered for '{provider}'.")

    request = ModelRequest(
        provider=provider,
        model_id=_runtime_model_id(runtime_model_id, provider, service),
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        resolved_config=resolved_config,
        credentials=runtime_credentials,
    )
    return factory(request)


__all__ = ["create_model"]
