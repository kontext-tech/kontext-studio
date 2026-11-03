"""Lakehouse cleanup job for deleted files."""

from __future__ import annotations

from pydantic import Field

from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.jobs.permissions import JobRequiredPermissions
from kontext.schema import JobCategory


class LakehouseCleanupParams(BaseJobParams):
    """Parameters for deleting lakehouse tables associated with a file."""

    project_id: str = Field(..., description="Project ID")
    file_id: str = Field(..., description="Deleted file ID")
    file_type: str | None = Field(default=None, description="Deleted file type")


@job(
    job_type="python.jobs.LakehouseCleanupJob",
    name="Lakehouse Cleanup",
    description="Removes internal Iceberg tables that were sourced from deleted files",
    category=JobCategory.DATAMANAGEMENT,
    params_model=LakehouseCleanupParams,
    required_permissions=JobRequiredPermissions.SYSTEM_INTERNAL,
    display_parameter="file_id",
    is_system_job=True,
    icon="database-off",
)
class LakehouseCleanupJob(BasePythonJob[LakehouseCleanupParams]):
    """Cleans up lakehouse entities linked to deleted source files."""

    async def execute_job(
        self, context: JobContext, parameters: LakehouseCleanupParams
    ) -> JobResult:
        query_session_service = context.get_query_session_service()
        catalog_service = context.get_catalog_service()

        deleted_entity_ids = await catalog_service.remove_file_entities(parameters.file_id)
        connection = await catalog_service.ensure_default_internal_connection()
        connection_id = connection.id or ""
        remaining_entities = await catalog_service.list_entities(
            connection_id=connection_id or None
        )
        invalidated_sessions = (
            await query_session_service.invalidate_sessions_for_catalog_connection(
                parameters.project_id,
                connection_id,
                reason="Lakehouse tables changed",
            )
        )

        return JobResult.success_result(
            f"Cleaned up {len(deleted_entity_ids)} lakehouse entity link(s)",
            data={
                "deleted_entity_ids": deleted_entity_ids,
                "entity_count": len(remaining_entities),
                "invalidated_session_ids": [str(session_id) for session_id in invalidated_sessions],
            },
        )
