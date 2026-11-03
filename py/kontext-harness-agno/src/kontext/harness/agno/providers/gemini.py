"""Google Gemini and Vertex AI provider factories."""

from __future__ import annotations

import os
from typing import Any

from kontext.llm.provider_definitions import (
    get_project_id_env_var,
    get_region_env_var,
)

from ..gemini_model import KontextGemini
from .base import ModelRequest


def create_gemini_model(request: ModelRequest) -> Any:
    """Google AI Studio Gemini, using a Google AI API key."""
    return KontextGemini(
        id=request.model_id,
        api_key=request.api_key(),
        **request.token_kwarg("max_output_tokens"),
    )


def create_google_vertex_model(request: ModelRequest) -> Any:
    """Google Vertex AI / Gemini Enterprise via project + location + ADC.

    Vertex accepts Application Default Credentials or a Google Cloud API key;
    the Agno ``Gemini`` model reads project/location itself.
    """
    resolved = request.resolved_config
    project_var = get_project_id_env_var(request.provider) or "GOOGLE_CLOUD_PROJECT"
    region_var = get_region_env_var(request.provider) or "GOOGLE_CLOUD_LOCATION"
    project_id = (resolved.project_id if resolved else None) or os.getenv(project_var)
    location = (resolved.location if resolved else None) or os.getenv(region_var)

    return KontextGemini(
        id=request.model_id,
        vertexai=True,
        project_id=project_id,
        location=location,
        api_key=request.api_key(),
        **request.token_kwarg("max_output_tokens"),
    )
