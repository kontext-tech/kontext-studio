"""OpenRouter provider factory."""

from __future__ import annotations

from typing import Any

from .base import ModelRequest


def create_openrouter_model(request: ModelRequest) -> Any:
    try:
        from agno.models.openrouter import OpenRouter
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"OpenRouter provider requires additional dependencies: {exc}") from exc

    kwargs: dict[str, Any] = {
        "id": request.model_id,
        "api_key": request.api_key() or "not-set",
        **request.token_kwarg(),
        **request.reasoning_kwargs(),
    }
    base_url = request.base_url()
    if base_url:
        kwargs["base_url"] = base_url
    return OpenRouter(**kwargs)
