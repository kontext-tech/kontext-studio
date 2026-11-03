"""Anthropic provider factory."""

from __future__ import annotations

from typing import Any

from .base import ModelRequest


def create_anthropic_model(request: ModelRequest) -> Any:
    try:
        from agno.models.anthropic import Claude
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"Anthropic provider requires additional dependencies: {exc}") from exc

    return Claude(
        id=request.model_id,
        api_key=request.api_key() or "not-set",
        **request.token_kwarg(),
    )
