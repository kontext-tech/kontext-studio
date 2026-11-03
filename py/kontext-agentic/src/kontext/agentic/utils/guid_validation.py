"""GUID validation utilities for AI tools.

This module provides utilities for validating GUID/UUID format in tool parameters.
GUIDs must follow the format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (8-4-4-4-12 hexadecimal digits).
"""

import re
from collections.abc import Callable
from functools import wraps
from inspect import signature
from typing import TypeVar

# GUID pattern: 8-4-4-4-12 hexadecimal characters with dashes
GUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

T = TypeVar("T", bound=Callable)


def validate_guid(guid: str, param_name: str = "ID") -> None:
    """
    Validate a GUID string format without normalization.

    This function validates that a string matches the standard GUID format.
    It does not normalize or fix malformed GUIDs - validation is strict to
    surface issues at the source (e.g., LLM formatting problems).

    Args:
        guid: The GUID string to validate
        param_name: Name of the parameter for error messages (e.g., "notebook_id")

    Raises:
        ValueError: If the GUID format is invalid, with a detailed error message

    Example:
        >>> validate_guid("1eb96811-39fe-47a4-7e25-08de0be1d149", "notebook_id")
        # Passes validation

        >>> validate_guid("1eb96811-39fe-47a4-08de0be1d149", "notebook_id")
        ValueError: Invalid notebook_id format...
    """
    if not GUID_PATTERN.match(guid):
        # Calculate expected vs actual character count for better error messages
        guid_without_dashes = guid.replace("-", "")
        expected_hex_chars = 32
        actual_hex_chars = len(guid_without_dashes)

        error_parts = [
            f"Invalid {param_name} format: '{guid}'.",
            "Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (8-4-4-4-12 hexadecimal digits).",
        ]

        if actual_hex_chars != expected_hex_chars:
            error_parts.append(
                f"Expected {expected_hex_chars} hex characters, got {actual_hex_chars}."
            )

        error_parts.append("Example: '1eb96811-39fe-47a4-7e25-08de0be1d149'")

        raise ValueError(" ".join(error_parts))


def validate_guids(*param_names: str) -> Callable[[T], T]:
    """
    Decorator to validate GUID format for specified parameters.

    This decorator validates that string parameters matching the specified names
    are properly formatted GUIDs before the function executes. It supports both
    synchronous and asynchronous functions.

    Args:
        *param_names: Names of parameters to validate as GUIDs

    Returns:
        Decorator function that wraps the target function with GUID validation

    Example:
        >>> @validate_guids("notebook_id", "project_id")
        ... async def add_data_table(self, notebook_id: str, project_id: str, ...):
        ...     # notebook_id and project_id are validated before method executes
        ...     ...

        >>> @validate_guids("block_id")
        ... async def delete_block(self, notebook_id: str, block_id: str):
        ...     # Only block_id is validated
        ...     ...

    Raises:
        ValueError: If any specified parameter has an invalid GUID format

    Notes:
        - None values are allowed and not validated (for optional parameters)
        - Non-string values are skipped (no validation)
        - Validation errors include the parameter name and expected format
        - Works with both positional and keyword arguments
    """

    def decorator(func: T) -> T:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get function signature to map args to param names
            sig = signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Validate each specified parameter
            for param_name in param_names:
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    # Only validate if value is a non-None string
                    if value is not None and isinstance(value, str):
                        validate_guid(value, param_name)

            # Call original function
            return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get function signature to map args to param names
            sig = signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Validate each specified parameter
            for param_name in param_names:
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    # Only validate if value is a non-None string
                    if value is not None and isinstance(value, str):
                        validate_guid(value, param_name)

            # Call original function
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator
