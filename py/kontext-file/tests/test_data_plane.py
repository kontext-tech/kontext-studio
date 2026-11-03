"""Unit tests for the columnar data-plane primitives (no database/storage needed)."""

from __future__ import annotations

from kontext.file.data_plane import (
    DataTablePayload,
    data_table_fingerprint,
    parquet_fingerprint,
    read_parquet_slice,
    result_row_count,
)
from kontext.schema import DataColumn, DataTable


def _table(rows: list[list[object]]) -> DataTable:
    return DataTable(
        columns=[DataColumn(name="a", type="VARCHAR"), DataColumn(name="b", type="BIGINT")],
        rows=rows,
        row_count=len(rows),
    )


def test_payload_round_trips_through_parquet():
    payload = DataTablePayload.from_table(_table([["x", 1], [None, 2]]))

    assert result_row_count(payload.parquet_bytes) == 2
    assert read_parquet_slice(payload.parquet_bytes, offset=0, limit=1) == [["x", 1]]
    assert read_parquet_slice(payload.parquet_bytes, offset=1, limit=None) == [[None, 2]]


def test_payload_zero_column_table_is_valid():
    payload = DataTablePayload.from_table(DataTable(columns=[], rows=[], row_count=0))
    assert result_row_count(payload.parquet_bytes) == 0


def test_fingerprint_is_content_addressed_and_value_sensitive():
    first = data_table_fingerprint(_table([["x", 1]]))
    same = data_table_fingerprint(_table([["x", 1]]))
    different = data_table_fingerprint(_table([["x", 2]]))

    assert first == same
    assert first != different


def test_payload_fingerprint_matches_parquet_bytes():
    """All materialization paths share one content-addressed key: the bytes."""
    payload = DataTablePayload.from_table(_table([["x", 1]]))

    assert payload.fingerprint == parquet_fingerprint(payload.parquet_bytes)


def test_slice_beyond_rows_returns_empty():
    payload = DataTablePayload.from_table(_table([["x", 1]]))
    assert read_parquet_slice(payload.parquet_bytes, offset=5, limit=10) == []


def test_parquet_is_readable_by_duckdb():
    """The row store must be queryable by DuckDB (enables session reuse)."""
    import duckdb

    payload = DataTablePayload.from_table(_table([["x", 1], ["y", 2]]))

    import tempfile
    from pathlib import Path

    path = Path(tempfile.mkdtemp()) / "store.parquet"
    path.write_bytes(payload.parquet_bytes)

    rows = (
        duckdb.connect().execute(f"SELECT a, b FROM read_parquet('{path}') ORDER BY b").fetchall()
    )
    assert rows == [("x", 1), ("y", 2)]
