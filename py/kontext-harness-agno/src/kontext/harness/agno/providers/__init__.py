"""Provider factory registry for the Agno harness.

Maps a normalized connection kind to the factory that builds its native Agno
model. This mirrors the reference architecture in ``pi``: each provider is a
tiny factory module, and the registry is the only place that knows the full
provider list.
"""

from __future__ import annotations

from kontext.llm.provider_definitions import SUPPORTED_PROVIDERS

from .anthropic import create_anthropic_model
from .azure_openai import create_azure_openai_model
from .base import ModelFactory, ModelRequest
from .bedrock import create_bedrock_model
from .deepseek import create_deepseek_model
from .gemini import create_gemini_model, create_google_vertex_model
from .lmstudio import create_lm_studio_model
from .mistral import create_mistral_model
from .ollama import create_ollama_cloud_model, create_ollama_model
from .openai import create_openai_model
from .openai_compatible import create_openai_compatible_model
from .openrouter import create_openrouter_model

PROVIDER_FACTORIES: dict[str, ModelFactory] = {
    "lm_studio": create_lm_studio_model,
    "ollama": create_ollama_model,
    "ollama_cloud": create_ollama_cloud_model,
    "openai": create_openai_model,
    "anthropic": create_anthropic_model,
    "gemini": create_gemini_model,
    "google_vertex": create_google_vertex_model,
    "deepseek": create_deepseek_model,
    "mistral": create_mistral_model,
    "openrouter": create_openrouter_model,
    "azure_openai": create_azure_openai_model,
    "bedrock": create_bedrock_model,
    "openai_compatible": create_openai_compatible_model,
}

# Provider kinds are the curated registry's single source of truth; fail loudly
# at import if this map drifts instead of failing per-request.
_MISSING = set(SUPPORTED_PROVIDERS) - set(PROVIDER_FACTORIES)
_UNKNOWN = set(PROVIDER_FACTORIES) - SUPPORTED_PROVIDERS
if _MISSING or _UNKNOWN:  # pragma: no cover - import-time guard
    raise RuntimeError(
        "Agno provider factory registry is out of sync with kontext-llm's "
        f"model-provider-definitions.json. Missing factories: {sorted(_MISSING)}; "
        f"unknown kinds: {sorted(_UNKNOWN)}."
    )


def get_provider_factory(provider: str) -> ModelFactory | None:
    return PROVIDER_FACTORIES.get(provider)


__all__ = [
    "PROVIDER_FACTORIES",
    "ModelFactory",
    "ModelRequest",
    "get_provider_factory",
]
