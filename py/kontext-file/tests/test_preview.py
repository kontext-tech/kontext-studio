"""Unit tests for adaptive preview sizing."""

from __future__ import annotations

from kontext.file.data_plane.preview import (
    MAX_PREVIEW_ROWS,
    MIN_PREVIEW_ROWS,
    build_preview,
    preview_row_budget,
)
from kontext.schema import DataColumn, DataTable


def test_row_budget_shrinks_as_columns_grow():
    narrow = preview_row_budget(2)
    wide = preview_row_budget(50)

    assert narrow > wide
    assert MIN_PREVIEW_ROWS <= wide <= narrow <= MAX_PREVIEW_ROWS


def test_row_budget_is_capped_and_floored():
    assert preview_row_budget(0) == MAX_PREVIEW_ROWS
    assert preview_row_budget(1_000_000) == MIN_PREVIEW_ROWS


def test_build_preview_bounds_rows_and_preserves_metadata():
    table = DataTable(
        columns=[DataColumn(name="a", type="VARCHAR"), DataColumn(name="b", type="BIGINT")],
        rows=[[str(i), i] for i in range(500)],
        row_count=500,
    )

    preview = build_preview(table)

    assert len(preview.rows or []) < 500
    assert preview.row_count == 500
    assert preview.columns == table.columns


def test_build_preview_keeps_small_tables_intact():
    table = DataTable(
        columns=[DataColumn(name="a", type="VARCHAR")],
        rows=[["x"], ["y"]],
        row_count=2,
    )

    assert build_preview(table).rows == [["x"], ["y"]]
