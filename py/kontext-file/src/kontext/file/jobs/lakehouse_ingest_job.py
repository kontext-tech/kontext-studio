"""Lakehouse ingest job for uploaded files."""

from __future__ import annotations

from pydantic import Field, field_validator

from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.jobs.permissions import JobRequiredPermissions
from kontext.schema import JobCategory

from ..lakehouse_ingest_models import LakehouseIngestFailure, LakehouseIngestResultData


class LakehouseIngestParams(BaseJobParams):
    """Parameters for ingesting uploaded files into the internal lakehouse."""

    file_ids: str = Field(..., description="Comma-separated list of file IDs to ingest")

    @field_validator("file_ids")
    @classmethod
    def validate_file_ids(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("file_ids cannot be empty")
        file_ids = [item.strip() for item in value.split(",") if item.strip()]
        if not file_ids:
            raise ValueError("At least one file ID is required")
        return value

    def get_file_id_list(self) -> list[str]:
        return [item.strip() for item in self.file_ids.split(",") if item.strip()]


@job(
    job_type="python.jobs.LakehouseIngestJob",
    name="Lakehouse Ingest",
    description="Profiles uploaded files and materializes internal Iceberg tables",
    category=JobCategory.DATAMANAGEMENT,
    params_model=LakehouseIngestParams,
    required_permissions=JobRequiredPermissions.SYSTEM_INTERNAL,
    display_parameter="file_ids",
    is_system_job=True,
    icon="database-sync",
)
class LakehouseIngestJob(BasePythonJob[LakehouseIngestParams]):
    """Profiles files and ingests them into the internal Iceberg lakehouse."""

    async def execute_job(
        self, context: JobContext, parameters: LakehouseIngestParams
    ) -> JobResult:
        project_id = context.project_id
        if not project_id:
            return JobResult.error_result("Project ID is required for lakehouse ingest")

        file_ids = parameters.get_file_id_list()
        runtime_provider = context.get_runtime_provider()
        profiling_service = runtime_provider.get_data_profiling_service()
        if profiling_service is None:
            from kontext.file.profiling import DefaultDataProfilingService

            profiling_service = DefaultDataProfilingService(project_id=project_id)

        file_service = context.get_file_service()
        query_session_service = context.get_query_session_service()
        catalog_service = context.get_catalog_service()

        await context.log_info(
            f"Ingesting {len(file_ids)} file(s) into the lakehouse",
            {"file_ids": file_ids},
        )
        await context.update_progress(5, "Profiling source files")

        successful_ids: list[str] = []
        failed_files: list[LakehouseIngestFailure] = []

        for index, file_id in enumerate(file_ids, start=1):
            try:
                profile_result = await profiling_service.profile_file_full(project_id, file_id)
                if not profile_result.success:
                    raise ValueError(profile_result.error_message or "Profiling returned no schema")

                await file_service.update_file_schema_and_stats(
                    project_id=project_id,
                    file_id=file_id,
                    schema=profile_result.file_schema,
                    statistics=profile_result.file_stats,
                )
                await catalog_service.ingest_file(file_id)
                successful_ids.append(file_id)
                await context.update_progress(
                    min(80, 5 + int(index * 70 / max(len(file_ids), 1))),
                    f"Ingested file {index}/{len(file_ids)}",
                )
            except Exception as exc:
                failed_files.append(LakehouseIngestFailure(file_id=file_id, error=str(exc)))
                await context.log_warning(f"Lakehouse ingest failed for file {file_id}: {exc}")

        connection = await catalog_service.ensure_default_internal_connection()
        connection_id = connection.id or ""
        sync_status = await catalog_service.sync_connection(connection_id)
        if failed_files:
            sync_status.error_message = f"{len(failed_files)} file(s) failed during ingest"
            sync_status.status = "partial"
        invalidated_sessions = (
            await query_session_service.invalidate_sessions_for_catalog_connection(
                project_id,
                connection_id,
                reason="Lakehouse tables changed",
            )
        )

        await context.update_progress(100, "Lakehouse ingest completed")
        result_data = LakehouseIngestResultData(
            connection_id=connection.id,
            successful_file_ids=successful_ids,
            failed_files=failed_files,
            entity_count=sync_status.entity_count,
            invalidated_session_ids=[str(session_id) for session_id in invalidated_sessions],
        ).to_job_result_payload()
        if failed_files:
            return JobResult.error_result(
                f"Lakehouse ingest completed with {len(failed_files)} failure(s)",
                data=result_data,
            )
        return JobResult.success_result(
            f"Successfully ingested {len(successful_ids)} file(s) into the lakehouse",
            data=result_data,
        )
