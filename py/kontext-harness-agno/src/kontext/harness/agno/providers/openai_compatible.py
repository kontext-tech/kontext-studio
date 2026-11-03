"""Generic OpenAI-compatible endpoint provider factory."""

from __future__ import annotations

from typing import Any

from kontext.llm.provider_resolution import get_provider_display_name

from .base import ModelRequest


def create_openai_compatible_model(request: ModelRequest) -> Any:
    try:
        from agno.models.openai.like import OpenAILike
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            f"{request.provider} provider requires additional dependencies: {exc}"
        ) from exc

    return OpenAILike(
        id=request.model_id,
        provider=get_provider_display_name(request.provider),
        base_url=request.base_url(),
        api_key=request.api_key() or ("ollama" if request.provider == "ollama" else "not-set"),
        **request.token_kwarg(),
        **request.reasoning_kwargs(),
    )
