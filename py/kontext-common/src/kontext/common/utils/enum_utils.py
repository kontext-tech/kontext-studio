from __future__ import annotations

from enum import Enum
from typing import Any, overload

"""Enum utilities for safe conversion and manipulation."""


def enum_value(value: object | None) -> str | None:
    """Return the string value of a string enum (or plain string), else ``None``.

    Accepts a ``str``, a ``str``-valued ``Enum`` member (whose ``.value`` is a
    string), or ``None``. Anything else yields ``None`` so callers can treat a
    missing/unexpected value uniformly.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    member_value = getattr(value, "value", None)
    return member_value if isinstance(member_value, str) else None


@overload
def safe_enum_conversion[T: Enum](enum_class: type[T], value: Any, default: T) -> T: ...


@overload
def safe_enum_conversion[T: Enum](enum_class: type[T], value: Any, default: None) -> T | None: ...


def safe_enum_conversion[T: Enum](enum_class: type[T], value: Any, default: T | None) -> T | None:
    """Safely convert a string value to an enum, returning default on failure.

    Args:
        enum_class: The Enum class to convert to.
        value: The value to convert.
        default: The default value to return if conversion fails.

    Returns:
        The converted Enum member or the default value.
    """
    if value is None:
        return default

    try:
        # Try finding by value first (standard for str, Enum)
        return enum_class(value)
    except ValueError:
        try:
            # Try finding by name (fallback)
            return enum_class[str(value)]
        except (ValueError, KeyError):
            return default
