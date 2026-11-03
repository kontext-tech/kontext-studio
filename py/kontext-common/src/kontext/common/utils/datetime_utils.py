"""
Datetime utilities for consistent ISO 8601 UTC formatting.

All datetime strings are formatted with the 'Z' suffix for UTC timezone,
which is required by the platform's schema validation. Datetime strings
include microsecond precision (e.g., '2025-11-30T08:56:09.123456Z').
"""

from __future__ import annotations

from datetime import UTC, datetime


def normalize_datetime_utc(dt: datetime | None) -> datetime | None:
    """Normalize a datetime to UTC while preserving null values.

    Args:
        dt: The datetime to normalize.

    Returns:
        A timezone-aware UTC datetime, or None if ``dt`` is None.
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)

    return dt.astimezone(UTC)


def utc_now() -> datetime:
    """Get current UTC datetime with microsecond precision.

    Returns:
        Current UTC datetime with microseconds.
    """
    return datetime.now(UTC)


def format_datetime_utc(dt: datetime) -> str:
    """Format a datetime as ISO 8601 string with UTC timezone and 'Z' suffix.

    Args:
        dt: The datetime to format.

    Returns:
        ISO 8601 formatted string with microseconds
        (e.g., '2025-11-30T08:56:09.123456Z').

    Notes:
        - If dt is naive (no timezone), assumes UTC.
        - If dt has a timezone, converts to UTC.
        - Includes microsecond precision for proper log ordering.
    """
    normalized_dt = normalize_datetime_utc(dt)
    if normalized_dt is None:
        raise ValueError("dt must not be None")
    return normalized_dt.isoformat().replace("+00:00", "Z")


def utc_now_iso() -> str:
    """Get the current UTC time as an ISO 8601 string with 'Z' suffix.

    Returns:
        Current UTC time as ISO 8601 string with microseconds
        (e.g., '2025-11-30T08:56:09.123456Z').
    """
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
