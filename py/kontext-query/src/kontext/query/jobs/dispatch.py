"""Job-dispatch helpers for query-owned jobs."""

from __future__ import annotations

import logging
from uuid import UUID

from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.common.messaging import IQueueClient
from kontext.jobs.job_run_dispatch import create_job_run_and_maybe_dispatch
from kontext.schema import (
    JobTriggerType,
    TriggerActorModel,
)

from .cleanup_session_job import CleanupSessionJob, CleanupSessionParams

logger = logging.getLogger(__name__)


async def dispatch_cleanup_session_job(
    queue_client: IQueueClient,
    project_id: UUID,
    session_ids: list[UUID],
    *,
    triggered_by: TriggerActorModel | None = None,
    owner_id: UUID | None = None,
) -> None:
    """Dispatch cleanup-session jobs for multiple sessions."""
    triggered_by_label = format_trigger_actor(triggered_by) or "System"

    for session_id in session_ids:
        try:
            params = CleanupSessionParams(
                session_id=str(session_id),
                project_id=str(project_id),
            )

            job_run, _dispatched = await create_job_run_and_maybe_dispatch(
                project_id=project_id,
                queue_client=queue_client,
                owner_id=owner_id,
                job_class=CleanupSessionJob,
                job_params=params,
                triggered_by=triggered_by,
                trigger_type=JobTriggerType.INTERACTIVE,
                created_by=triggered_by_label,
                timeout_minutes=1,
                priority=5,
            )
            logger.info(
                "Dispatched cleanup job %s for session %s",
                str(job_run.id),
                session_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to dispatch cleanup job for session %s: %s",
                session_id,
                exc,
            )
