"""Default data profiling service using DuckDB-backed profilers."""

from __future__ import annotations

import logging
from uuid import UUID

from kontext.common.constants import DataLakeConstants
from kontext.common.protocols import DataProfilingResult, IDataProfilingProtocol
from kontext.jobs.schema_profiler.models import ProfilerParameters
from kontext.jobs.schema_profiler.profilers import create_profiler
from kontext.schema import FileStatsModel
from kontext.storage import get_storage_provider

from ..service import FileService

logger = logging.getLogger(__name__)


class DefaultDataProfilingService(IDataProfilingProtocol):
    """Server-side profiling adapter backed by DuckDB profilers."""

    def __init__(self, project_id: str) -> None:
        self._project_id = str(project_id)

    async def profile_file(self, project_id: str, file_id: str) -> FileStatsModel | None:
        results = await self.profile_files(project_id, [file_id])
        return results.get(file_id)

    async def profile_file_full(self, project_id: str, file_id: str) -> DataProfilingResult:
        results = await self.profile_files_full(project_id, [file_id])
        return results.get(file_id, DataProfilingResult(error_message="File not found"))

    async def profile_files(
        self, project_id: str, file_ids: list[str]
    ) -> dict[str, FileStatsModel | None]:
        full = await self.profile_files_full(project_id, file_ids)
        return {fid: result.file_stats for fid, result in full.items()}

    async def profile_files_full(
        self, project_id: str, file_ids: list[str]
    ) -> dict[str, DataProfilingResult]:
        file_service = FileService(project_id=project_id, storage_provider=get_storage_provider())
        files = await file_service.get_files_by_ids(project_id, file_ids)

        if not files:
            return {fid: DataProfilingResult(error_message="File not found") for fid in file_ids}

        results: dict[str, DataProfilingResult] = {
            fid: DataProfilingResult(error_message="File not found") for fid in file_ids
        }

        for file in files:
            if file.id is None or not file.uri or file.file_type is None:
                continue
            if not DataLakeConstants.is_supported_data_file_type(file.file_type):
                logger.debug(
                    "Skipping unsupported file type %s for file %s",
                    file.file_type,
                    file.id,
                )
                results[str(file.id)] = DataProfilingResult(
                    error_message=f"Unsupported file type: {file.file_type}"
                )
                continue

            try:
                params = ProfilerParameters(
                    uri=file.uri,
                    file_type=file.file_type,
                    file_name=file.name,
                    file_size_bytes=file.size if file.size and file.size > 0 else None,
                    project_id=UUID(str(file.project_id or project_id)),
                )
                with create_profiler(params) as profiler:
                    result = profiler.profile()

                results[str(file.id)] = DataProfilingResult(
                    file_stats=result.file_stats if result.success else None,
                    file_schema=result.file_schema if result.success else None,
                    error_message=result.error_message if not result.success else None,
                )
            except Exception as exc:
                logger.exception("Failed to profile file %s (%s)", file.name, file.id)
                results[str(file.id)] = DataProfilingResult(
                    error_message=f"Profiling failed for {file.name}: {exc!s}"
                )

        return results
