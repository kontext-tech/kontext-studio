"""Ollama provider factories (local and Ollama Cloud)."""

from __future__ import annotations

from typing import Any

from .base import ModelRequest


def _token_options(request: ModelRequest) -> dict[str, Any]:
    """Ollama controls generation length through ``options["num_predict"]``."""
    if request.max_tokens is None:
        return {}
    return {"options": {"num_predict": request.max_tokens}}


def create_ollama_model(request: ModelRequest) -> Any:
    """Local Ollama via its native client (keyless on localhost)."""
    try:
        from agno.models.ollama import Ollama
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"Ollama provider requires additional dependencies: {exc}") from exc

    return Ollama(
        id=request.model_id,
        host=request.base_url(),
        api_key=request.api_key(),
        **_token_options(request),
    )


def create_ollama_cloud_model(request: ModelRequest) -> Any:
    """Ollama Cloud via the native client, authenticated with an API key."""
    try:
        from agno.models.ollama import Ollama
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            f"Ollama Cloud provider requires additional dependencies: {exc}"
        ) from exc

    return Ollama(
        id=request.model_id,
        host=request.base_url() or "https://ollama.com",
        api_key=request.api_key(),
        **_token_options(request),
    )
