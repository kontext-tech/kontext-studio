"""Utility functions for handling tool results, serialization, and side-loading."""

import json
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


def tool_result_to_str(
    result: Any,
    exclude_none: bool = True,
) -> str:
    """
    Convert a tool result to a JSON string representation for LLM communication.

    Args:
        result: The result object (Pydantic model or string)
        exclude_none: Whether to exclude None values from the output

    Returns:
        String representation of the result
    """
    if isinstance(result, str):
        return result

    if not isinstance(result, BaseModel):
        try:
            return json.dumps(result, ensure_ascii=False)
        except Exception:
            return str(result)

    # Always use camelCase aliases for tool results to match platform schemas
    # Prefer to_dict() if available as it handles model-specific serialization logic (like preserving required Nulls)
    to_dict_method = getattr(result, "to_dict", None)
    if callable(to_dict_method):
        try:
            data = to_dict_method()
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"Failed to use to_dict for tool result validation/serialization: {e}")
            # Fallback to standard Pydantic serialization below

    try:
        return result.model_dump_json(by_alias=True, indent=None, exclude_none=exclude_none)
    except Exception as e:
        logger.warning(f"Failed to use model_dump_json for tool result serialization: {e}")
        try:
            data = result.model_dump(mode="json", by_alias=True, exclude_none=exclude_none)
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception as inner:
            logger.warning(
                f"Failed to use model_dump fallback for tool result serialization: {inner}"
            )
            return str(result)
