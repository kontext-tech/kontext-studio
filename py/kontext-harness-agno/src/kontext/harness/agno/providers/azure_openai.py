"""Microsoft Azure OpenAI provider factory."""

from __future__ import annotations

import os
from typing import Any

from kontext.llm.provider_definitions import get_api_version_env_var

from .base import ModelRequest


def create_azure_openai_model(request: ModelRequest) -> Any:
    """Azure OpenAI deployment.

    ``model_id`` is the Azure deployment name. The endpoint and API version
    come from the connection config, then their env vars.
    """
    try:
        from agno.models.azure import AzureOpenAI
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Azure OpenAI provider requires additional dependencies: "
            f"{exc}. Install with `pip install openai`."
        ) from exc

    resolved = request.resolved_config
    api_version_var = get_api_version_env_var(request.provider) or "OPENAI_API_VERSION"
    azure_endpoint = request.base_url() or os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = (resolved.api_version if resolved else None) or os.getenv(api_version_var)

    kwargs: dict[str, Any] = {
        "id": request.model_id,
        "api_key": request.api_key() or "not-set",
        **request.token_kwarg(),
    }
    if azure_endpoint:
        kwargs["azure_endpoint"] = azure_endpoint
    if api_version:
        kwargs["api_version"] = api_version
    return AzureOpenAI(**kwargs)
