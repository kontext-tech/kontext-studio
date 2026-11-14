"""Execution-owned job-run management helpers."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from kontext.common import BadRequestError, NotFoundError
from kontext.common.jobs.trigger_actor import system_actor, user_actor
from kontext.common.messaging import IQueueClient
from kontext.data import JobRunDataService, JobRunLogDataService
from kontext.schema import (
    AddJobRunLogRequest,
    JobResetResponse,
    JobRunLogModel,
    JobRunModel,
    JobRunStatus,
    JobTriggerType,
    LogLevel,
    PaginatedListOfJobRunModel,
    ResetJobRunsRequest,
    TriggerActorModel,
    UpdateJobRunProgressRequest,
    UpdateJobRunStatusRequest,
    UpdateJobRunWorkerRequest,
)

from .job_run_dispatch import (
    create_queued_job_run_and_maybe_dispatch,
    dispatch_job_run_if_configured,
)
from .job_run_summary import enrich_job_run_display_summary
from .workflows import WorkflowOrchestrationService

logger = logging.getLogger(__name__)

RESETTABLE_STATUSES = {
    JobRunStatus.FAILED,
    JobRunStatus.CANCELED,
    JobRunStatus.TIMEDOUT,
    JobRunStatus.DEADLETTERED,
    JobRunStatus.RUNNING,
    JobRunStatus.DISPATCHED,
}


def get_project_name(auth_context: Any) -> str | None:
    """Safely extract a project name from an auth context."""
    project = getattr(auth_context, "project", None)
    project_name = getattr(project, "project_name", None)
    return str(project_name) if project_name else None


def get_request_actor(auth_context: Any) -> TriggerActorModel:
    """Resolve the best available structured actor for audit and trigger metadata."""
    try:
        trigger_actor = getattr(auth_context, "trigger_actor", None)
    except Exception:  # pragma: no cover - defensive against context accessors
        trigger_actor = None

    if isinstance(trigger_actor, TriggerActorModel):
        return trigger_actor

    actor_label = getattr(auth_context, "actor_label", None)

    user = getattr(auth_context, "user", None)
    user_id = getattr(user, "id", None)

    try:
        auth_user_id = getattr(auth_context, "user_id", None)
    except Exception:  # pragma: no cover - defensive against context accessors
        auth_user_id = None

    resolved_user_id = user_id or auth_user_id
    if resolved_user_id:
        return user_actor(str(resolved_user_id))

    if actor_label:
        return system_actor(str(actor_label))

    return system_actor()


async def get_job_run_resource_service(*, run_id: UUID, auth_context: Any) -> JobRunModel | None:
    """Fetch a job run resource for authorization checks."""
    run_service = JobRunDataService(auth_context.project_id)
    return await run_service.get_run_by_id_async(run_id)


async def list_job_runs_service(
    *,
    project_id: UUID,
    page_index: int,
    page_size: int,
    job_id: UUID | None,
    status: str | None,
    auth_context: Any,
) -> PaginatedListOfJobRunModel:
    run_service = JobRunDataService(project_id, project_name=get_project_name(auth_context))
    result = await run_service.get_runs_paginated_async(
        page_index=page_index,
        page_size=page_size,
        job_id=job_id,
        status=status,
        owner_id=auth_context.effective_owner_id,
    )
    for run in result.items or []:
        enrich_job_run_display_summary(run)
    return result


def get_job_run_service(
    *,
    run_id: UUID,
    auth_context: Any,
) -> JobRunModel:
    if not auth_context.resource:
        raise NotFoundError(f"Job run {run_id} not found")

    return enrich_job_run_display_summary(auth_context.resource)


async def get_job_run_logs_service(
    *,
    run_id: UUID,
    limit: int,
    auth_context: Any,
) -> list[JobRunLogModel]:
    if not auth_context.resource:
        raise NotFoundError(f"Job run {run_id} not found")

    log_service = JobRunLogDataService(auth_context.project_id)
    return await log_service.get_logs_for_run_async(job_run_id=run_id, limit=limit)


async def update_job_run_status_service(
    *,
    run_id: UUID,
    request: UpdateJobRunStatusRequest,
    auth_context: Any,
    queue_client: IQueueClient | None = None,
) -> None:
    if not auth_context.resource:
        raise NotFoundError(f"Job run {run_id} not found")

    run_service = JobRunDataService(auth_context.project_id)
    result_data_json = json.dumps(request.result_data) if request.result_data else None
    await run_service.update_status_async(
        run_id,
        status=request.status.value,
        error_message=request.error_message,
        result_data=result_data_json,
    )
    if request.status in {
        JobRunStatus.SUCCEEDED,
        JobRunStatus.FAILED,
        JobRunStatus.CANCELED,
        JobRunStatus.TIMEDOUT,
        JobRunStatus.DEADLETTERED,
    }:
        await WorkflowOrchestrationService().handle_run_status_change_async(
            project_id=auth_context.project_id,
            run_id=run_id,
            queue_client=queue_client,
        )


async def update_job_run_progress_service(
    *,
    run_id: UUID,
    request: UpdateJobRunProgressRequest,
    auth_context: Any,
) -> None:
    if not auth_context.resource:
        raise NotFoundError(f"Job run {run_id} not found")

    if not 0 <= request.progress <= 100:
        raise BadRequestError(f"Progress must be between 0 and 100, got {request.progress}")

    run_service = JobRunDataService(auth_context.project_id)
    await run_service.update_progress_async(run_id, progress=request.progress)


async def update_job_run_worker_service(
    *,
    run_id: UUID,
    request: UpdateJobRunWorkerRequest,
    auth_context: Any,
) -> None:
    if not auth_context.resource:
        raise NotFoundError(f"Job run {run_id} not found")

    run_service = JobRunDataService(auth_context.project_id)
    await run_service.update_worker_async(run_id, worker=request.worker)


async def add_job_run_log_service(
    *,
    run_id: UUID,
    request: AddJobRunLogRequest,
    auth_context: Any,
) -> None:
    if not auth_context.resource:
        raise NotFoundError(f"Job run {run_id} not found")

    if not request.message or not request.message.strip():
        raise BadRequestError("Log message cannot be empty")

    log_service = JobRunLogDataService(auth_context.project_id)
    data_json = json.dumps(request.data) if request.data else None
    await log_service.add_log_async(
        job_run_id=run_id,
        level=request.level,
        message=request.message,
        data=data_json,
    )


async def reset_job_runs_service(
    *,
    request: ResetJobRunsRequest,
    project_id: UUID,
    auth_context: Any,
    queue_client: IQueueClient | None,
) -> JobResetResponse:
    logger.info(
        "Reset job runs request received: project_id=%s, job_run_ids=%s, reason=%s",
        project_id,
        request.job_run_ids,
        request.reason,
    )

    run_service = JobRunDataService(project_id, project_name=get_project_name(auth_context))
    log_service = JobRunLogDataService(project_id)
    request_actor = get_request_actor(auth_context)

    reset_count = 0
    dispatched_count = 0

    for run_id_str in request.job_run_ids:
        try:
            run_id = UUID(run_id_str)
        except ValueError:
            logger.warning("Invalid job run ID format: %s", run_id_str)
            continue

        job_run = await run_service.get_run_by_id_async(
            run_id, include_job=True, include_trigger=False
        )
        if not job_run:
            logger.warning("Job run %s not found for reset", run_id)
            continue

        if job_run.status not in RESETTABLE_STATUSES:
            logger.warning("Cannot reset job run %s with status %s", run_id, job_run.status)
            continue

        if not job_run.job_id:
            logger.warning("Job run %s has no job_id, cannot reset", run_id)
            continue

        try:
            trigger_config = json.dumps({"OriginalJobRunId": str(run_id)})
            job_type = job_run.job.type if job_run.job and job_run.job.type else "unknown"
            job_name = job_run.job.name if job_run.job and job_run.job.name else "Unknown Job"
            timeout_seconds = job_run.job.timeout if job_run.job else 300
            new_job_run, dispatched = await create_queued_job_run_and_maybe_dispatch(
                project_id=project_id,
                queue_client=None,
                job_id=job_run.job_id,
                parameters=job_run.parameters,
                job_type=job_type,
                job_name=job_name,
                timeout_seconds=timeout_seconds,
                triggered_by=request_actor,
                trigger_type=JobTriggerType.RETRY,
                trigger_configuration=trigger_config,
                attempt_count=(job_run.attempt_count or 0) + 1,
            )
            if not new_job_run.id:
                logger.error("New job run has no ID, cannot proceed")
                continue

            dispatch_run_id = UUID(new_job_run.id)
            reset_count += 1

            await log_service.add_log_async(
                job_run_id=run_id,
                level=LogLevel.INFORMATION,
                message=(
                    f"Job run manually reset. New retry attempt created: "
                    f"{dispatch_run_id}. Reason: {request.reason}"
                ),
            )
            await log_service.add_log_async(
                job_run_id=dispatch_run_id,
                level=LogLevel.INFORMATION,
                message=(f"Job run started as retry of {run_id}. Reason: {request.reason}"),
                data=json.dumps(
                    {
                        "previousJobRunId": str(run_id),
                        "previousStatus": (job_run.status.value if job_run.status else None),
                        "reason": request.reason,
                    }
                ),
            )
            await WorkflowOrchestrationService().rebind_step_retry_async(
                project_id=project_id,
                previous_run_id=run_id,
                new_run_id=dispatch_run_id,
                requested_by=request_actor,
                reason=request.reason,
            )
            dispatched = await dispatch_job_run_if_configured(
                queue_client=queue_client,
                project_id=project_id,
                job_run_id=dispatch_run_id,
                job_type=job_type,
                job_name=job_name,
                timeout_seconds=timeout_seconds,
                parameters=job_run.parameters,
            )
        except Exception as create_error:
            logger.error("Failed to create retry run for %s: %s", run_id, create_error)
            continue

        if dispatched:
            dispatched_count += 1
        else:
            logger.info(
                "Queue client not available, reset job run %s will be picked up "
                "locally if a worker is running",
                dispatch_run_id,
            )

    message = f"Successfully reset {reset_count} job run(s)"
    if dispatched_count > 0:
        message += f", {dispatched_count} dispatched to queue"
    elif reset_count > 0:
        message += " (queue unavailable - jobs not dispatched)"

    return JobResetResponse(reset_count=reset_count, message=message)


__all__ = [
    "add_job_run_log_service",
    "get_job_run_logs_service",
    "get_job_run_resource_service",
    "get_job_run_service",
    "list_job_runs_service",
    "reset_job_runs_service",
    "update_job_run_progress_service",
    "update_job_run_status_service",
    "update_job_run_worker_service",
]
