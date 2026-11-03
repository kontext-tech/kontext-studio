"""AWS Bedrock provider factory."""

from __future__ import annotations

import os
from typing import Any

from kontext.llm.provider_definitions import get_region_env_var

from .base import ModelRequest


def create_bedrock_model(request: ModelRequest) -> Any:
    try:
        from agno.models.aws.bedrock import AwsBedrock
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(f"Bedrock provider requires additional dependencies: {exc}") from exc

    resolved = request.resolved_config
    credentials = request.credentials
    region_var = get_region_env_var(request.provider) or "BEDROCK_REGION"

    kwargs: dict[str, Any] = {"id": request.model_id, **request.token_kwarg()}
    region = (resolved.region if resolved else None) or (
        os.getenv(region_var) or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    )
    if region:
        kwargs["aws_region"] = region
    if credentials.get("accessKeyId"):
        kwargs["aws_access_key_id"] = credentials["accessKeyId"]
    elif os.getenv("AWS_ACCESS_KEY_ID"):
        kwargs["aws_access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")
    if credentials.get("secretAccessKey"):
        kwargs["aws_secret_access_key"] = credentials["secretAccessKey"]
    elif os.getenv("AWS_SECRET_ACCESS_KEY"):
        kwargs["aws_secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")
    if credentials.get("sessionToken"):
        kwargs["aws_session_token"] = credentials["sessionToken"]
    elif os.getenv("AWS_SESSION_TOKEN"):
        kwargs["aws_session_token"] = os.getenv("AWS_SESSION_TOKEN")
    return AwsBedrock(**kwargs)
