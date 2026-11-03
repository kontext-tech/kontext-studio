"""Columnar data-plane primitives for materialized query results.

Turns a :class:`~kontext.schema.DataTable` into a content-addressed Parquet row
store and back. The file service is the only writer/reader; this package just
owns the encoding and the pure helpers. Parquet is used (over Arrow IPC) so the
store is directly readable by DuckDB via ``read_parquet``.
"""

from .payload import (
    DataTablePayload,
    data_table_fingerprint,
    parquet_fingerprint,
    read_parquet_slice,
    result_row_count,
)

__all__ = [
    "DataTablePayload",
    "data_table_fingerprint",
    "parquet_fingerprint",
    "read_parquet_slice",
    "result_row_count",
]
