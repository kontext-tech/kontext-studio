"""Mistral provider factory (native Mistral client)."""

from __future__ import annotations

from typing import Any

from .base import ModelRequest


def create_mistral_model(request: ModelRequest) -> Any:
    try:
        from agno.models.mistral import MistralChat
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"Mistral provider requires additional dependencies: {exc}") from exc

    kwargs: dict[str, Any] = {
        "id": request.model_id,
        "api_key": request.api_key() or "not-set",
        **request.token_kwarg(),
    }
    base_url = request.base_url()
    if base_url:
        kwargs["endpoint"] = base_url
    return MistralChat(**kwargs)
