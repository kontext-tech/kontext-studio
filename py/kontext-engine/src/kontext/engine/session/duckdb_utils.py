"""
DuckDB utility functions for query engine management.
"""

import os
import tempfile

import duckdb

from kontext.common.constants import QueryConstants


def _default_temp_directory() -> str:
    """Resolve the directory DuckDB may spill to when memory is exhausted."""
    configured = os.environ.get("KONTEXT_DUCKDB_TEMP_DIR")
    if configured:
        os.makedirs(configured, exist_ok=True)
        return configured
    return tempfile.gettempdir()


def get_duckdb_config() -> dict:
    """
    Get the recommended DuckDB configuration dictionary for connections.

    Includes:
    - extension_directory from KONTEXT_EXTENSIONS_DIR
    - memory_limit / threads / temp_directory resource guards
    """
    config: dict[str, str] = {}

    # Set extension directory if configured via environment
    ext_dir = os.environ.get("KONTEXT_EXTENSIONS_DIR")
    if ext_dir and os.path.exists(ext_dir):
        config["extension_directory"] = ext_dir

    # Bound memory and allow disk spilling so a single query cannot exhaust
    # the host. These are connection-level and can be overridden per call site.
    config.setdefault("memory_limit", QueryConstants.DUCKDB_MEMORY_LIMIT)
    config.setdefault("threads", str(QueryConstants.DUCKDB_MAX_THREADS))
    config.setdefault("temp_directory", _default_temp_directory())

    return config


def configure_duckdb_engine(connection: duckdb.DuckDBPyConnection) -> None:
    """
    Apply common configuration settings to a DuckDB connection.

    Handles:
    - Setting default thread count
    - Bounding memory usage and configuring a spill directory
    """
    connection.execute(f"SET threads={QueryConstants.DUCKDB_MAX_THREADS}")
    connection.execute(f"SET memory_limit='{QueryConstants.DUCKDB_MEMORY_LIMIT}'")
    temp_dir = _default_temp_directory().replace("'", "''")
    connection.execute(f"SET temp_directory='{temp_dir}'")
