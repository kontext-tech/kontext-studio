"""Utility functions for the Kontext API."""

import logging
from uuid import UUID

from fastapi import HTTPException, Request
from pydantic.alias_generators import to_camel

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str | None:
    """
    Get the real client IP address, considering forwarded headers from load balancers.

    Checks headers in order of priority:
    1. X-Forwarded-For (most common for load balancers)
    2. X-Real-IP
    3. X-Client-IP
    4. Falls back to the connection remote IP
       (will be load balancer IP if no forwarded headers)

    Args:
        request: FastAPI Request object

    Returns:
        The original client IP address or None if not available
    """
    # Check X-Forwarded-For header (most common for load balancers)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The first one is the original client IP
        first_ip = x_forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip

    # Check other forwarded headers as fallback
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip

    x_client_ip = request.headers.get("X-Client-IP")
    if x_client_ip:
        return x_client_ip

    # Fallback to the connection remote IP
    # (will be load balancer IP if no forwarded headers)
    if request.client:
        return request.client.host

    return None


def extract_path_param(request: Request, name: str) -> str | None:
    """
    Extract a path parameter from the request.

    Route path parameters declare a camelCase alias (see
    ``kontext.api.dependencies.params``), so ``request.path_params`` keys are the
    camelCase form. ``name`` is the snake_case Python parameter name; look up
    its camelCase alias first, then fall back to the raw name.
    """
    camel_name = to_camel(name)
    if camel_name != name:
        val = request.path_params.get(camel_name)
        if val is not None:
            return val

    return request.path_params.get(name)


def parse_uuid_param(value: str, param_name: str = "id") -> UUID:
    """Parse a string parameter to UUID with consistent error handling.

    Args:
        value: String value to parse as UUID.
        param_name: Name of the parameter for error messages.

    Returns:
        Parsed UUID.

    Raises:
        HTTPException: 400 if the value is not a valid UUID.
    """
    try:
        return UUID(value)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {param_name}: '{value}' is not a valid UUID",
        ) from e


def ensure_uuid_param(value: str | UUID, param_name: str = "id") -> UUID:
    """Ensure a value is a UUID, parsing if necessary.

    Args:
        value: String or UUID value.
        param_name: Name of the parameter for error messages.

    Returns:
        UUID instance.

    Raises:
        HTTPException: 400 if the string is not a valid UUID.
    """
    if isinstance(value, UUID):
        return value
    return parse_uuid_param(value, param_name)
