from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from kontext.chat import ChatAccessContext, ChatStreamContext
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


def _chat_session(
    *,
    project_id: uuid.UUID,
    session_id: uuid.UUID,
    owner_id: uuid.UUID,
    created_at: datetime | None = None,
) -> ChatSessionModel:
    return ChatSessionModel(
        id=str(session_id),
        project_id=str(project_id),
        session_name="Session",
        owner_id=str(owner_id),
        date_created=created_at or datetime.now(UTC),
        python_execution_approval_mode=PythonExecutionApprovalMode.ALWAYSASK,
        is_deleted=False,
    )


class _RuntimeProvider:
    def __init__(self, chat_session_service: Any = None) -> None:
        self._chat_session_service = chat_session_service

    def get_chat_session_service(self) -> Any:
        return self._chat_session_service


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


class _AgentWorkflow:
    def __init__(self, event_payloads: list[SimpleRunEvent]) -> None:
        self.event_payloads = event_payloads
        self.create_agent_calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []

    async def create_agent(
        self,
        chat_request: ChatRequest,
        runtime_provider: Any,
        project: ProjectModel,
        user_id: str | None = None,
        session: ChatSessionModel | None = None,
    ) -> Any:
        self.create_agent_calls.append(
            {
                "chat_request": chat_request,
                "runtime_provider": runtime_provider,
                "project": project,
                "user_id": user_id,
                "session": session,
            }
        )
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
        _ = runtime_provider, session
        return True

    async def stream_agent_response(
        self,
        agent: object,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        *,
        emit_tool_call_events: bool = True,
        tool_outputs=None,
        run_id: str | None = None,
        current_execution_run_id: str | None = None,
        chat_session_service=None,
        token_usage_service=None,
    ):
        self.stream_calls.append(
            {
                "agent": agent,
                "message": message,
                "session_id": session_id,
                "user_id": user_id,
                "project_id": project_id,
                "emit_tool_call_events": emit_tool_call_events,
                "tool_outputs": tool_outputs,
                "run_id": run_id,
                "current_execution_run_id": current_execution_run_id,
                "chat_session_service": chat_session_service,
                "token_usage_service": token_usage_service,
            }
        )
        for event in self.event_payloads:
            yield (
                event.model_dump_json(
                    by_alias=True,
                    exclude_none=True,
                    ensure_ascii=True,
                )
                + "\n"
            )


class _ExecutionTracker:
    def __init__(self, waiting_run_id: uuid.UUID | None = None) -> None:
        self.waiting_run_id = waiting_run_id
        self.created_runs: list[dict[str, Any]] = []
        self.marked_runs: list[dict[str, Any]] = []
        self.persisted_events: list[dict[str, Any]] = []

    async def resolve_waiting_run_id(
        self,
        *,
        project_id: uuid.UUID,
        chat_session_id: uuid.UUID,
        agent_runtime_run_id: str | None = None,
    ) -> uuid.UUID | None:
        self.marked_runs.append(
            {
                "phase": "resolve",
                "project_id": project_id,
                "chat_session_id": chat_session_id,
                "agent_runtime_run_id": agent_runtime_run_id,
            }
        )
        return self.waiting_run_id

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
        self.created_runs.append(
            {
                "project_id": project_id,
                "owner_id": owner_id,
                "chat_session_id": chat_session_id,
                "triggered_by": triggered_by,
                "engine_type": engine_type,
                "platform_run_id": created_run_id,
            }
        )
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
        self.marked_runs.append(
            {
                "phase": "running",
                "project_id": project_id,
                "platform_run_id": platform_run_id,
                "chat_session_id": chat_session_id,
                "agent_runtime_run_id": agent_runtime_run_id,
                "message": message,
            }
        )

    async def persist_event(
        self,
        *,
        project_id: uuid.UUID,
        platform_run_id: uuid.UUID,
        chat_session_id: uuid.UUID,
        event: SimpleRunEvent,
    ) -> SimpleRunEvent:
        self.persisted_events.append(
            {
                "project_id": project_id,
                "platform_run_id": platform_run_id,
                "chat_session_id": chat_session_id,
                "event": event,
            }
        )
        return SimpleRunEvent(
            event_type=event.event_type,
            content=f"persisted:{event.content}",
        )


@pytest.mark.asyncio
async def test_stream_chat_session_prepares_and_persists_events(monkeypatch):
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    session = _chat_session(
        project_id=project_id,
        session_id=session_id,
        owner_id=user_id,
    )

    async def _get_stream_chat_session(**kwargs) -> ChatSessionModel:
        assert kwargs["project_id"] == project_id
        assert kwargs["session_id"] == session_id
        return session

    monkeypatch.setattr(
        "kontext.chat.streaming.get_stream_chat_session",
        _get_stream_chat_session,
    )

    runtime_provider = _RuntimeProvider(chat_session_service=object())
    runtime_factory = _RuntimeFactory(runtime_provider)
    agent_workflow = _AgentWorkflow(
        [
            SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="hello"),
            SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, content="done"),
        ]
    )
    execution_tracker = _ExecutionTracker()

    stream = await stream_chat_session(
        context=ChatStreamContext(
            request=ChatRequest(
                project_id=str(project_id),
                session_id=str(session_id),
                message="  hi there  ",
            ),
            access=ChatAccessContext(
                project_id=project_id,
                user_id=user_id,
                project=_project_model(project_id),
            ),
            headers={"Authorization": "Bearer token"},
        ),
        runtime_factory=runtime_factory,
        agent_workflow=agent_workflow,
        execution_tracker=execution_tracker,
    )

    payloads = []
    async for line in stream:
        payloads.append(json.loads(line))

    assert runtime_factory.calls == [(str(project_id), {"Authorization": "Bearer token"})]
    assert agent_workflow.create_agent_calls[0]["session"] == session
    assert agent_workflow.create_agent_calls[0]["user_id"] == str(user_id)
    assert agent_workflow.stream_calls[0]["message"] == "hi there"
    assert agent_workflow.stream_calls[0]["current_execution_run_id"] == str(
        execution_tracker.created_runs[0]["platform_run_id"]
    )
    assert len(execution_tracker.created_runs) == 1
    assert len(execution_tracker.persisted_events) == 2
    assert [payload["content"] for payload in payloads] == [
        "persisted:hello",
        "persisted:done",
    ]


@pytest.mark.asyncio
async def test_stream_chat_session_resumes_waiting_run(monkeypatch):
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    platform_run_id = uuid.uuid4()
    session = _chat_session(
        project_id=project_id,
        session_id=session_id,
        owner_id=user_id,
    )

    async def _get_stream_chat_session(**kwargs) -> ChatSessionModel:
        _ = kwargs
        return session

    monkeypatch.setattr(
        "kontext.chat.streaming.get_stream_chat_session",
        _get_stream_chat_session,
    )

    execution_tracker = _ExecutionTracker(waiting_run_id=platform_run_id)
    agent_workflow = _AgentWorkflow(
        [SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, content="done")]
    )
    stream = await stream_chat_session(
        context=ChatStreamContext(
            request=ChatRequest(
                project_id=str(project_id),
                session_id=str(session_id),
                message="resume",
                run_id="runtime-run-1",
            ),
            access=ChatAccessContext(
                project_id=project_id,
                user_id=user_id,
                project=_project_model(project_id),
            ),
            headers={},
        ),
        runtime_factory=_RuntimeFactory(_RuntimeProvider()),
        agent_workflow=agent_workflow,
        execution_tracker=execution_tracker,
    )

    assert [json.loads(line)["content"] async for line in stream] == ["persisted:done"]
    assert execution_tracker.created_runs == []
    assert execution_tracker.marked_runs[-1]["phase"] == "running"
    assert execution_tracker.marked_runs[-1]["platform_run_id"] == platform_run_id
    assert agent_workflow.stream_calls[0]["current_execution_run_id"] == str(platform_run_id)


@pytest.mark.asyncio
async def test_stream_delivers_events_when_persistence_fails(monkeypatch):
    """A tracking failure must degrade, never truncate the HTTP stream."""
    project_id = uuid.uuid4()
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    session = _chat_session(
        project_id=project_id,
        session_id=session_id,
        owner_id=user_id,
    )

    async def _get_stream_chat_session(**kwargs) -> ChatSessionModel:
        _ = kwargs
        return session

    monkeypatch.setattr(
        "kontext.chat.streaming.get_stream_chat_session",
        _get_stream_chat_session,
    )

    execution_tracker = _ExecutionTracker()

    async def _failing_persist_event(**kwargs) -> SimpleRunEvent:
        _ = kwargs
        raise RuntimeError("database is locked")

    execution_tracker.persist_event = _failing_persist_event  # type: ignore[method-assign]
    agent_workflow = _AgentWorkflow(
        [
            SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="hello"),
            SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, content="done"),
        ]
    )

    stream = await stream_chat_session(
        context=ChatStreamContext(
            request=ChatRequest(
                project_id=str(project_id),
                session_id=str(session_id),
                message="hi",
            ),
            access=ChatAccessContext(
                project_id=project_id,
                user_id=user_id,
                project=_project_model(project_id),
            ),
            headers={},
        ),
        runtime_factory=_RuntimeFactory(_RuntimeProvider()),
        agent_workflow=agent_workflow,
        execution_tracker=execution_tracker,
    )

    payloads = [json.loads(line) async for line in stream]
    assert [payload["content"] for payload in payloads] == ["hello", "done"]
