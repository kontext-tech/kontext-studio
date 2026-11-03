"""Execution run endpoints projected from job-run persistence."""

from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from kontext.auth import JobPermissions, QuerySessionPermissions
from kontext.common.messaging import IQueueClient
from kontext.execution.runs import ExecutionRunService
from kontext.schema import (
    ExecutionEventModel,
    ExecutionLogModel,
    ExecutionRunCancelRequest,
    ExecutionRunInputRequest,
    ExecutionRunModel,
    ExecutionRunRetryRequest,
    PaginatedListOfExecutionRunModel,
)

from ..dependencies import (
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_QUERY,
    QUEUE_CLIENT_DEP,
    RUN_ID_PATH,
    AuthContext,
    create_auth_dependency,
    extract_path_param,
)
from ..services.execution_runs import (
    resume_execution_run_input_async,
    validate_run_input_request_async,
)
from ..services.run_event_bus import stream_run_event_batches
from ..transport_adapters import build_query_access_context

router = APIRouter()

# Upper bound on how long a single SSE connection may stream a run that never
# reaches a terminal status. Prevents a stuck run from holding a connection
# open indefinitely. (The shared run-event bus enforces the same bound on its
# tailer loop.)
RUN_EVENT_MAX_STREAM_SECONDS = 30 * 60


async def get_execution_run_resource(
    request: Request, auth_context: AuthContext[ExecutionRunModel]
) -> ExecutionRunModel | None:
    run_id = extract_path_param(request, "run_id")
    if not run_id:
        return None

    return await ExecutionRunService().get_run_async(
        project_id=auth_context.project_id,
        run_id=UUID(str(run_id)),
    )


RUN_READ_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.READ, QuerySessionPermissions.READ],
    resource_getter=get_execution_run_resource,
    allow_owner=True,
)

RUN_WRITE_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.UPDATE],
    resource_getter=get_execution_run_resource,
    allow_owner=True,
)


@router.get(
    "",
    response_model=PaginatedListOfExecutionRunModel,
    operation_id="ListRuns",
)
async def list_runs(
    project_id: PROJECT_ID_QUERY,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    status: str | None = Query(None, description="Optional underlying run status filter"),
    auth_context: AuthContext[ExecutionRunModel] = RUN_READ_AUTH,
) -> PaginatedListOfExecutionRunModel:
    service = ExecutionRunService()
    return await service.list_runs_async(
        project_id=project_id,
        page_index=page_index,
        page_size=page_size,
        owner_id=auth_context.effective_owner_id,
        status=status,
    )


@router.get("/{runId}", response_model=ExecutionRunModel, operation_id="GetRun")
async def get_run(
    run_id: Annotated[UUID, RUN_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ExecutionRunModel] = RUN_READ_AUTH,
) -> ExecutionRunModel:
    _ = project_id
    service = ExecutionRunService()
    run = await service.get_run_async(project_id=auth_context.project_id, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return run


@router.get(
    "/{runId}/logs",
    response_model=list[ExecutionLogModel],
    operation_id="GetRunLogs",
)
async def get_run_logs(
    run_id: Annotated[UUID, RUN_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    limit: int = Query(default=100, ge=1, le=1000),
    auth_context: AuthContext[ExecutionRunModel] = RUN_READ_AUTH,
) -> list[ExecutionLogModel]:
    _ = project_id
    service = ExecutionRunService()
    run = await service.get_run_async(project_id=auth_context.project_id, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return await service.get_logs_async(
        project_id=auth_context.project_id,
        run_id=run_id,
        limit=limit,
    )


@router.get(
    "/{runId}/events",
    response_model=None,
    operation_id="StreamRunEvents",
)
async def stream_run_events(
    run_id: Annotated[UUID, RUN_ID_PATH],
    request: Request,
    project_id: PROJECT_ID_QUERY,
    limit: int = Query(default=100, ge=1, le=1000),
    auth_context: AuthContext[ExecutionRunModel] = RUN_READ_AUTH,
) -> StreamingResponse:
    _ = project_id
    service = ExecutionRunService()
    run = await service.get_run_async(project_id=auth_context.project_id, run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    async def event_stream():
        emitted_event_ids: set[str] = set()
        deadline = asyncio.get_running_loop().time() + RUN_EVENT_MAX_STREAM_SECONDS

        async with stream_run_event_batches(
            run_id=run_id, project_id=auth_context.project_id, limit=limit
        ) as batches:
            async for batch in batches:
                if batch.run_missing:
                    break

                status_event = batch.status_event
                if status_event is not None and status_event.id not in emitted_event_ids:
                    emitted_event_ids.add(status_event.id)
                    yield _sse_event("status", status_event)

                for log_event in batch.log_events:
                    if log_event.id in emitted_event_ids:
                        continue
                    emitted_event_ids.add(log_event.id)
                    yield _sse_event("log", log_event)

                # A terminal batch (or the tail loop's end-of-stream sentinel,
                # which arrives terminal with no status event) ends the stream.
                if batch.is_terminal:
                    break

                if await request.is_disconnected():
                    break

                if asyncio.get_running_loop().time() >= deadline:
                    break

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse_event(event_name: str, payload: ExecutionEventModel) -> str:
    return f"event: {event_name}\ndata: {payload.model_dump_json(by_alias=True)}\n\n"


@router.post(
    "/{runId}/input",
    response_model=ExecutionRunModel,
    status_code=202,
    operation_id="SubmitRunInput",
)
async def submit_run_input(
    run_id: Annotated[UUID, RUN_ID_PATH],
    request: ExecutionRunInputRequest,
    fastapi_request: Request,
    background_tasks: BackgroundTasks,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ExecutionRunModel] = RUN_WRITE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> ExecutionRunModel:
    _ = project_id
    resolved = await validate_run_input_request_async(
        project_id=auth_context.project_id,
        run_id=run_id,
        request=request,
        user_id=auth_context.user_id,
    )

    if not auth_context.project or not auth_context.user:
        raise HTTPException(status_code=500, detail="Project or user context not loaded")

    background_tasks.add_task(
        resume_execution_run_input_async,
        project_id=auth_context.project_id,
        run_id=run_id,
        chat_session_id=resolved.chat_session_id,
        paused_run_id=resolved.paused_run_id,
        request=request,
        user=auth_context.user,
        project=auth_context.project,
        query_access_context=build_query_access_context(auth_context),
        queue_client=queue_client,
    )

    service = ExecutionRunService()
    updated = await service.get_run_async(
        project_id=auth_context.project_id,
        run_id=run_id,
    )
    return updated or resolved.run


@router.post(
    "/{runId}/cancel",
    response_model=ExecutionRunModel,
    operation_id="CancelRun",
)
async def cancel_run(
    run_id: Annotated[UUID, RUN_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    request: ExecutionRunCancelRequest | None = None,
    auth_context: AuthContext[ExecutionRunModel] = RUN_WRITE_AUTH,
) -> ExecutionRunModel:
    _ = project_id
    service = ExecutionRunService()

    try:
        run = await service.cancel_run_async(
            project_id=auth_context.project_id,
            run_id=run_id,
            requested_by=auth_context.trigger_actor,
            reason=request.reason if request else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return run


@router.post(
    "/{runId}/retry",
    response_model=ExecutionRunModel,
    status_code=202,
    operation_id="RetryRun",
)
async def retry_run(
    run_id: Annotated[UUID, RUN_ID_PATH],
    request: ExecutionRunRetryRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ExecutionRunModel] = RUN_WRITE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> ExecutionRunModel:
    _ = project_id
    if not queue_client:
        raise HTTPException(status_code=503, detail="Queue service unavailable")

    service = ExecutionRunService()
    try:
        run = await service.retry_run_async(
            project_id=auth_context.project_id,
            run_id=run_id,
            requested_by=auth_context.trigger_actor,
            reason=request.reason,
            queue_client=queue_client,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    return run
