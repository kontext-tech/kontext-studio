"""Bounded, adaptive previews for data tables.

A preview is what gets embedded in a ``.dt`` descriptor (and shown to the
model), so it must stay small regardless of result size. Rather than a fixed
row count, the budget is a *cell* budget: a table with many narrow columns can
afford more sample rows than one with a few very wide columns.
"""

from __future__ import annotations

from kontext.schema import DataTable

__all__ = ["build_preview", "preview_row_budget"]

# Upper bounds for an embedded preview. ``DEFAULT_PREVIEW_CELLS`` is the total
# number of values (rows x columns) kept; ``MAX_PREVIEW_ROWS`` caps how many
# rows that translates to so a two-column table does not embed hundreds of rows.
DEFAULT_PREVIEW_CELLS = 200
MAX_PREVIEW_ROWS = 25
MIN_PREVIEW_ROWS = 1


def preview_row_budget(column_count: int, *, cell_limit: int = DEFAULT_PREVIEW_CELLS) -> int:
    """Return how many sample rows fit in the cell budget for ``column_count``."""
    if column_count <= 0:
        return MAX_PREVIEW_ROWS
    rows_by_cells = max(MIN_PREVIEW_ROWS, cell_limit // column_count)
    return max(MIN_PREVIEW_ROWS, min(MAX_PREVIEW_ROWS, rows_by_cells))


def build_preview(
    table: DataTable,
    *,
    cell_limit: int = DEFAULT_PREVIEW_CELLS,
) -> DataTable:
    """Return a bounded preview preserving schema and total row count."""
    columns = table.columns or []
    rows = table.rows or []
    total = table.row_count if table.row_count is not None else len(rows)
    limit = preview_row_budget(len(columns), cell_limit=cell_limit)

    return DataTable(
        columns=columns,
        rows=rows[:limit],
        row_count=total,
    )
