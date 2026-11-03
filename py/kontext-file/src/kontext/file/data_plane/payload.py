"""Columnar row store for materialized data tables.

The physical encoding is Parquet: columnar, compressed, and — unlike Arrow IPC —
directly readable by DuckDB via ``read_parquet``. That last property is what
lets a materialized result be reused natively inside a query session instead of
being parsed from JSON in Python.

This module owns only the encoding/decoding helpers; persisting and reading is
the file service's job, so there is no second place that can drift from the
canonical write path.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from kontext.schema import DataTable

__all__ = [
    "DataTablePayload",
    "data_table_fingerprint",
    "parquet_fingerprint",
    "read_parquet_slice",
    "result_row_count",
]


def parquet_fingerprint(parquet_bytes: bytes) -> str:
    """Return the content hash used to name the row store for these bytes.

    This is the single content-addressed key used by every materialization
    path: query results encode a table and hash the bytes, and
    ``kontext.save_table`` hashes the bytes the kernel already encoded. One
    definition keeps dedupe and storage naming consistent across producers.
    """
    return hashlib.sha256(parquet_bytes).hexdigest()


def data_table_fingerprint(table: DataTable) -> str:
    """Return the content hash for a table's canonical Parquet encoding.

    Delegates to :func:`parquet_fingerprint` so callers that hold a table and
    callers that already have Parquet bytes share one key space.
    """
    return parquet_fingerprint(_encode_parquet(table))


@dataclass(frozen=True)
class DataTablePayload:
    """A data table encoded for content-addressed storage.

    ``parquet_bytes`` is the canonical row store; ``fingerprint`` is the
    content hash used as its storage name.
    """

    table: DataTable
    parquet_bytes: bytes
    fingerprint: str

    @classmethod
    def from_table(cls, table: DataTable) -> DataTablePayload:
        """Build a payload, encoding the rows as Parquet in one pass."""
        parquet_bytes = _encode_parquet(table)
        return cls(
            table=table,
            parquet_bytes=parquet_bytes,
            fingerprint=parquet_fingerprint(parquet_bytes),
        )


def _to_arrow_table(table: DataTable):
    import pyarrow as pa

    columns = table.columns or []
    rows = table.rows or []

    if not columns:
        return pa.table({})

    column_names = [column.name for column in columns]
    column_data: dict[str, list[Any]] = {name: [] for name in column_names}
    for row in rows:
        for index, name in enumerate(column_names):
            column_data[name].append(row[index] if index < len(row) else None)

    arrays = [pa.array(column_data[column.name]) for column in columns]
    return pa.Table.from_arrays(arrays, names=column_names)


def _encode_parquet(table: DataTable) -> bytes:
    """Encode a data table as Parquet bytes.

    Parquet infers column types from the values; the declared warehouse type
    string is preserved separately in the ``.dt`` descriptor.
    """
    import io

    import pyarrow.parquet as pq

    buffer = io.BytesIO()
    pq.write_table(_to_arrow_table(table), buffer)
    return buffer.getvalue()


def read_parquet_slice(parquet_bytes: bytes, *, offset: int, limit: int | None) -> list[list[Any]]:
    """Return a window of rows from Parquet bytes."""
    import io

    import pyarrow.parquet as pq

    table = pq.read_table(io.BytesIO(parquet_bytes))
    if offset:
        table = table.slice(offset, limit if limit is not None else None)
    elif limit is not None:
        table = table.slice(0, limit)

    columns = [column.to_pylist() for column in table.columns]
    return [[columns[col][row] for col in range(len(columns))] for row in range(table.num_rows)]


def result_row_count(parquet_bytes: bytes) -> int:
    """Return the total number of rows in Parquet bytes."""
    import io

    import pyarrow.parquet as pq

    return pq.read_metadata(io.BytesIO(parquet_bytes)).num_rows
