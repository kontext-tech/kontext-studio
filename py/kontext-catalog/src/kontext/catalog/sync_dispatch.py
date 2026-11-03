"""Queued dispatch helpers for catalog-owned background sync work."""

from __future__ import annotations

import logging
from uuid import UUID

from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.common.messaging import IQueueClient
from kontext.common.project_scoped import ProjectScopedService
from kontext.data import CatalogDataService
from kontext.execution.scheduling import create_queued_job_run_and_maybe_dispatch
from kontext.jobs.service import JobService
from kontext.schema import CatalogConnection, CatalogConnectionKind, TriggerActorModel

from .jobs import ExternalCatalogInitialSyncJob

logger = logging.getLogger(__name__)


class CatalogSyncDispatchService(ProjectScopedService):
    """Dispatches catalog-owned background sync jobs."""

    def __init__(
        self,
        *,
        project_id: UUID | str,
        queue_client: IQueueClient | None = None,
    ) -> None:
        super().__init__(project_id)
        self._queue_client = queue_client
        self._catalog_data_service = CatalogDataService(project_id)

    async def queue_initial_sync(
        self,
        connection: CatalogConnection,
        *,
        triggered_by: TriggerActorModel | None,
    ) -> bool:
        """Create a queued job run for an external connection initial sync."""
        if not connection.id or connection.connection_kind != CatalogConnectionKind.EXTERNAL:
            return False

        job_metadata = ExternalCatalogInitialSyncJob.get_job_metadata()
        job_service = JobService(project_id=self.project_id)
        job_entity = await job_service.ensure_job_exists_async(
            job_type=job_metadata.type,
            name=job_metadata.name or "External Catalog Initial Sync",
            description=job_metadata.description,
            timeout=300,
            created_by=format_trigger_actor(triggered_by),
        )
        if not job_entity or not job_entity.id:
            logger.warning("Could not find or create job definition for external catalog sync")
            return False

        await self._catalog_data_service.update_sync_status_async(
            connection.id,
            status="queued",
            error_message=None,
        )
        try:
            await create_queued_job_run_and_maybe_dispatch(
                project_id=self.project_id,
                queue_client=self._queue_client,
                job_id=job_entity.id,
                parameters={"connection_id": connection.id},
                job_type=job_metadata.type,
                job_name=job_entity.name or job_metadata.name or job_metadata.type,
                timeout_seconds=job_entity.timeout,
                triggered_by=triggered_by,
                priority=5,
            )
        except Exception as exc:
            logger.exception(
                "Failed to create queued run for external catalog sync %s",
                connection.id,
            )
            await self._catalog_data_service.update_sync_status_async(
                connection.id,
                status="failed",
                error_message=f"Failed to queue initial sync: {exc}",
            )
            return False
        return True
