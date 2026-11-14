"""Internal helpers for creating queued job runs and optional dispatch."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.common.messaging import IQueueClient
from kontext.data import JobRunDataService
from kontext.jobs import build_job_execution_message
from kontext.schema import JobRunModel, JobTriggerType, TriggerActorModel

logger = logging.getLogger(__name__)


def _normalize_parameters(
    parameters: str | dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any]]:
    """Return parameters as both JSON text and a dict for dispatch messages."""
    if parameters is None:
        return None, {}

    if isinstance(parameters, str):
        try:
            parsed = json.loads(parameters)
        except json.JSONDecodeError:
            return parameters, {}
        return parameters, parsed if isinstance(parsed, dict) else {}

    return json.dumps(parameters), parameters


async def dispatch_job_run_if_configured(
    *,
    queue_client: IQueueClient | None,
    project_id: UUID | str,
    job_run_id: UUID | str,
    job_type: str,
    job_name: str,
    timeout_seconds: int | None,
    parameters: str | dict[str, Any] | None,
    priority: int = 5,
) -> bool:
    """Dispatch a queued job run when an external queue transport is available."""
    if queue_client is None:
        return False

    _, parameter_map = _normalize_parameters(parameters)
    timeout_minutes = max(1, (timeout_seconds or 300) // 60)
    message = build_job_execution_message(
        job_run_id=UUID(str(job_run_id)),
        project_id=UUID(str(project_id)),
        job_type=job_type,
        job_name=job_name,
        timeout_minutes=timeout_minutes,
        parameters=parameter_map,
        priority=priority,
    )
    await queue_client.send_message(message.to_json())
    logger.info(
        "Dispatched queued job run %s for %s via external queue transport",
        job_run_id,
        job_type,
    )
    return True


async def create_queued_job_run_and_maybe_dispatch(
    *,
    project_id: UUID | str,
    queue_client: IQueueClient | None,
    job_id: UUID | str,
    parameters: str | dict[str, Any] | None,
    job_type: str,
    job_name: str,
    timeout_seconds: int | None,
    triggered_by: TriggerActorModel | None,
    trigger_id: UUID | str | None = None,
    trigger_type: JobTriggerType = JobTriggerType.MANUAL,
    trigger_configuration: str | None = None,
    attempt_count: int = 0,
    execution_id: str | None = None,
    priority: int = 5,
) -> tuple[JobRunModel, bool]:
    """Create a queued job run, then dispatch it when a queue transport exists."""
    run_service = JobRunDataService(project_id=project_id)
    parameters_json, _ = _normalize_parameters(parameters)
    job_run = await run_service.create_run_async(
        job_id=job_id,
        parameters=parameters_json,
        trigger_id=trigger_id,
        status="Queued",
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        trigger_configuration=trigger_configuration,
        attempt_count=attempt_count,
        execution_id=execution_id,
    )

    if not job_run.id:
        raise ValueError(f"Created queued job run for {job_type} has no ID")

    dispatched = await dispatch_job_run_if_configured(
        queue_client=queue_client,
        project_id=project_id,
        job_run_id=job_run.id,
        job_type=job_type,
        job_name=job_name,
        timeout_seconds=timeout_seconds,
        parameters=parameters_json,
        priority=priority,
    )

    if not dispatched:
        logger.info(
            "Created queued job run %s for %s; dispatch deferred to local embedded worker",
            job_run.id,
            job_type,
        )

    return job_run, dispatched


async def create_job_run_and_maybe_dispatch(
    *,
    project_id: UUID | str,
    queue_client: IQueueClient | None,
    owner_id: UUID | str | None,
    job_class: Any,
    job_params: Any,
    triggered_by: TriggerActorModel | None,
    trigger_type: JobTriggerType = JobTriggerType.MANUAL,
    timeout_minutes: int,
    priority: int = 5,
    created_by: str | None = None,
    on_run_created: Any = None,
) -> tuple[JobRunModel, bool]:
    """Create the job (if needed), a queued run, and dispatch it.

    The choreography every domain dispatcher repeated: resolve the job row for
    the owner, create a queued run with JSON parameters, let the caller link
    the run to domain state (via ``on_run_created``) while it is still queued,
    then dispatch when a queue transport exists.

    ``job_class`` must expose ``get_job_metadata()``; ``job_params`` is a
    Pydantic model or plain dict serialized with camelCase aliases.
    """
    from collections.abc import Awaitable

    from kontext.data import JobDataService
    from kontext.jobs.dispatch import build_job_execution_message
    from kontext.schema import CreateJobRequest, JobRetryStrategy

    metadata = job_class.get_job_metadata()
    label = created_by or (format_trigger_actor(triggered_by) if triggered_by else "System")
    job_service = JobDataService(project_id)
    job = await job_service.get_or_create_job_for_owner_async(
        job_type=metadata.type,
        owner_id=owner_id,
        request=CreateJobRequest(
            name=metadata.name,
            type=metadata.type,
            description=metadata.description,
            timeout=timeout_minutes * 60,
            is_enabled=True,
            retry_strategy=JobRetryStrategy.NONE,
            retry_limit=0,
        ),
        created_by=label,
    )

    parameters = (
        job_params.model_dump(mode="json", by_alias=True)
        if hasattr(job_params, "model_dump")
        else job_params
    )
    parameters_json, _ = _normalize_parameters(parameters)
    run_service = JobRunDataService(project_id)
    job_run = await run_service.create_run_async(
        job_id=UUID(str(job.id)),
        parameters=parameters_json,
        status="Queued",
        triggered_by=triggered_by,
        trigger_type=trigger_type,
    )
    job_run_id = UUID(str(job_run.id))

    if on_run_created is not None:
        result = on_run_created(job_run)
        if isinstance(result, Awaitable):
            await result

    if queue_client is not None:
        message = build_job_execution_message(
            job_run_id=job_run_id,
            project_id=project_id,
            job_class=job_class,
            params=job_params,
            timeout_minutes=timeout_minutes,
            priority=priority,
        )
        await queue_client.send_message(message.to_json())
        logger.info(
            "Dispatched queued job run %s for %s via external queue transport",
            job_run_id,
            metadata.type,
        )
        return job_run, True

    logger.info(
        "Created queued job run %s for %s; dispatch deferred to local embedded worker",
        job_run_id,
        metadata.type,
    )
    return job_run, False


async def handle_run_status_change_hook(project_id: UUID | str, run_id: UUID | str) -> None:
    """Composition hook for run-status side effects (workflow orchestration).

    Engine adapters and worker transports receive this callable instead of
    importing the execution orchestration layer directly.
    """
    from kontext.jobs.workflows import WorkflowOrchestrationService

    await WorkflowOrchestrationService().handle_run_status_change_async(
        project_id=UUID(str(project_id)),
        run_id=UUID(str(run_id)),
        queue_client=None,
    )
