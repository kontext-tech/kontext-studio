"""Data profiling contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from kontext.schema import FileSchemaModel, FileStatsModel


@dataclass(frozen=True)
class DataProfilingResult:
    """Full result of a profiling pass — both schema and statistics."""

    file_stats: FileStatsModel | None = None
    """Statistical summary (row counts, null %, column distributions)."""

    file_schema: FileSchemaModel | None = None
    """Structural schema (column names, types, nullability)."""

    error_message: str | None = None
    """Set when profiling failed; both ``file_stats`` and ``file_schema`` will be
    None."""

    @property
    def success(self) -> bool:
        return self.error_message is None and self.file_stats is not None


class IDataProfilingProtocol(Protocol):
    """Protocol defining the interface for data profiling operations.

    Abstracts the compute engine (DuckDB server-side, etc.)
    so that callers — jobs and agents alike — remain fully environment-agnostic.
    """

    async def profile_file(self, project_id: str, file_id: str) -> FileStatsModel | None:
        """Profile a single file by its ID and return statistical metadata.

        The adapter is responsible for resolving the file URI and routing to
        the appropriate compute backend (cloud DuckDB, etc.).
        Returns ``None`` when profiling is unsupported in the current environment.
        """
        ...

    async def profile_file_full(self, project_id: str, file_id: str) -> DataProfilingResult:
        """Profile a single file returning both schema and statistics.

        Server-side adapters return ``file_schema`` and ``file_stats``.
        On failure, the result has ``error_message`` set.
        """
        ...

    async def profile_files(
        self, project_id: str, file_ids: list[str]
    ) -> dict[str, FileStatsModel | None]:
        """Profile multiple files, returning a mapping of file_id → FileStatsModel.

        Files that fail to profile will have ``None`` as their value rather than
        raising, so callers can continue processing the remaining files.
        """
        ...

    async def profile_files_full(
        self, project_id: str, file_ids: list[str]
    ) -> dict[str, DataProfilingResult]:
        """Profile multiple files returning both schema and statistics.

        Server-side adapters return ``file_schema`` and ``file_stats``.
        On per-file failure the result has ``error_message`` set and both
        data fields as ``None`` — callers should not raise on individual failures.
        """
        ...
