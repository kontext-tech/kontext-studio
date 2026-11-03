"""SQL utility functions for DuckDB and other SQL engines."""

import uuid


def escape_sql_literal(value: str) -> str:
    """Escape a string literal for use in a SQL query.

    DuckDB uses single quotes for string literals and escapes them by doubling.
    """
    if value is None:
        return "NULL"
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def quote_identifier(name: str) -> str:
    """Quote a SQL identifier (table name, column name, etc.).

    DuckDB uses double quotes for identifiers and escapes them by doubling.
    """
    if not name:
        return '""'
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def generate_temp_view_name(prefix: str = "temp_view") -> str:
    """Generate a unique temporary view name to avoid collisions."""
    unique_id = uuid.uuid4().hex[:8]
    return f"{prefix}_{unique_id}"


def parse_describe_nullability(nullability_str: str | None) -> bool:
    """Parse nullability string from DuckDB DESCRIBE output.

    DuckDB DESCRIBE returns 'YES' or 'NO' for nullability.
    """
    if nullability_str is None:
        return True
    return nullability_str.upper() in ("YES", "Y", "TRUE", "T", "1")
