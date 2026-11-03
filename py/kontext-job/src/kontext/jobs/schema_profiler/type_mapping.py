"""Centralized type mapping from DuckDB types to Kontext ColumnDataType."""

from kontext.schema import ColumnDataType


def map_duckdb_type_to_column_data_type(duckdb_type: str) -> ColumnDataType:
    """Map DuckDB data type string to ColumnDataType enum.

    Args:
        duckdb_type: The type string returned by DuckDB (e.g., from DESCRIBE).

    Returns:
        The corresponding ColumnDataType enum value.
    """
    type_mapping = {
        "INTEGER": ColumnDataType.INTEGER,
        "BIGINT": ColumnDataType.BIGINT,
        "SMALLINT": ColumnDataType.SMALLINT,
        "TINYINT": ColumnDataType.TINYINT,
        "HUGEINT": ColumnDataType.HUGEINT,
        "UINTEGER": ColumnDataType.UINTEGER,
        "UBIGINT": ColumnDataType.UBIGINT,
        "USMALLINT": ColumnDataType.USMALLINT,
        "UTINYINT": ColumnDataType.UTINYINT,
        "UHUGEINT": ColumnDataType.UHUGEINT,
        "FLOAT": ColumnDataType.FLOAT,
        "DOUBLE": ColumnDataType.DOUBLE,
        "REAL": ColumnDataType.REAL,
        "DECIMAL": ColumnDataType.DECIMAL,
        "NUMERIC": ColumnDataType.NUMERIC,
        "VARCHAR": ColumnDataType.VARCHAR,
        "CHAR": ColumnDataType.CHAR,
        "TEXT": ColumnDataType.TEXT,
        "STRING": ColumnDataType.STRING,
        "BOOLEAN": ColumnDataType.BOOLEAN,
        "BOOL": ColumnDataType.BOOLEAN,
        "DATE": ColumnDataType.DATE,
        "TIME": ColumnDataType.TIME,
        "TIMESTAMP": ColumnDataType.TIMESTAMP,
        "TIMESTAMPTZ": ColumnDataType.TIMESTAMPTZ,
        "TIMESTAMP_S": ColumnDataType.TIMESTAMP,
        "TIMESTAMP_MS": ColumnDataType.TIMESTAMP,
        "TIMESTAMP_NS": ColumnDataType.TIMESTAMP,
        "UUID": ColumnDataType.UUID,
        "JSON": ColumnDataType.JSON,
        "BLOB": ColumnDataType.BLOB,
        "BYTEA": ColumnDataType.BLOB,
        "BIT": ColumnDataType.BIT,
        "BITSTRING": ColumnDataType.BITSTRING,
    }

    normalized_type = duckdb_type.upper().strip()

    # Handle complex types like DECIMAL(18,2) or VARCHAR(255)
    base_type = normalized_type.split("(")[0]

    return type_mapping.get(base_type, ColumnDataType.UNKNOWN)


def is_numeric_type(duckdb_type: str) -> bool:
    """Check if a DuckDB type is numeric."""
    numeric_types = {
        "INTEGER",
        "BIGINT",
        "SMALLINT",
        "TINYINT",
        "HUGEINT",
        "UINTEGER",
        "UBIGINT",
        "USMALLINT",
        "UTINYINT",
        "UHUGEINT",
        "FLOAT",
        "DOUBLE",
        "REAL",
        "DECIMAL",
        "NUMERIC",
    }
    base_type = duckdb_type.upper().strip().split("(")[0]
    return base_type in numeric_types


def is_text_type(duckdb_type: str) -> bool:
    """Check if a DuckDB type is text-based."""
    text_types = {"VARCHAR", "CHAR", "TEXT", "STRING"}
    base_type = duckdb_type.upper().strip().split("(")[0]
    return base_type in text_types
