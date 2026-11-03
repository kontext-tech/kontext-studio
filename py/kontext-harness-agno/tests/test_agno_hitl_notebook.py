"""End-to-end HITL pause/resume for notebook-owned Python execution.

The Notebook agent triggers `execute_python_code` itself (no Python agent
round trip). These tests pin the full harness contract around that tool with a
scripted model - no live provider:

- the run must pause instead of executing the server tool body,
- a client-produced `PythonExecutionResult` must resume the run to completion,
- a client error payload must also resume (the model sees the failure).

Notebook-state persistence happens in the client execution flow; the harness
contract under test here is pause -> external result -> continued run.

This is an in-workspace integration test: it uses the real notebook Python tool
(`kontext-agentic`) to prove the adapter handles an actual domain toolkit. The
adapter distribution itself does not depend on `kontext-agentic`; generic HITL
behavior is covered harness-neutrally by the conformance suite.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from agno.db.in_memory import InMemoryDb
from agno.models.base import Model
from agno.models.response import ModelResponse
from agno.tools import Toolkit

from kontext.agent import AgentDescriptor, AgentKind, StreamOptions
from kontext.agentic.tools.python_tool import NotebookPythonTools
from kontext.common.contracts import AgentConfig, ModelRuntime, ResolvedModelConfig
from kontext.harness.agno import materialize
from kontext.harness.agno.system import AgnoAgenticSystem
from kontext.harness.agno.toolkits import adapt_tools_for_agno
from kontext.schema import (
    CodeExecutionOutput,
    CodeTextOutput,
    ProjectModel,
    PythonExecutionResult,
    RunEvent,
    SimpleRunEvent,
    ToolCall,
    ToolCallResult,
)

NOTEBOOK_ID = "1eb96811-39fe-47a4-7e25-08de0be1d149"
BLOCK_ID = "1eb96811-39fe-47a4-7e25-08de0be1d155"


@pytest.fixture(autouse=True)
def _isolated_stream_executor(monkeypatch: pytest.MonkeyPatch):
    """Use a per-test stream pool and reap its thread at teardown.

    The production pool is a process-global singleton whose idle worker thread
    would otherwise show up in the workspace's live-thread diagnostics after
    every run of this module.
    """
    import kontext.harness.agno.run as run_module

    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="agno-stream-test")
    monkeypatch.setattr(run_module, "_agent_stream_executor", executor)
    yield
    executor.shutdown(wait=True, cancel_futures=True)


@dataclass
class _ScriptedToolModel(Model):
    """Replays a fixed tool-call sequence, then answers with plain text."""

    sequence: tuple[tuple[str, dict[str, Any]], ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        self._step = 0

    def _next(self) -> ModelResponse:
        if self._step < len(self.sequence):
            name, arguments = self.sequence[self._step]
            self._step += 1
            return ModelResponse(
                content="",
                tool_calls=[
                    {
                        "id": f"call-{self._step}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }
                ],
            )
        return ModelResponse(content="Done.")

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._next()

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._next()

    def invoke_stream(self, *args: Any, **kwargs: Any) -> Iterator[ModelResponse]:
        yield self._next()

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> AsyncIterator[ModelResponse]:
        yield self._next()

    def _parse_provider_response(self, response: Any, **kwargs: Any) -> ModelResponse:
        return response

    def _parse_provider_response_delta(self, response: Any) -> ModelResponse:
        return response


def _sample_config() -> AgentConfig:
    return AgentConfig(summary=False)


def _model_runtime() -> ModelRuntime:
    return ModelRuntime(
        binding=ResolvedModelConfig(
            canonical_model_id="scripted/model",
            source_type="user_managed",
            adapter_type="scripted",
            connection_kind="scripted",
            display_name="Scripted",
            provider_model_name="model",
        )
    )


def _sample_project() -> ProjectModel:
    return ProjectModel.model_construct(
        id=NOTEBOOK_ID,
        project_code="test-project",
        project_name="Test Project",
        access_level="Private",
    )


def _notebook_system(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, file_service: MagicMock
) -> AgnoAgenticSystem:
    provider = MagicMock()
    provider.get_file_service.return_value = file_service
    provider.get_chat_session_service.return_value = None

    python_tools = NotebookPythonTools(project=_sample_project(), runtime_provider=provider)
    model = _ScriptedToolModel(
        id="scripted",
        sequence=(("execute_python_code", {"notebook_id": NOTEBOOK_ID, "block_id": BLOCK_ID}),),
    )
    monkeypatch.setattr(materialize, "create_model", lambda **_: model)

    agent = materialize.create_agno_agent(
        agent_id="notebook-1",
        name="Notebook Agent",
        tools=[python_tools],
        instructions="Run notebook blocks.",
        config=_sample_config(),
        db=InMemoryDb(),
        model=_model_runtime(),
        session_id="session-1",
        user_id="user-1",
    )
    return AgnoAgenticSystem(
        agent,
        runtime_provider=provider,
        project_id=NOTEBOOK_ID,
        descriptor=AgentDescriptor(
            id=AgentKind.NOTEBOOK,
            name="Notebook Python HITL",
            description="Test helper",
            icon="TestIcon",
        ),
    )


async def _collect_events(
    system: AgnoAgenticSystem,
    *,
    session_id: str,
    tool_outputs: list[ToolCall] | None = None,
) -> list[SimpleRunEvent]:
    events: list[SimpleRunEvent] = []
    async for event in system.stream_response(
        "Execute the notebook python block.",
        session_id=session_id,
        user_id="user-1",
        options=StreamOptions(tool_outputs=tool_outputs),
    ):
        events.append(event)
    return events


def _ok_tool_call(tool_call_id: str) -> ToolCall:
    return ToolCall(
        tool_call_id=tool_call_id,
        tool_name="execute_python_code",
        result=ToolCallResult(
            root=PythonExecutionResult(
                success=True,
                message="ok",
                outputs=[
                    CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="printed"))
                ],
            )
        ),
    )


def _paused_tool_call_ids_from_session(agent: Any, session_id: str) -> str | None:
    """Read the paused run's requirement ids back from the persisted session."""
    session = agent.get_session(session_id=session_id)
    for run in reversed(session.runs or []):
        for requirement in run.active_requirements or []:
            tool_execution = requirement.tool_execution
            if tool_execution is not None and tool_execution.tool_call_id:
                return str(tool_execution.tool_call_id)
    return None


def _event_types(events: list[SimpleRunEvent]) -> list[RunEvent]:
    return [event.event_type for event in events]


def test_notebook_python_toolkit_is_materialized_as_external_execution() -> None:
    """The neutral `external_execution` metadata must reach the Agno toolkit.

    This metadata is what makes Agno pause instead of invoking the server body.
    """
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None

    tools = NotebookPythonTools(project=_sample_project(), runtime_provider=provider)
    adapted = adapt_tools_for_agno([tools])

    assert len(adapted) == 1
    agno_toolkit = adapted[0]
    assert isinstance(agno_toolkit, Toolkit)
    assert "execute_python_code" in agno_toolkit.external_execution_required_tools


@pytest.mark.asyncio
async def test_notebook_python_execution_pauses_and_resumes_with_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    file_service = MagicMock()
    file_service.get_file_content = AsyncMock()
    file_service.update_notebook = AsyncMock()
    system = _notebook_system(monkeypatch, tmp_path, file_service)

    pause_events = await _collect_events(system, session_id="session-1")
    assert RunEvent.RUNPAUSED in _event_types(pause_events)
    assert RunEvent.RUNERROR not in _event_types(pause_events)

    # The server tool body must never run: the client (HITL flow) executes.
    file_service.get_file_content.assert_not_awaited()
    file_service.update_notebook.assert_not_awaited()

    tool_call_id = _paused_tool_call_ids_from_session(system.agent, "session-1")
    assert tool_call_id is not None

    resumed_events = await _collect_events(
        system,
        session_id="session-1",
        tool_outputs=[_ok_tool_call(tool_call_id)],
    )

    assert RunEvent.RUNCOMPLETED in _event_types(resumed_events)
    assert RunEvent.RUNPAUSED not in _event_types(resumed_events)
    assert RunEvent.RUNERROR not in _event_types(resumed_events)


@pytest.mark.asyncio
async def test_notebook_python_execution_resumes_with_client_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """A client-side failure payload resumes the run; the model sees the error."""
    file_service = MagicMock()
    file_service.get_file_content = AsyncMock()
    file_service.update_notebook = AsyncMock()
    system = _notebook_system(monkeypatch, tmp_path, file_service)

    pause_events = await _collect_events(system, session_id="session-err")
    assert RunEvent.RUNPAUSED in _event_types(pause_events)

    tool_call_id = _paused_tool_call_ids_from_session(system.agent, "session-err")
    assert tool_call_id is not None

    error_output = ToolCall(tool_call_id=tool_call_id, tool_call_error="sandbox exploded")
    resumed_events = await _collect_events(
        system,
        session_id="session-err",
        tool_outputs=[error_output],
    )

    assert RunEvent.RUNCOMPLETED in _event_types(resumed_events)
    assert RunEvent.RUNPAUSED not in _event_types(resumed_events)
    assert RunEvent.RUNERROR not in _event_types(resumed_events)
