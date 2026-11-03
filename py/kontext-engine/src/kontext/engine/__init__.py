"""Concrete in-process compute implementations.

This package owns the query execution engines (DuckDB, live SQL). It depends
only on compute contracts and ``kontext-query``'s engine-resolution seam,
never on query orchestration internals.
"""

from .adapters import LocalChatSessionService, LocalJobRunService

__all__ = [
    "LocalChatSessionService",
    "LocalJobRunService",
]
