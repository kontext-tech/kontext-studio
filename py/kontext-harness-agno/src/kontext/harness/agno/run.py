"""Agno run execution and event streaming.

Runs the Agno agent/team in a dedicated thread with its own event loop so sync
Agno internals (SQLite persistence, provider SDK calls) cannot block the API
event loop, and converts the produced events into the neutral `SimpleRunEvent`
stream with consolidated buffering.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agno.agent import RunErrorEvent, RunPausedEvent
from kontext.agent import (
    AgentContext,
    InMemoryToolResultSidecar,
    ToolExecutionContext,
    agent_context_scope,
)
from kontext.agent.streaming import BoundedEventQueue, EventBuffer
from kontext.schema import RunEvent, SimpleRunEvent, ToolCall

from .agent_types import AgnoAgentOrTeam
from .event_converters import to_simple_event
from .pauses import AgnoResumeState, apply_tool_outputs, recover_paused_run

_logger = logging.getLogger(__name__)

#: Cap concurrent agent streams so a burst of chat requests cannot spawn one
#: OS thread + event loop each; extra streams queue until a slot is free.
_AGNO_STREAM_THREADS = int(os.getenv("KONTEXT_AGENT_STREAM_THREADS", "8"))
_agent_stream_executor = ThreadPoolExecutor(
    max_workers=max(1, _AGNO_STREAM_THREADS), thread_name_prefix="agno-stream"
)

# Events buffered for the API-server consumer while the agent thread keeps
# producing. Bounded so an abandoned consumer (client disconnected mid-run)
# cannot grow memory without limit; see `_AgentEventQueue`.
_AGENT_EVENT_QUEUE_LIMIT = 10_000

# Pause/error events (and the end-of-stream sentinel, represented by ``None``)
# must never be evicted: dropping a pause would make the consumer emit a false
# completion instead of leaving the run resumable.
_CRITICAL_EVENT_TYPES = (RunPausedEvent, RunErrorEvent)


def _is_critical_event(item: Any) -> bool:
    return item is None or isinstance(item, _CRITICAL_EVENT_TYPES)


async def _recover_paused_state_into(
    *,
    agent: AgnoAgentOrTeam,
    session_id: str | None,
    tool_outputs: Sequence[ToolCall] | None,
    run_id: str | None,
    resume_state: AgnoResumeState,
    logger: Any,
) -> None:
    """Fill ``resume_state`` from the persisted Agno session.

    Used when tool outputs resume a run whose in-memory pause state was lost
    across requests. A client-provided ``run_id`` narrows the search to that
    specific run.
    """
    if run_id:
        logger.info(f"Fetching requirements for client-provided run_id: {run_id}")
    else:
        logger.info("Attempting to recover paused run state from session")

    recovered = await recover_paused_run(
        agent,
        session_id=session_id,
        tool_outputs=tool_outputs,
        run_id=run_id,
        logger=logger,
    )
    if recovered is not None and recovered.run_id and recovered.requirements:
        resume_state.run_id = recovered.run_id
        resume_state.requirements = recovered.requirements
        logger.info(
            f"Recovered paused run {recovered.run_id} from Agno session state "
            f"with {len(recovered.requirements)} requirements"
        )


async def _stream_agent_turn(
    *,
    agent: AgnoAgentOrTeam,
    message: str,
    session_id: str | None,
    user_id: str | None,
    tool_outputs: Sequence[ToolCall] | None,
    resume_state: AgnoResumeState,
    process_tool_outputs: (Callable[[str, Sequence[ToolCall]], Awaitable[None]] | None),
    emit: Callable[[Any], None],
) -> None:
    """Stream one agent turn: a fresh run, or a paused-run continuation."""
    if tool_outputs:
        # Resuming from pause: set external execution results on the persisted
        # Agno RunRequirements (neutral requirement payloads lack the internal
        # state Agno's continue_run needs).
        active_requirements = resume_state.requirements
        if active_requirements:
            apply_tool_outputs(active_requirements, tool_outputs or [])
            if process_tool_outputs is not None and session_id:
                await process_tool_outputs(session_id, tool_outputs or [])

        if not resume_state.run_id or not active_requirements:
            raise RuntimeError(
                "Received tool outputs but no paused run state was found for this session. "
                "The run may have already completed or the session_id is incorrect."
            )

        async for event in agent.acontinue_run(
            run_id=resume_state.run_id,
            requirements=active_requirements,
            stream=True,
            stream_events=True,
            session_id=session_id,
            user_id=user_id,
        ):
            if event:
                emit(event)
        return

    async for event in agent.arun(
        message,
        stream=True,
        stream_events=True,
        session_id=session_id,
        user_id=user_id,
    ):
        if event:
            emit(event)


async def stream_agno_events(
    *,
    agent: AgnoAgentOrTeam,
    message: str,
    session_id: str | None,
    user_id: str | None,
    context: AgentContext,
    resume_state: AgnoResumeState,
    tool_outputs: Sequence[ToolCall] | None = None,
    run_id: str | None = None,
    emit_tool_call_events: bool = True,
    event_buffer: EventBuffer,
    process_tool_outputs: (Callable[[str, Sequence[ToolCall]], Awaitable[None]] | None) = None,
    logger: Any,
) -> AsyncGenerator[SimpleRunEvent, None]:
    """Run the Agno agent (or resume a paused run) and stream neutral events.

    Mutates ``resume_state`` when a new pause is encountered so the caller can
    chain resumes without re-scanning the persisted session.
    """
    # Adapter-owned storage for typed tool payloads referenced across tool
    # calls (see ToolResultSidecar). One instance per streaming turn, shared
    # by the agent-run thread and the consumer loop; released when the turn's
    # context is unregistered.
    tool_ctx = ToolExecutionContext(
        project_id=context.project_id,
        session_id=context.session_id,
        tool_results=InMemoryToolResultSidecar(),
    )
    consumer_loop = asyncio.get_running_loop()
    # Neutral bounded queue with adapter-specific critical events: pause/error
    # agno events (and the None end-of-stream sentinel) are never evicted.
    queue = BoundedEventQueue(maxsize=_AGENT_EVENT_QUEUE_LIMIT, is_critical=_is_critical_event)
    had_error = False
    had_paused = False

    def _emit(item: Any) -> None:
        """Thread-safely enqueue an item for the consumer loop."""
        try:
            consumer_loop.call_soon_threadsafe(queue.offer, item)
        except RuntimeError:
            # Consumer loop already closed (e.g. client disconnected).
            logger.debug("Dropping agent stream event: consumer loop is closed")

    async def agent_runner() -> None:
        with agent_context_scope(context, tool_ctx):
            try:
                if (
                    tool_outputs
                    and (not resume_state.run_id or not resume_state.requirements)
                    and session_id
                ):
                    await _recover_paused_state_into(
                        agent=agent,
                        session_id=session_id,
                        tool_outputs=tool_outputs,
                        run_id=run_id,
                        resume_state=resume_state,
                        logger=logger,
                    )

                await _stream_agent_turn(
                    agent=agent,
                    message=message,
                    session_id=session_id,
                    user_id=user_id,
                    tool_outputs=tool_outputs,
                    resume_state=resume_state,
                    process_tool_outputs=process_tool_outputs,
                    emit=_emit,
                )
                # Signal completion
                _emit(None)
            except Exception as e:
                logger.error(f"Agent error in stream runner: {e}")
                _emit(RunErrorEvent(content=str(e)))
                _emit(None)

    def run_agent_in_thread() -> None:
        """Run agent in a pooled worker thread with its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(agent_runner())
        except Exception as e:
            logger.error(f"Thread event loop error: {e}")
            _emit(RunErrorEvent(content=str(e)))
            _emit(None)
        finally:
            loop.close()

    _agent_stream_executor.submit(run_agent_in_thread)

    with agent_context_scope(context):
        while True:
            try:
                event = await queue.take()
                if event is None:  # End of stream
                    break

                current_session_id = session_id or getattr(agent, "session_id", None)

                if isinstance(event, RunErrorEvent):
                    had_error = True
                    buffered_event = event_buffer.flush()
                    if buffered_event:
                        yield buffered_event

                    simple_events = to_simple_event(
                        event,
                        emit_tool_call_events=emit_tool_call_events,
                        session_id=current_session_id,
                    )
                    simple_event = (
                        simple_events[0]
                        if simple_events
                        else SimpleRunEvent(event_type=RunEvent.RUNERROR)
                    )
                    yield simple_event
                    break

                converted_events = to_simple_event(
                    event,
                    emit_tool_call_events=emit_tool_call_events,
                    session_id=current_session_id,
                )

                for simple_event in converted_events:
                    if simple_event.event_type == RunEvent.RUNPAUSED:
                        had_paused = True
                        if isinstance(event, RunPausedEvent):
                            resume_state.run_id = event.run_id
                            resume_state.requirements = event.active_requirements
                        else:
                            logger.warning(
                                f"Captured RunPaused SimpleRunEvent but underlying event type was {type(event)}"
                            )
                        logger.info(
                            f"Captured pause event: run_id={resume_state.run_id}, "
                            f"num_requirements={len(resume_state.requirements) if resume_state.requirements else 0}"
                        )

                    # Disabled buffers pass events through unchanged (the buffer's
                    # `add_event` yields non-bufferable events immediately).
                    flush_event = event_buffer.flush_on_event_type_change(simple_event.event_type)
                    if flush_event:
                        yield flush_event

                    buffered_result = event_buffer.add_event(simple_event)
                    if buffered_result:
                        yield buffered_result

            except TimeoutError:
                continue
            except Exception as e:
                had_error = True
                logger.error(f"Streaming error: {e}")
                buffered_event = event_buffer.flush()
                if buffered_event:
                    yield buffered_event

                yield SimpleRunEvent(event_type=RunEvent.RUNERROR, error_details=str(e))
                break

    buffered_event = event_buffer.flush() if not had_error else None
    if buffered_event:
        yield buffered_event

    if not had_error and not had_paused:
        yield SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED)
