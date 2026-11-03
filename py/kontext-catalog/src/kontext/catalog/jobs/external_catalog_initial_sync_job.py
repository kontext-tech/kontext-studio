"""Queued job for initial external catalog sync."""

from __future__ import annotations

from pydantic import Field, field_validator

from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.jobs.permissions import JobRequiredPermissions
from kontext.schema import CatalogConnectionKind, JobCategory

from ..connections.management import CatalogManagementService


class ExternalCatalogInitialSyncParams(BaseJobParams):
    """Parameters for syncing an external catalog connection."""

    connection_id: str = Field(..., description="Catalog connection ID to sync")
    project_id: str | None = Field(
        default=None, description="Optional explicit project ID override"
    )

    @field_validator("connection_id")
    @classmethod
    def validate_connection_id(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("connection_id cannot be empty")
        return value


@job(
    job_type="python.jobs.ExternalCatalogInitialSyncJob",
    name="External Catalog Initial Sync",
    description="Validates and syncs an external catalog connection",
    category=JobCategory.DATAMANAGEMENT,
    params_model=ExternalCatalogInitialSyncParams,
    required_permissions=JobRequiredPermissions.SYSTEM_INTERNAL,
    display_parameter="connection_id",
    is_system_job=True,
    icon="database-sync",
)
class ExternalCatalogInitialSyncJob(BasePythonJob[ExternalCatalogInitialSyncParams]):
    """Validates and syncs a queued external catalog connection."""

    async def execute_job(
        self, context: JobContext, parameters: ExternalCatalogInitialSyncParams
    ) -> JobResult:
        project_id = parameters.project_id or context.project_id
        if not project_id:
            return JobResult.error_result("Project ID is required for external catalog sync")

        runtime_provider = context.get_runtime_provider()
        catalog_service = CatalogManagementService(
            project_id=project_id,
            runtime_provider=runtime_provider,
        )
        connection_id = parameters.connection_id
        connection = await catalog_service.data_service.get_connection_async(connection_id)
        if connection is None:
            return JobResult.error_result(
                f"Catalog connection {connection_id} was not found",
                data={"connection_id": connection_id},
            )

        if connection.connection_kind != CatalogConnectionKind.EXTERNAL:
            return JobResult.error_result(
                "Initial external sync can only run for external connections",
                data={"connection_id": connection_id},
            )

        await context.log_info(
            "Starting initial external catalog sync",
            {"connection_id": connection_id},
        )
        await context.update_progress(10, "Validating data source")
        await catalog_service.data_service.update_sync_status_async(
            connection_id,
            status="running",
            error_message=None,
        )

        validation = await catalog_service.validate_connection(connection_id)
        if validation.status != "succeeded":
            error_message = (
                validation.error_message or validation.message or "Connection validation failed."
            )
            await catalog_service.data_service.update_sync_status_async(
                connection_id,
                status="failed",
                error_message=error_message,
            )
            return JobResult.error_result(
                error_message,
                data={
                    "connection_id": connection_id,
                    "validation_status": validation.status,
                },
            )

        await context.update_progress(45, "Syncing metadata")
        sync_status = await catalog_service.sync_connection(connection_id)
        if sync_status.status != "succeeded":
            return JobResult.error_result(
                sync_status.error_message or "Catalog sync failed",
                data={
                    "connection_id": connection_id,
                    "sync_status": sync_status.status,
                },
            )

        await context.update_progress(100, "Data source ready")
        return JobResult.success_result(
            "External catalog connection synced successfully",
            data={
                "connection_id": connection_id,
                "entity_count": sync_status.entity_count,
            },
        )
