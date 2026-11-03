"""Shared data-layer entity and DTO contracts.

These types are used across all data service implementations
(PostgreSQL, local file-backed, HTTP SDK) and in protocol definitions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FileStats:
    """Simple DTO for file statistics (count & size)."""

    file_count: int
    total_size_in_bytes: int
