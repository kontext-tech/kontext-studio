"""Policy for deciding when a query result should be persisted.

This lives in ``kontext-common`` so both the in-process query service and the
queued query job share one rule instead of each re-implementing the
``row_count > threshold`` check. Keeping it pure (no I/O, no engine) means the
decision is unit-testable on its own.
"""

from __future__ import annotations

__all__ = ["should_persist_result"]


def should_persist_result(
    *,
    row_count: int,
    store_as_resource: bool = False,
    threshold_rows: int | None = None,
) -> bool:
    """Return whether a result should be persisted as a materialized artifact.

    A result is persisted when the caller explicitly asked for it, or when its
    row count exceeds the configured threshold (auto-persist large results so
    they never have to be re-run or embedded inline).
    """
    if store_as_resource:
        return True
    if threshold_rows is None:
        return False
    return row_count > threshold_rows
