"""
Base class for schema profilers using DuckDB with local storage support.

Uses DuckDB for in-memory schema analysis of local files.
"""

import os
import tempfile
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import duckdb

from kontext.common.constants import QueryConstants

from .models import ProfilerParameters, SchemaProfilingError

if TYPE_CHECKING:
    from .models import SchemaProfilingResult


def _default_temp_directory() -> str:
    """Resolve the directory DuckDB may spill to when memory is exhausted."""
    configured = os.environ.get("KONTEXT_DUCKDB_TEMP_DIR")
    if configured:
        os.makedirs(configured, exist_ok=True)
        return configured
    return tempfile.gettempdir()


def get_duckdb_config() -> dict:
    """Same resource guards as the query engine (see engine/session/duckdb_utils)."""
    config: dict[str, str] = {}
    ext_dir = os.environ.get("KONTEXT_EXTENSIONS_DIR")
    if ext_dir and os.path.exists(ext_dir):
        config["extension_directory"] = ext_dir
    config.setdefault("memory_limit", QueryConstants.DUCKDB_MEMORY_LIMIT)
    config.setdefault("threads", str(QueryConstants.DUCKDB_MAX_THREADS))
    config.setdefault("temp_directory", _default_temp_directory())
    return config


def configure_duckdb_engine(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(f"SET threads={QueryConstants.DUCKDB_MAX_THREADS}")
    connection.execute(f"SET memory_limit='{QueryConstants.DUCKDB_MEMORY_LIMIT}'")
    temp_dir = _default_temp_directory().replace("'", "''")
    connection.execute(f"SET temp_directory='{temp_dir}'")


class SchemaProfilerBase(ABC):
    """Base abstract class for schema profiling files via DuckDB.

    Supports local filesystem paths.
    """

    # Threshold for distinct values to consider a column as categorical
    # (low cardinality) for which we collect top values. Typically used for
    # indexing sample values in vector databases.
    CATEGORICAL_THRESHOLD = 50

    # Max number of top values to collect for categorical columns
    TOP_VALUES_LIMIT = 10

    # Max number of raw sample values to collect for any column
    SAMPLES_LIMIT = 5

    def __init__(self, params: ProfilerParameters):
        self.uri = params.uri
        self.file_type = params.file_type
        self.file_name = params.file_name or params.uri.split("/")[-1]
        self.file_size_bytes = params.file_size_bytes
        self.project_id = params.project_id
        self._connection: duckdb.DuckDBPyConnection | None = None

    def __enter__(self):
        self._initialize_duckdb()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._connection:
            self._connection.close()
            self._connection = None

    def _initialize_duckdb(self) -> None:
        """Initialize DuckDB for local file access."""
        try:
            self._connection = duckdb.connect(":memory:", config=get_duckdb_config())
            configure_duckdb_engine(self._connection)
        except Exception as e:
            raise SchemaProfilingError(
                f"Failed to initialize DuckDB: {e!s}",
                file_path=self.uri,
                original_error=e,
            ) from e

    @property
    def storage_path(self) -> str:
        """Get the full storage path for the file."""
        return self.uri

    @abstractmethod
    def profile(self) -> "SchemaProfilingResult":
        pass
