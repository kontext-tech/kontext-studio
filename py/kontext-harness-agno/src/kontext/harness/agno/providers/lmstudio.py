"""LM Studio provider factory (OpenAI-compatible local server)."""

from __future__ import annotations

from typing import Any

from .base import ModelRequest


def create_lm_studio_model(request: ModelRequest) -> Any:
    try:
        from agno.models.lmstudio import LMStudio
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"LM Studio provider requires additional dependencies: {exc}") from exc

    return LMStudio(
        id=request.model_id,
        base_url=request.base_url() or "http://127.0.0.1:1234/v1",
        api_key=request.api_key() or "lm-studio",
        **request.token_kwarg(),
        **request.reasoning_kwargs(),
    )
