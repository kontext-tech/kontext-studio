"""Characterisation tests for chat-stream disconnect survival (D-A/I5.14-rem).

Under the job-tracked model the execution-run row is the source of truth:
when the HTTP response task is cancelled (client disconnect) while a tracked
agent turn is still streaming, the turn must keep running server-side and
finish normally — its terminal status is written by the stream pipeline, and
the client can reattach via /runs/{id}/events and resume via /runs/{id}/input.

Stub classes mirror the shapes of ``test_streaming.py``; the difference is a
*slow* harness that is visibly mid-turn when the response generator closes.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from kontext.chat import ChatAccessContext, ChatStreamContext
from kontext.chat import streaming as streaming_module
from kontext.chat.streaming import stream_chat_session
from kontext.schema import (
    AccessLevel,
    ChatRequest,
    ChatSessionModel,
    ProjectConfiguration,
    ProjectModel,
    PythonExecutionApprovalMode,
    RunEvent,
    SimpleRunEvent,
    TriggerActorModel,
)


def _project_model(project_id: uuid.UUID) -> ProjectModel:
    return ProjectModel(
        id=str(project_id),
        project_name="Test Project",
        project_code="test",
        access_level=AccessLevel.PRIVATE,
        configuration=ProjectConfiguration(
            features=[],
            allowed_file_types=[],
            max_file_bytes_size=0,
            total_storage_allocation_bytes=0,
        ),
        owner_id=str(uuid.uuid4()),
        is_deleted=False,
    )


class _RuntimeProvider:
    def get_chat_session_service(self) -> Any:
        return None


class _RuntimeFactory:
    def __init__(self, runtime_provider: _RuntimeProvider) -> None:
        self.runtime_provider = runtime_provider
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def create_runtime_provider(
        self,
        *,
        project_id: uuid.UUID | str,
        headers: Mapping[str, str],
    ) -> Any:
        self.calls.append((str(project_id), dict(headers)))
        return self.runtime_provider


class _SlowAgentWorkflow:
    """Agent workflow over a slow harness stream with a completion flag."""

    def __init__(self, events: list[str], delay: float) -> None:
        self._events = events
        self._delay = delay
        self.finished = False
        self.stream_calls: list[dict[str, Any]] = []

    async def create_agent(
        self,
        chat_request: ChatRequest,
        runtime_provider: Any,
        project: ProjectModel,
        user_id: str | None = None,
        session: ChatSessionModel | None = None,
    ) -> Any:
        return object()

    async def load_session_messages(
        self,
        chat_request: ChatRequest,
        runtime_provider: Any,
        project: ProjectModel,
        user_id: str | None = None,
        session: ChatSessionModel | None = None,
    ) -> list[Any]:
        return []

    def resolve_emit_tool_call_events(
        self,
        runtime_provider: Any,
        session: ChatSessionModel | None,
    ) -> bool:
        return False

    async def stream_agent_response(
        self,
        agent: object,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        *,
        emit_tool_call_events: bool = True,
        tool_outputs: Any = None,
        run_id: str | None = None,
        current_execution_run_id: str | None = None,
        chat_session_service: Any = None,
        token_usage_service: Any = None,
    ):
        self.stream_calls.append({"message": message, "run_id": current_execution_run_id})
        for event in self._events:
            await asyncio.sleep(self._delay)
            yield event
        self.finished = True


class _ExecutionTracker:
    def __init__(self) -> None:
        self.created_runs: list[uuid.UUID] = []

    async def resolve_waiting_run_id(
        self,
        *,
        project_id: uuid.UUID,
        chat_session_id: uuid.UUID,
        agent_runtime_run_id: str | None = None,
    ) -> uuid.UUID | None:
        return None

    async def create_run(
        self,
        *,
        project_id: uuid.UUID,
        owner_id: uuid.UUID,
        chat_session_id: uuid.UUID,
        triggered_by: TriggerActorModel,
        engine_type: str | None = None,
    ) -> uuid.UUID:
        created_run_id = uuid.uuid4()
        self.created_runs.append(created_run_id)
        return created_run_id

    async def mark_run_running(
        self,
        *,
        project_id: uuid.UUID,
        platform_run_id: uuid.UUID,
        chat_session_id: uuid.UUID,
        agent_runtime_run_id: str | None = None,
        message: str = "Agent execution running",
    ) -> None:
        return None

    async def persist_event(
        self,
        *,
        project_id: uuid.UUID,
        platform_run_id: uuid.UUID,
        chat_session_id: uuid.UUID,
        event: SimpleRunEvent,
    ) -> SimpleRunEvent:
        return event


def _context(project_id: uuid.UUID, user_id: uuid.UUID) -> ChatStreamContext:
    return ChatStreamContext(
        request=ChatRequest(
            project_id=str(project_id),
            session_id=str(uuid.uuid4()),
            message="  hi  ",
        ),
        access=ChatAccessContext(
            project_id=project_id,
            user_id=user_id,
            project=_project_model(project_id),
        ),
        headers={"Authorization": "Bearer token"},
    )


def _session(project_id: uuid.UUID, user_id: uuid.UUID) -> ChatSessionModel:
    return ChatSessionModel(
        id=str(uuid.uuid4()),
        project_id=str(project_id),
        session_name="Session",
        owner_id=str(user_id),
        date_created=datetime.now(UTC),
        python_execution_approval_mode=PythonExecutionApprovalMode.ALWAYSASK,
        is_deleted=False,
    )


def _harness_events() -> list[str]:
    return [
        SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content=c).model_dump_json(
            by_alias=True, exclude_none=True, ensure_ascii=True
        )
        + "\n"
        for c in ("one", "two", "three")
    ]


@pytest.fixture
def _fake_session(monkeypatch: Any) -> None:
    """Make get_stream_chat_session deterministic without the database."""
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async def get_stream_chat_session(**kwargs: Any) -> ChatSessionModel:
        return _session(project_id, user_id)

    monkeypatch.setattr(streaming_module, "get_stream_chat_session", get_stream_chat_session)
    return project_id, user_id  # type: ignore[return-value]


async def _wait_until(predicate: Any, interval: float = 0.02, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not predicate():
        if loop.time() > deadline:
            pytest.fail("condition not met in time")
        await asyncio.sleep(interval)


@pytest.mark.asyncio
async def test_disconnect_does_not_kill_tracked_turn(_fake_session: Any) -> None:
    """A cancelled response generator must not cancel the in-flight turn."""
    project_id, user_id = _fake_session
    harness = _SlowAgentWorkflow(_harness_events(), delay=0.05)
    tracker = _ExecutionTracker()

    stream_gen = await stream_chat_session(
        context=_context(project_id, user_id),
        runtime_factory=_RuntimeFactory(_RuntimeProvider()),
        agent_workflow=harness,
        execution_tracker=tracker,
    )

    # Receive the first line, then disconnect (cancel the response task).
    first_line = await stream_gen.__anext__()
    assert first_line.strip()
    await stream_gen.aclose()

    # The turn keeps running server-side and finishes normally.
    await _wait_until(lambda: harness.finished)
    assert len(tracker.created_runs) == 1


@pytest.mark.asyncio
async def test_disconnected_turn_retains_no_unconsumed_lines(
    _fake_session: Any, monkeypatch: Any
) -> None:
    """An abandoned turn keeps persisting but must not queue lines forever.

    The producer outlives the HTTP response, so anything it keeps queueing
    after the disconnect is unreachable memory. The queue is drained on detach
    and no further lines are enqueued.
    """
    project_id, user_id = _fake_session
    harness = _SlowAgentWorkflow(_harness_events(), delay=0.01)
    tracker = _ExecutionTracker()

    class _QueueSpy:
        """Record the queue the streaming module creates (module-local patch)."""

        def __init__(self, real: Any) -> None:
            self._real = real
            self.instances: list[asyncio.Queue[Any]] = []

        def __getattr__(self, name: str) -> Any:
            return getattr(self._real, name)

        def Queue(self, *args: Any, **kwargs: Any) -> asyncio.Queue[Any]:  # noqa: N802
            queue: asyncio.Queue[Any] = self._real.Queue(*args, **kwargs)
            self.instances.append(queue)
            return queue

    spy = _QueueSpy(asyncio)
    monkeypatch.setattr(streaming_module, "asyncio", spy)

    stream_gen = await stream_chat_session(
        context=_context(project_id, user_id),
        runtime_factory=_RuntimeFactory(_RuntimeProvider()),
        agent_workflow=harness,
        execution_tracker=tracker,
    )
    await stream_gen.__anext__()
    await stream_gen.aclose()

    await _wait_until(lambda: harness.finished)
    assert len(spy.instances) == 1
    assert spy.instances[0].qsize() == 0


@pytest.mark.asyncio
async def test_tracked_stream_relays_persisted_lines(_fake_session: Any) -> None:
    """Normal completion still relays every event through the tracker."""
    project_id, user_id = _fake_session
    harness = _SlowAgentWorkflow(_harness_events(), delay=0.0)
    tracker = _ExecutionTracker()

    stream_gen = await stream_chat_session(
        context=_context(project_id, user_id),
        runtime_factory=_RuntimeFactory(_RuntimeProvider()),
        agent_workflow=harness,
        execution_tracker=tracker,
    )
    lines: list[str] = [line async for line in stream_gen]

    assert len(lines) == 3
    assert harness.finished


@pytest.mark.asyncio
async def test_untracked_turn_still_cancels_on_disconnect(monkeypatch: Any) -> None:
    """Untracked turns keep their previous inline semantics."""
    project_id, user_id = uuid.uuid4(), uuid.uuid4()

    async def get_stream_chat_session(**kwargs: Any) -> ChatSessionModel:
        return _session(project_id, user_id)

    monkeypatch.setattr(streaming_module, "get_stream_chat_session", get_stream_chat_session)

    harness = _SlowAgentWorkflow(_harness_events(), delay=0.05)
    stream_gen = await stream_chat_session(
        context=_context(project_id, user_id),
        runtime_factory=_RuntimeFactory(_RuntimeProvider()),
        agent_workflow=harness,
        execution_tracker=None,
    )
    await stream_gen.__anext__()
    await stream_gen.aclose()
    await asyncio.sleep(0.2)
    assert not harness.finished
