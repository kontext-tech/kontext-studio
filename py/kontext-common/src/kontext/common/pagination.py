"""Shared pagination helpers for Kontext Python packages."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PaginatedResult[T]:
    """Paginated result wrapper."""

    items: list[T]
    total_count: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total_count + self.page_size - 1) // self.page_size


def total_pages(total_count: int, page_size: int) -> int:
    """Compute the page count for a result set (never less than one)."""
    return max(1, -(-total_count // page_size)) if page_size > 0 else 1


def page_flags(page_index: int, pages: int) -> tuple[bool, bool]:
    """Return (has_previous_page, has_next_page) for a 1-based page index."""
    return page_index > 1, page_index < pages
