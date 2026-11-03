"""OpenAI provider factory (native OpenAI API)."""

from __future__ import annotations

from typing import Any

from .base import ModelRequest


def create_openai_model(request: ModelRequest) -> Any:
    try:
        from agno.models.openai import OpenAIChat
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"OpenAI provider requires additional dependencies: {exc}") from exc

    kwargs: dict[str, Any] = {
        "id": request.model_id,
        "api_key": request.api_key() or "not-set",
        **request.token_kwarg(),
        **request.reasoning_kwargs(),
    }
    base_url = request.base_url()
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAIChat(**kwargs)
