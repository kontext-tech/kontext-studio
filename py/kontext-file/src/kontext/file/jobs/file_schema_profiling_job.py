"""
File Schema Profiling Job

Profiles data files (CSV, Parquet, JSON, JSONL, TSV) to extract schema information
and statistics, then updates the file table with the profiling results.
"""

from uuid import UUID

from pydantic import Field, field_validator

from kontext.auth import FilePermissions, JobPermissions
from kontext.common.constants import DataLakeConstants
from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.schema import FileFormatType, JobCategory


class FileSchemaProfilingParams(BaseJobParams):
    """Parameters for profiling data files to extract schema information."""

    file_ids: str = Field(..., description="Comma-separated list of file IDs to profile")

    @field_validator("file_ids")
    @classmethod
    def validate_file_ids(cls, v: str) -> str:
        """Validate that file_ids is not empty and contains valid entries."""
        if not v or not v.strip():
            raise ValueError("file_ids cannot be empty")

        ids = [fid.strip() for fid in v.split(",") if fid.strip()]
        if not ids:
            raise ValueError("At least one valid file ID must be provided")

        return v

    def get_file_id_list(self) -> list[UUID | str]:
        """Parse and return the list of file IDs."""
        return [fid.strip() for fid in self.file_ids.split(",") if fid.strip()]


@job(
    job_type="python.jobs.FileSchemaProfilingJob",
    name="File Schema Profiling",
    description=(
        "Profiles data files to extract schema information and statistics for data lake queries"
    ),
    category=JobCategory.DATAMANAGEMENT,
    params_model=FileSchemaProfilingParams,
    required_permissions=[
        JobPermissions.EXECUTE,
        FilePermissions.READ,
        FilePermissions.UPDATE,
    ],
    display_parameter="file_ids",
    is_system_job=False,
    icon="database-search",
)
class FileSchemaProfilingJob(BasePythonJob[FileSchemaProfilingParams]):
    """Job for profiling data files to extract schema and statistics."""

    @staticmethod
    def is_supported_file_type(file_type: FileFormatType) -> bool:
        """Check if a file type is supported for profiling."""
        return DataLakeConstants.is_supported_data_file_type(file_type)

    async def execute_job(
        self, context: JobContext, parameters: FileSchemaProfilingParams
    ) -> JobResult:
        """Execute the file schema profiling job."""
        try:
            file_ids = [str(fid) for fid in parameters.get_file_id_list()]

            await context.update_progress(0, "Initializing profiling service...")
            await context.log_info(
                f"Starting file profiling for {len(file_ids)} files: {', '.join(file_ids)}"
            )

            if not context.project_id:
                return JobResult.error_result("Project ID is required for file profiling")

            profiling_service = context.runtime_provider.get_data_profiling_service()
            if profiling_service is None:
                from kontext.file.profiling import DefaultDataProfilingService

                profiling_service = DefaultDataProfilingService(context.project_id)

            return await self._execute_via_service(context, file_ids, profiling_service)
        except Exception as e:
            error_msg = f"File profiling job failed: {e!s}"
            await context.log_error(error_msg)
            return JobResult.error_result(error_msg)

    async def _execute_via_service(
        self, context: JobContext, file_ids: list[str], profiling_service
    ) -> JobResult:
        """Profile files via IDataProfilingProtocol and persist results."""
        file_service = context.get_file_service()
        project_id = context.project_id
        if not project_id:
            return JobResult.error_result("Project ID is required")

        successful_count = 0
        failed_files = []
        total = len(file_ids)

        for i, file_id in enumerate(file_ids):
            progress = int((i / total) * 90)
            await context.update_progress(progress, f"Profiling file {i + 1}/{total}")

            try:
                result = await profiling_service.profile_file_full(project_id, file_id)
            except Exception as exc:
                await context.log_warning(f"Failed to profile file {file_id}: {exc}")
                failed_files.append({"id": file_id, "error": str(exc)})
                continue

            try:
                await file_service.update_file_schema_and_stats(
                    project_id=project_id,
                    file_id=file_id,
                    schema=result.file_schema,
                    statistics=result.file_stats,
                )
            except Exception as exc:
                await context.log_warning(
                    f"Failed to persist profiling result for {file_id}: {exc}"
                )
                failed_files.append({"id": file_id, "error": str(exc)})
                continue

            if result.success:
                successful_count += 1
                await context.log_debug(f"Profiled file {file_id} successfully")
            else:
                await context.log_warning(
                    f"Profiling incomplete for {file_id}: {result.error_message}"
                )
                failed_files.append(
                    {"id": file_id, "error": result.error_message or "Unknown error"}
                )

        await context.update_progress(100, "Profiling completed")
        return self._build_result(context, file_ids, successful_count, failed_files)

    @staticmethod
    def _build_result(
        context: JobContext,
        file_ids: list[str],
        successful_count: int,
        failed_files: list[dict],
    ) -> JobResult:
        _ = context
        max_failed_logs = 20
        failed_summary = failed_files[:max_failed_logs]
        if len(failed_files) > max_failed_logs:
            failed_summary.append(
                {"error": f"Plus {len(failed_files) - max_failed_logs} more failures"}
            )

        result_data = {
            "file_ids": file_ids,
            "total_files": len(file_ids),
            "successful_count": successful_count,
            "failed_count": len(failed_files),
            "failed_files": failed_summary,
        }

        if failed_files:
            message = f"Profiling failed for {len(failed_files)}/{len(file_ids)} files."
            return JobResult.error_result(message, data=result_data)
        return JobResult.success_result(
            f"Successfully profiled all {successful_count} files", result_data
        )
