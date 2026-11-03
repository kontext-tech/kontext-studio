"""Chat streaming application workflows."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from kontext.common.jobs.trigger_actor import user_actor
from kontext.data import ChatSessionTokenUsageDataService
from kontext.schema import SimpleRunEvent

from .errors import ChatServiceError
from .models import ChatStreamContext
from .providers import (
    ChatAgentWorkflowProtocol,
    ChatExecutionTrackerProtocol,
    ChatRuntimeProviderFactoryProtocol,
)
from .sessions import get_stream_chat_session

logger = logging.getLogger(__name__)


class _TurnComplete:
    """Sentinel inserted after the final event of a streamed agent turn."""


_TURN_COMPLETE = _TurnComplete()


async def stream_chat_session(
    *,
    context: ChatStreamContext,
    runtime_factory: ChatRuntimeProviderFactoryProtocol,
    agent_workflow: ChatAgentWorkflowProtocol,
    execution_tracker: ChatExecutionTrackerProtocol | None = None,
) -> AsyncGenerator[str, None]:
    """Prepare and stream a chat response for an existing chat session."""
    if context.access.project is None:
        raise ChatServiceError(500, "Project context not loaded")

    if str(context.request.project_id) != str(context.access.project_id):
        raise ChatServiceError(403, "Project ID does not match authenticated context")

    request_project_id = UUID(str(context.request.project_id))
    request_session_id = UUID(str(context.request.session_id))

    runtime_provider = await runtime_factory.create_runtime_provider(
        project_id=request_project_id,
        headers=context.headers,
    )
    chat_session_service = runtime_provider.get_chat_session_service()

    session = await get_stream_chat_session(
        project_id=request_project_id,
        session_id=request_session_id,
    )

    if (
        session.owner_id
        and context.access.user_id
        and str(session.owner_id) != str(context.access.user_id)
    ):
        raise ChatServiceError(403, "You do not own this chat session")

    effective_user_id = (
        str(session.owner_id)
        if session.owner_id
        else (str(context.access.user_id) if context.access.user_id else None)
    )

    platform_run_id: UUID | None = None
    if execution_tracker is not None and (context.request.tool_outputs or context.request.run_id):
        platform_run_id = await execution_tracker.resolve_waiting_run_id(
            project_id=request_project_id,
            chat_session_id=request_session_id,
            agent_runtime_run_id=context.request.run_id,
        )

    agent = await agent_workflow.create_agent(
        context.request,
        runtime_provider,
        context.access.project,
        effective_user_id,
        session=session,
    )
    emit_tool_call_events = agent_workflow.resolve_emit_tool_call_events(runtime_provider, session)

    if execution_tracker is not None:
        if platform_run_id is None and not (context.request.tool_outputs or context.request.run_id):
            if context.access.user_id is None:
                raise ChatServiceError(
                    401,
                    "User context required to create an execution run",
                )
            platform_run_id = await execution_tracker.create_run(
                project_id=request_project_id,
                owner_id=context.access.user_id,
                chat_session_id=request_session_id,
                triggered_by=user_actor(str(context.access.user_id)),
                engine_type=session.engine_type if session is not None else None,
            )
        elif platform_run_id is not None and (
            context.request.tool_outputs or context.request.run_id
        ):
            await execution_tracker.mark_run_running(
                project_id=request_project_id,
                platform_run_id=platform_run_id,
                chat_session_id=request_session_id,
                agent_runtime_run_id=context.request.run_id,
                message="Agent execution resumed through chat stream",
            )

    async def _persist_event_line(event_json: str) -> str:
        """Persist one harness event through the tracker (or pass it raw).

        Event delivery must survive execution-tracking failures: an exception
        raised here would truncate the chunked HTTP response (the browser
        reports ERR_INCOMPLETE_CHUNKED_ENCODING) even though the agent run
        itself continues server-side.
        """
        if execution_tracker is None or platform_run_id is None:
            return event_json

        try:
            event = SimpleRunEvent.from_json(event_json)
        except Exception:
            logger.exception("Unparseable run event in execution tracking; delivering raw event")
            return event_json

        if event is None:
            return event_json

        try:
            persisted_event = await execution_tracker.persist_event(
                project_id=request_project_id,
                platform_run_id=platform_run_id,
                chat_session_id=request_session_id,
                event=event,
            )
        except Exception:
            logger.exception(
                "Failed to persist execution run event %s; delivering without tracking",
                event.event_type,
            )
            return event_json

        return (
            persisted_event.model_dump_json(
                by_alias=True,
                exclude_none=True,
                ensure_ascii=True,
            )
            + "\n"
        )

    async def _stream() -> AsyncGenerator[str, None]:
        tracked = execution_tracker is not None and platform_run_id is not None
        agent_stream = agent_workflow.stream_agent_response(
            agent,
            context.request.message.strip(),
            str(context.request.session_id),
            str(context.access.user_id) if context.access.user_id else None,
            project_id=str(context.request.project_id),
            emit_tool_call_events=emit_tool_call_events,
            tool_outputs=context.request.tool_outputs,
            run_id=context.request.run_id,
            current_execution_run_id=(str(platform_run_id) if platform_run_id else None),
            chat_session_service=chat_session_service,
            token_usage_service=ChatSessionTokenUsageDataService(request_project_id),
        )

        if not tracked:
            # Untracked turns stream inline, as before: disconnect
            # cancellation tears the turn down with the connection.
            async for event_json in agent_stream:
                yield await _persist_event_line(event_json)
            return

        # Tracked turns are consumed by a producer task that is NOT owned by
        # the HTTP response. When the client disconnects, Starlette cancels
        # the generator's task — which previously tore the agent turn down
        # mid-flight and left the execution run wedged in "Running" with no
        # terminal status (I5.14-rem). Under the job-tracked model the run
        # row is the source of truth: an orphaned turn keeps running
        # server-side, its terminal status is written by the stream pipeline,
        # and the client can reattach through /runs/{id}/events and resume
        # via /runs/{id}/input.
        items: asyncio.Queue[str | _TurnComplete] = asyncio.Queue()
        completed_inline = asyncio.Event()
        detached = asyncio.Event()

        async def _run_turn() -> None:
            try:
                async for event_json in agent_stream:
                    line = await _persist_event_line(event_json)
                    if detached.is_set():
                        # The HTTP response is gone: keep draining and
                        # persisting (the run row is the source of truth) but
                        # stop queueing lines, so an abandoned turn cannot
                        # accumulate unbounded memory until it finishes.
                        # Nothing is awaited between the check and the put, so
                        # the detach cannot race this iteration.
                        continue
                    items.put_nowait(line)
            except Exception:
                logger.exception("Agent turn failed; ending stream")
            finally:
                completed_inline.set()
                if not detached.is_set():
                    items.put_nowait(_TURN_COMPLETE)

        producer = asyncio.create_task(_run_turn())
        try:
            while True:
                item = await items.get()
                if item is _TURN_COMPLETE:
                    break
                yield str(item)
        finally:
            # Stop delivery before anything else: from here on the producer
            # persists without queueing.
            detached.set()
            while not items.empty():
                items.get_nowait()

            if not completed_inline.is_set() and not producer.done():
                # The response task was cancelled (client disconnect) while
                # the turn was still running: detach — the turn continues
                # server-side. Cancelling this generator must not cancel the
                # producer task.
                logger.info(
                    "Chat stream detached before completion; agent turn continues "
                    "(run %s, session %s)",
                    platform_run_id,
                    request_session_id,
                )

    return _stream()
