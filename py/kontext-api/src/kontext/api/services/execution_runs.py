"""API access to execution-run application services."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException

from kontext.agentic.chat_handler import ChatHandler
from kontext.data import ChatSessionTokenUsageDataService
from kontext.execution import (
    ExecutionRunInputValidationError,
    ExecutionRunService,
    ResolvedExecutionRunInput,
    build_log_event,
    build_status_event,
    get_job_run_resource_async,
    infer_execution_run_kind,
    map_job_run_status,
    project_execution_run,
)
from kontext.query import QueryAccessContext
from kontext.schema import (
    ChatRequest,
    ExecutionRunInputRequest,
    SimpleRunEvent,
)

from .agent_run_tracking import LIFECYCLE_SERVICE as _LIFECYCLE_SERVICE
from .agent_run_tracking import (
    create_agent_execution_run_async,
    mark_agent_execution_running_async,
    persist_agent_execution_event_async,
    resolve_waiting_agent_execution_run_id_async,
)
from .chats import get_stream_chat_session_service
from .runtime import build_authorized_runtime_provider


async def _process_resumed_agent_stream(
    *,
    project_id: UUID,
    run_id: UUID,
    chat_session_id: UUID,
    raw_events,
) -> None:
    # Cast to Any to avoid stale editor type-cache false positives
    # when new lifecycle methods are added during refactors.
    lifecycle_service: Any = cast(Any, _LIFECYCLE_SERVICE)
    await lifecycle_service.process_resumed_agent_stream_async(
        project_id=project_id,
        run_id=run_id,
        chat_session_id=chat_session_id,
        raw_events=raw_events,
        parse_event=SimpleRunEvent.from_json,
    )


async def validate_run_input_request_async(
    *,
    project_id: UUID,
    run_id: UUID,
    request: ExecutionRunInputRequest,
    user_id: UUID,
) -> ResolvedExecutionRunInput:
    """Validate that a run-input submission targets a resumable agent run."""
    try:
        return await _LIFECYCLE_SERVICE.validate_run_input_request_async(
            project_id=project_id,
            run_id=run_id,
            request=request,
            user_id=user_id,
            get_chat_session=get_stream_chat_session_service,
        )
    except ExecutionRunInputValidationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


async def resume_execution_run_input_async(
    *,
    project_id: UUID,
    run_id: UUID,
    chat_session_id: UUID,
    paused_run_id: str | None,
    request: ExecutionRunInputRequest,
    user,
    project,
    query_access_context: QueryAccessContext,
    queue_client,
) -> None:
    """Resume a paused execution run through the existing agent/session pipeline."""
    chat_handler = ChatHandler()

    try:
        session = await get_stream_chat_session_service(
            project_id=project_id,
            session_id=chat_session_id,
        )

        runtime_provider = build_authorized_runtime_provider(
            project_id=str(project_id),
            access_context=query_access_context,
            queue_client=queue_client,
        )

        effective_user_id = str(getattr(user, "id", ""))
        if session.owner_id:
            effective_user_id = str(session.owner_id)

        agent = await chat_handler.create_agent(
            ChatRequest(
                project_id=str(project_id),
                session_id=str(chat_session_id),
                message=request.message or "",
                tool_outputs=request.tool_outputs,
                run_id=paused_run_id,
            ),
            runtime_provider,
            project,
            effective_user_id,
            session=session,
        )
        emit_tool_call_events = chat_handler.resolve_emit_tool_call_events(
            runtime_provider, session
        )

        await _LIFECYCLE_SERVICE.mark_execution_resumed_async(
            project_id=project_id,
            run_id=run_id,
            chat_session_id=chat_session_id,
            paused_run_id=paused_run_id,
        )

        await _process_resumed_agent_stream(
            project_id=project_id,
            run_id=run_id,
            chat_session_id=chat_session_id,
            raw_events=chat_handler.stream_agent_response(
                agent,
                (request.message or "").strip(),
                str(chat_session_id),
                str(getattr(user, "id", "")),
                project_id=str(project_id),
                emit_tool_call_events=emit_tool_call_events,
                tool_outputs=request.tool_outputs,
                run_id=paused_run_id,
                chat_session_service=runtime_provider.get_chat_session_service(),
                token_usage_service=ChatSessionTokenUsageDataService(project_id),
            ),
        )
    except Exception as exc:
        await _LIFECYCLE_SERVICE.mark_resume_failed_async(
            project_id=project_id,
            run_id=run_id,
            chat_session_id=chat_session_id,
            paused_run_id=paused_run_id,
            error=exc,
        )


__all__ = [
    "ExecutionRunService",
    "ResolvedExecutionRunInput",
    "build_log_event",
    "build_status_event",
    "create_agent_execution_run_async",
    "get_job_run_resource_async",
    "infer_execution_run_kind",
    "map_job_run_status",
    "mark_agent_execution_running_async",
    "persist_agent_execution_event_async",
    "project_execution_run",
    "resolve_waiting_agent_execution_run_id_async",
    "resume_execution_run_input_async",
    "validate_run_input_request_async",
]
