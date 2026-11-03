"""Execution run projections over existing job-run persistence."""

from __future__ import annotations

import json
from datetime import UTC
from uuid import UUID

from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.common.messaging import IQueueClient
from kontext.data import (
    ExecutionRunContextDataService,
    JobRunDataService,
    JobRunLogDataService,
)
from kontext.jobs.cancellation import get_cancellation_registry
from kontext.schema import (
    ExecutionEventModel,
    ExecutionLogModel,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    JobRunLogModel,
    JobRunModel,
    JobRunStatus,
    JobTriggerType,
    PaginatedListOfExecutionRunModel,
    TriggerActorModel,
)

from .scheduling import (
    create_queued_job_run_and_maybe_dispatch,
    dispatch_job_run_if_configured,
)
from .workflows import (
    WorkflowOrchestrationService,
    extract_workflow_projection_metadata,
)

_RUN_KIND_QUERY = ExecutionRunKind("query")
_RUN_KIND_SESSION_INIT = ExecutionRunKind("session_init")
_RUN_KIND_JOB = ExecutionRunKind("job")
_RUN_KIND_WORKFLOW = ExecutionRunKind("workflow")
_RUN_KIND_AGENT = ExecutionRunKind("agent")
_RUN_KIND_NOTEBOOK = ExecutionRunKind("notebook")
_RUN_KIND_PROFILING = ExecutionRunKind("profiling")
_RUN_KIND_INDEXING = ExecutionRunKind("indexing")

_NOTEBOOK_PYTHON_JOB_TYPE = "python.jobs.ExecuteNotebookPythonJob"

_RUN_STATUS_QUEUED = ExecutionRunStatus("queued")
_RUN_STATUS_STARTING = ExecutionRunStatus("starting")
_RUN_STATUS_RUNNING = ExecutionRunStatus("running")
_RUN_STATUS_WAITING_INPUT = ExecutionRunStatus("waiting_input")
_RUN_STATUS_SUCCEEDED = ExecutionRunStatus("succeeded")
_RUN_STATUS_FAILED = ExecutionRunStatus("failed")
_RUN_STATUS_CANCELLED = ExecutionRunStatus("cancelled")
_RUN_STATUS_TIMED_OUT = ExecutionRunStatus("timed_out")

_JOB_KIND_MAP: dict[str, ExecutionRunKind] = {
    "python.jobs.ExecuteQueryJob": _RUN_KIND_QUERY,
    "python.jobs.InitializeSessionJob": _RUN_KIND_SESSION_INIT,
    "python.jobs.CleanupSessionJob": _RUN_KIND_SESSION_INIT,
    "python.jobs.FileSchemaProfilingJob": _RUN_KIND_PROFILING,
    "python.jobs.LakehouseIngestJob": _RUN_KIND_PROFILING,
    "python.jobs.LakehouseCleanupJob": _RUN_KIND_JOB,
    "python.jobs.ExternalCatalogInitialSyncJob": _RUN_KIND_JOB,
    "python.jobs.CatalogIndexingJob": _RUN_KIND_INDEXING,
    "python.jobs.DocumentIndexingJob": _RUN_KIND_INDEXING,
    "python.jobs.ExecutePythonScriptJob": _RUN_KIND_NOTEBOOK,
    "python.jobs.ExecuteNotebookJob": _RUN_KIND_NOTEBOOK,
    "python.jobs.ExecuteNotebookPythonJob": _RUN_KIND_NOTEBOOK,
    "python.jobs.RunAgentJob": _RUN_KIND_AGENT,
}

_JOB_STATUS_MAP: dict[JobRunStatus, ExecutionRunStatus] = {
    JobRunStatus.QUEUED: _RUN_STATUS_QUEUED,
    JobRunStatus.DISPATCHED: _RUN_STATUS_STARTING,
    JobRunStatus.RUNNING: _RUN_STATUS_RUNNING,
    JobRunStatus.SUCCEEDED: _RUN_STATUS_SUCCEEDED,
    JobRunStatus.FAILED: _RUN_STATUS_FAILED,
    JobRunStatus.CANCELED: _RUN_STATUS_CANCELLED,
    JobRunStatus.TIMEDOUT: _RUN_STATUS_TIMED_OUT,
    JobRunStatus.DEADLETTERED: _RUN_STATUS_FAILED,
}

_TERMINAL_STATUSES = {
    _RUN_STATUS_SUCCEEDED,
    _RUN_STATUS_FAILED,
    _RUN_STATUS_CANCELLED,
    _RUN_STATUS_TIMED_OUT,
}

_CANCELLABLE_JOB_STATUSES = {
    JobRunStatus.QUEUED,
    JobRunStatus.DISPATCHED,
    JobRunStatus.RUNNING,
}

_RESETTABLE_JOB_STATUSES = {
    JobRunStatus.FAILED,
    JobRunStatus.CANCELED,
    JobRunStatus.TIMEDOUT,
    JobRunStatus.DEADLETTERED,
    JobRunStatus.RUNNING,
    JobRunStatus.DISPATCHED,
}
_WORKFLOW_ROOT_JOB_TYPE_PREFIX = "python.workflow."


def _parse_json_payload(value: str | None) -> object | str | None:
    if not value:
        return None

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def infer_execution_run_kind(job_run: JobRunModel, *, context=None) -> ExecutionRunKind:
    workflow_projection = extract_workflow_projection_metadata(context)
    if workflow_projection.is_workflow_root:
        return _RUN_KIND_WORKFLOW

    job_type = job_run.job.type if job_run.job else None
    if not job_type:
        return _RUN_KIND_JOB

    if job_type.startswith(_WORKFLOW_ROOT_JOB_TYPE_PREFIX):
        return _RUN_KIND_WORKFLOW

    if job_type in _JOB_KIND_MAP:
        return _JOB_KIND_MAP[job_type]

    normalized = job_type.lower()
    if "agent" in normalized:
        return _RUN_KIND_AGENT
    if "notebook" in normalized or "pythonscript" in normalized:
        return _RUN_KIND_NOTEBOOK

    return _RUN_KIND_JOB


def _is_waiting_for_input(job_run: JobRunModel) -> bool:
    if job_run.status != JobRunStatus.RUNNING:
        return False

    payload = _parse_json_payload(job_run.result_data)
    if isinstance(payload, dict):
        if payload.get("status") == _RUN_STATUS_WAITING_INPUT.value:
            return True
        for key in (
            "is_paused",
            "paused",
            "awaiting_input",
            "waiting_for_input",
            "needs_external_execution",
        ):
            if payload.get(key) is True:
                return True

    error_message = (job_run.error_message or "").lower()
    return "external execution" in error_message or "waiting for input" in error_message


def map_job_run_status(
    status: JobRunStatus, *, job_run: JobRunModel | None = None
) -> ExecutionRunStatus:
    if job_run and _is_waiting_for_input(job_run):
        return _RUN_STATUS_WAITING_INPUT
    return _JOB_STATUS_MAP.get(status, _RUN_STATUS_RUNNING)


def project_execution_run(job_run: JobRunModel, *, context=None) -> ExecutionRunModel:
    workflow_projection = extract_workflow_projection_metadata(context)
    return ExecutionRunModel(
        id=str(job_run.id),
        project_id=job_run.project_id,
        owner_id=job_run.owner_id,
        kind=infer_execution_run_kind(job_run, context=context),
        status=map_job_run_status(job_run.status, job_run=job_run),
        name=job_run.job.name if job_run.job else None,
        progress=job_run.progress,
        created_at=job_run.created_at,
        started_at=job_run.started_at,
        completed_at=job_run.completed_at,
        error_message=job_run.error_message,
        result_data=_parse_json_payload(job_run.result_data),
        source_job_run_id=str(job_run.id),
        root_run_id=(
            str(context.root_run_id)
            if context is not None and context.root_run_id is not None
            else None
        ),
        parent_run_id=(
            str(context.parent_run_id)
            if context is not None and context.parent_run_id is not None
            else None
        ),
        workflow_key=workflow_projection.workflow_key,
        step_key=workflow_projection.step_key,
        is_workflow_root=workflow_projection.is_workflow_root,
    )


def project_execution_log(
    log: JobRunLogModel,
    *,
    requested_run_id: str | None = None,
    context=None,
) -> ExecutionLogModel:
    workflow_projection = extract_workflow_projection_metadata(context)
    source_run_id = str(log.job_run_id)
    return ExecutionLogModel(
        id=str(log.id),
        run_id=requested_run_id or source_run_id,
        timestamp=log.timestamp,
        level=log.level,
        message=log.message,
        data=_parse_json_payload(log.data),
        source_run_id=source_run_id,
        root_run_id=(
            str(context.root_run_id)
            if context is not None and context.root_run_id is not None
            else None
        ),
        parent_run_id=(
            str(context.parent_run_id)
            if context is not None and context.parent_run_id is not None
            else None
        ),
        workflow_key=workflow_projection.workflow_key,
        step_key=workflow_projection.step_key,
    )


def build_status_event(run: ExecutionRunModel) -> ExecutionEventModel:
    timestamp = run.completed_at or run.started_at or run.created_at
    event_type = "run.completed" if run.status in _TERMINAL_STATUSES else "run.status_changed"
    message = run.error_message if run.status == _RUN_STATUS_FAILED else None

    return ExecutionEventModel(
        id=f"{run.id}:{run.status.value}",
        run_id=run.id,
        event_type=event_type,
        timestamp=timestamp,
        status=run.status,
        message=message,
        data={"kind": run.kind.value},
    )


def build_log_event(log: ExecutionLogModel) -> ExecutionEventModel:
    return ExecutionEventModel(
        id=f"log:{log.id}",
        run_id=log.run_id,
        event_type="run.log_appended",
        timestamp=log.timestamp,
        message=log.message,
        data=log.data,
        log=log,
    )


class ExecutionRunService:
    """Thin application service that projects job runs into execution runs."""

    async def list_runs_async(
        self,
        *,
        project_id: UUID,
        page_index: int = 1,
        page_size: int = 20,
        owner_id: UUID | None = None,
        status: str | None = None,
    ) -> PaginatedListOfExecutionRunModel:
        run_service = JobRunDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)
        paged = await run_service.get_runs_paginated_async(
            page_index=page_index,
            page_size=page_size,
            owner_id=owner_id,
            status=status,
        )
        run_ids = [UUID(str(item.id)) for item in paged.items if item.id]
        contexts_by_run_id = await context_service.get_by_run_ids_async(run_ids)
        return PaginatedListOfExecutionRunModel(
            items=[
                project_execution_run(
                    item,
                    context=(contexts_by_run_id.get(UUID(str(item.id))) if item.id else None),
                )
                for item in paged.items
            ],
            total_count=paged.total_count,
            page_index=paged.page_index,
            page_size=paged.page_size,
            total_pages=paged.total_pages,
        )

    async def list_recent_notebook_python_runs_async(
        self,
        *,
        project_id: UUID,
        notebook_id: str,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        """Recent managed notebook Python executions targeting a notebook.

        Recent job runs are filtered by the notebook Python job type and the
        persisted run parameters (``NotebookId`` case-insensitively keyed);
        returns compact records so tools can discover execution-run IDs for a
        notebook without relying on ids being relayed in member prose.
        """
        run_service = JobRunDataService(project_id)
        matches: list[dict[str, object]] = []
        page_index = 1
        page_size = 50
        max_pages = 5
        while len(matches) < limit and page_index <= max_pages:
            paged = await run_service.get_runs_paginated_async(
                page_index=page_index,
                page_size=page_size,
            )
            for item in paged.items:
                job_type = getattr(item.job, "type", None) if item.job else None
                if job_type != _NOTEBOOK_PYTHON_JOB_TYPE:
                    continue
                params = _parse_json_payload(item.parameters)
                params = params if isinstance(params, dict) else {}
                params_notebook = str(params.get("notebook_id") or params.get("NotebookId") or "")
                if params_notebook != notebook_id:
                    continue
                matches.append(
                    {
                        "runId": str(item.id),
                        "blockId": str(params.get("block_id") or params.get("BlockId") or ""),
                        "chatSessionId": (
                            params.get("chat_session_id") or params.get("ChatSessionId")
                        ),
                        "status": map_job_run_status(item.status, job_run=item).value,
                        "createdAt": (item.created_at.isoformat() if item.created_at else None),
                    }
                )
                if len(matches) >= limit:
                    break
            if len(paged.items) < page_size:
                break
            page_index += 1
        return matches

    async def get_run_async(
        self, *, project_id: UUID, run_id: UUID, include_job: bool = True
    ) -> ExecutionRunModel | None:
        run_service = JobRunDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)
        job_run = await run_service.get_run_by_id_async(
            run_id, include_job=include_job, include_trigger=False
        )
        if not job_run:
            return None

        run_context = await context_service.get_by_run_id_async(run_id)
        return project_execution_run(job_run, context=run_context)

    async def get_logs_async(
        self, *, project_id: UUID, run_id: UUID, limit: int = 100
    ) -> list[ExecutionLogModel]:
        log_service = JobRunLogDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)
        run_context = await context_service.get_by_run_id_async(run_id)
        workflow_projection = extract_workflow_projection_metadata(run_context)

        if workflow_projection.is_workflow_root:
            contexts = await context_service.list_by_root_run_id_async(run_id)
            contexts_by_run_id = {UUID(str(context.run_id)): context for context in contexts}
            run_ids = list(contexts_by_run_id.keys())
            logs = await log_service.get_logs_for_run_ids_async(run_ids, limit=limit)
            return [
                project_execution_log(
                    log,
                    requested_run_id=str(run_id),
                    context=contexts_by_run_id.get(UUID(str(log.job_run_id))),
                )
                for log in reversed(logs)
            ]

        logs = await log_service.get_logs_for_run_async(job_run_id=run_id, limit=limit)
        return [project_execution_log(log, context=run_context) for log in reversed(logs)]

    async def get_events_snapshot_async(
        self, *, project_id: UUID, run_id: UUID, limit: int = 100
    ) -> list[ExecutionEventModel]:
        run = await self.get_run_async(project_id=project_id, run_id=run_id)
        if not run:
            return []

        logs = await self.get_logs_async(
            project_id=project_id,
            run_id=run_id,
            limit=limit,
        )
        events = [build_status_event(run), *[build_log_event(log) for log in logs]]
        events.sort(key=lambda event: event.timestamp.astimezone(UTC))
        return events

    async def cancel_run_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        requested_by: TriggerActorModel,
        reason: str | None = None,
    ) -> ExecutionRunModel | None:
        run_service = JobRunDataService(project_id)
        log_service = JobRunLogDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)

        job_run = await run_service.get_run_by_id_async(
            run_id, include_job=True, include_trigger=False
        )
        if not job_run:
            return None

        if job_run.status not in _CANCELLABLE_JOB_STATUSES:
            raise ValueError(f"Run {run_id} cannot be cancelled from status {job_run.status}")

        # Signal any in-process execution so jobs that observe cancellation can
        # stop promptly. A no-op when the run executes in another process.
        get_cancellation_registry().request_cancel(str(run_id))

        # Force-terminate a kernel process owned by this process for this run,
        # so a runaway script stops immediately rather than at the next
        # cooperative checkpoint. Process-local: a run executed by the worker is
        # cancelled via the persisted status, not this call. Imported locally to
        # avoid an import cycle at module load.
        from kontext.kernel.run_registry import terminate_running_kernel

        terminate_running_kernel(str(run_id))

        run_context = await context_service.get_by_run_id_async(run_id)
        workflow_projection = extract_workflow_projection_metadata(run_context)
        if workflow_projection.is_workflow_root:
            await WorkflowOrchestrationService().cancel_workflow_async(
                project_id=project_id,
                root_run_id=run_id,
                requested_by=requested_by,
                reason=reason,
            )
            return await self.get_run_async(project_id=project_id, run_id=run_id)

        message = reason or f"Cancelled by {format_trigger_actor(requested_by)}"
        await run_service.update_status_async(
            run_id,
            status=JobRunStatus.CANCELED.value,
            error_message=message,
        )
        await log_service.add_log_async(
            job_run_id=run_id,
            message=f"Execution run cancelled by {format_trigger_actor(requested_by)}",
            data=json.dumps({"reason": reason} if reason else {"reason": None}),
        )
        await WorkflowOrchestrationService().handle_run_status_change_async(
            project_id=project_id,
            run_id=run_id,
            queue_client=None,
        )

        updated = await run_service.get_run_by_id_async(
            run_id, include_job=True, include_trigger=False
        )
        if not updated:
            return None

        updated_context = await context_service.get_by_run_id_async(run_id)
        return project_execution_run(updated, context=updated_context)

    async def retry_run_async(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
        requested_by: TriggerActorModel,
        reason: str,
        queue_client: IQueueClient,
    ) -> ExecutionRunModel | None:
        run_service = JobRunDataService(project_id)
        log_service = JobRunLogDataService(project_id)
        context_service = ExecutionRunContextDataService(project_id)

        job_run = await run_service.get_run_by_id_async(
            run_id, include_job=True, include_trigger=False
        )
        if not job_run:
            return None

        if job_run.status not in _RESETTABLE_JOB_STATUSES:
            raise ValueError(f"Run {run_id} cannot be retried from status {job_run.status}")

        run_context = await context_service.get_by_run_id_async(run_id)
        workflow_projection = extract_workflow_projection_metadata(run_context)
        workflow_service = WorkflowOrchestrationService()
        if workflow_projection.is_workflow_root:
            new_root_run_id = await workflow_service.retry_workflow_async(
                project_id=project_id,
                root_run_id=run_id,
                requested_by=requested_by,
                reason=reason,
                queue_client=queue_client,
            )
            if new_root_run_id is None:
                return None
            return await self.get_run_async(
                project_id=project_id,
                run_id=new_root_run_id,
            )

        if not job_run.job_id:
            raise ValueError(f"Run {run_id} has no job_id")

        trigger_config = json.dumps({"OriginalJobRunId": str(run_id)})
        job_type = job_run.job.type if job_run.job and job_run.job.type else "unknown"
        job_name = job_run.job.name if job_run.job and job_run.job.name else "Unknown Job"
        timeout_seconds = job_run.job.timeout if job_run.job else 300
        new_job_run, _ = await create_queued_job_run_and_maybe_dispatch(
            project_id=project_id,
            queue_client=None,
            job_id=job_run.job_id,
            parameters=job_run.parameters,
            job_type=job_type,
            job_name=job_name,
            timeout_seconds=timeout_seconds,
            triggered_by=requested_by,
            trigger_type=JobTriggerType.RETRY,
            trigger_configuration=trigger_config,
            attempt_count=(job_run.attempt_count or 0) + 1,
        )

        dispatch_run_id = UUID(str(new_job_run.id))

        await log_service.add_log_async(
            job_run_id=run_id,
            message=(
                f"Execution run manually retried. New retry attempt created: {dispatch_run_id}"
            ),
            data=json.dumps({"reason": reason}),
        )
        await log_service.add_log_async(
            job_run_id=dispatch_run_id,
            message=f"Execution run started as retry of {run_id}",
            data=json.dumps(
                {
                    "previousRunId": str(run_id),
                    "previousStatus": job_run.status.value if job_run.status else None,
                    "reason": reason,
                }
            ),
        )
        await workflow_service.rebind_step_retry_async(
            project_id=project_id,
            previous_run_id=run_id,
            new_run_id=dispatch_run_id,
            requested_by=requested_by,
            reason=reason,
        )
        await dispatch_job_run_if_configured(
            queue_client=queue_client,
            project_id=project_id,
            job_run_id=dispatch_run_id,
            job_type=job_type,
            job_name=job_name,
            timeout_seconds=timeout_seconds,
            parameters=job_run.parameters,
        )

        updated = await run_service.get_run_by_id_async(
            dispatch_run_id, include_job=True, include_trigger=False
        )
        if not updated:
            return None

        updated_context = await context_service.get_by_run_id_async(dispatch_run_id)
        return project_execution_run(updated, context=updated_context)


async def get_job_run_resource_async(project_id: UUID, run_id: UUID) -> JobRunModel | None:
    run_service = JobRunDataService(project_id)
    return await run_service.get_run_by_id_async(run_id, include_job=True, include_trigger=False)
