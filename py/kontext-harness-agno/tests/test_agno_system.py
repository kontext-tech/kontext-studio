from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from agno.models.response import ToolExecution
from agno.run.agent import RunOutput
from agno.run.base import RunStatus
from agno.run.requirement import RunRequirement
from agno.run.team import TeamRunOutput
from agno.session.team import TeamSession

from kontext.agent import (
    KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY,
    KONTEXT_SESSION_NAMESPACE,
    AgentDescriptor,
    AgentKind,
    create_kontext_session_state,
)
from kontext.common.contracts import AgentConfig, ModelRuntime, ResolvedModelConfig
from kontext.harness.agno.materialize import (
    create_agno_agent,
    create_agno_team,
)
from kontext.harness.agno.pauses import recover_paused_run
from kontext.harness.agno.storage import NeutralBackedDb
from kontext.harness.agno.system import AgnoAgenticSystem
from kontext.schema import ToolCall


class _TestAgnoSystem(AgnoAgenticSystem):
    agent_definition = AgentDescriptor(
        id=AgentKind.COORDINATOR,
        name="Test Agno System",
        description="Test helper for agno system behavior",
        icon="TestIcon",
    )


def _sample_config() -> AgentConfig:
    return AgentConfig(default_sample_limit=3, sql_dialect="DuckDB")


def _model_runtime() -> ModelRuntime:
    return ModelRuntime(
        binding=ResolvedModelConfig(
            canonical_model_id="openai/gpt-4.1-mini",
            source_type="user_managed",
            adapter_type="openai_native",
            connection_kind="openai",
            display_name="Test",
            provider_model_name="gpt-4.1-mini",
        )
    )


def _external_requirement(tool_call_id: str) -> RunRequirement:
    return RunRequirement(
        ToolExecution(
            tool_call_id=tool_call_id,
            external_execution_required=True,
        )
    )


@pytest.mark.asyncio
async def test_aget_paused_run_state_supports_team_sessions() -> None:
    requirement = _external_requirement("tool-1")
    runs: list[TeamRunOutput | RunOutput] = [
        TeamRunOutput(
            run_id="run-1",
            status=RunStatus.paused,
            requirements=[requirement],
        )
    ]
    team_session = TeamSession(
        session_id="session-1",
        runs=runs,
    )

    agent = MagicMock()
    agent.db = object()
    agent.get_session.return_value = team_session

    _ = _TestAgnoSystem  # subclasses verified constructible; recovery is module-level

    state = await recover_paused_run(
        agent,
        session_id="session-1",
        tool_outputs=[ToolCall(tool_call_id="tool-1")],
        run_id="run-1",
        logger=MagicMock(),
    )

    assert state is not None
    assert state.run_id == "run-1"
    assert state.requirements == [requirement]


@pytest.mark.asyncio
async def test_aget_paused_run_state_ignores_member_run_ids_for_team_sessions() -> None:
    requirement = _external_requirement("tool-1")
    runs: list[TeamRunOutput | RunOutput] = [
        RunOutput(
            run_id="member-run-1",
            status=RunStatus.paused,
            requirements=[requirement],
        ),
        TeamRunOutput(
            run_id="team-run-1",
            status=RunStatus.paused,
            requirements=[requirement],
        ),
    ]
    team_session = TeamSession(
        session_id="session-1",
        runs=runs,
    )

    agent = MagicMock()
    agent.db = object()
    agent.get_session.return_value = team_session

    _ = _TestAgnoSystem  # subclasses verified constructible; recovery is module-level

    state = await recover_paused_run(
        agent,
        session_id="session-1",
        tool_outputs=[ToolCall(tool_call_id="tool-1")],
        run_id="member-run-1",
        logger=MagicMock(),
    )

    assert state is not None
    assert state.run_id == "team-run-1"
    assert state.requirements == [requirement]


def test_create_agno_team_enables_member_response_storage(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("kontext.harness.agno.materialize.create_model", lambda **_kwargs: object())

    def fake_team(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("kontext.harness.agno.materialize.Team", fake_team)

    create_agno_team(
        team_id="team-1",
        name="Team",
        members=[],
        instructions="test",
        config=_sample_config(),
        db=NeutralBackedDb(None),
        model=_model_runtime(),
    )

    assert captured["store_member_responses"] is True
    assert captured["compress_tool_results"] is True
    assert captured["add_session_summary_to_context"] is True
    assert captured["max_tool_calls_from_history"] == 3


def test_create_agno_agent_enables_tool_result_compression(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("kontext.harness.agno.materialize.create_model", lambda **_kwargs: object())

    def fake_agent(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("kontext.harness.agno.materialize.Agent", fake_agent)

    create_agno_agent(
        agent_id="agent-1",
        name="Agent",
        tools=[],
        instructions="test",
        config=_sample_config(),
        db=NeutralBackedDb(None),
        model=_model_runtime(),
    )

    assert captured["compress_tool_results"] is True
    assert captured["add_session_summary_to_context"] is True
    assert captured["max_tool_calls_from_history"] == 3


@pytest.mark.asyncio
async def test_resume_registers_saved_tables_in_shared_state(monkeypatch) -> None:
    """HITL results must register ``save_table`` outputs server-side.

    The Python tool bodies never run for external-execution tools, so the
    resume hook is the only place the harness can put saved tables into the
    shared session state that team members read.
    """

    from kontext.agent import SharedSessionStore, create_kontext_session_state
    from kontext.common.jobs.trigger_actor import agent_actor
    from kontext.schema import (
        ArtifactOrigin,
        ArtifactProvenance,
        ArtifactType,
        PythonExecutionResult,
        PythonSavedTable,
        ToolCallResult,
    )

    session_state = create_kontext_session_state()
    agent = MagicMock()
    agent.session_state = session_state
    provider = MagicMock()
    recorded: dict[str, object] = {}

    async def fake_link(**kwargs):
        recorded.update(kwargs)
        return True

    monkeypatch.setattr("kontext.harness.agno.system.helper_link_artifact_to_session", fake_link)

    system = _TestAgnoSystem(agent=agent, runtime_provider=provider, project_id=str(uuid4()))
    data_table_id = str(uuid4())
    provenance = ArtifactProvenance(
        origin=ArtifactOrigin.AGENTPYTHON, created_by=agent_actor("python_tool")
    )
    tool_call = ToolCall(
        tool_call_id="tool-1",
        tool_name="execute_python_script",
        result=ToolCallResult(
            root=PythonExecutionResult(
                success=True,
                message="ok",
                saved_tables=[
                    PythonSavedTable(data_table_id=data_table_id, title="Saved", row_count=3)
                ],
                provenance=provenance,
            )
        ),
    )

    await system._process_tool_output_artifacts("session-1", [tool_call])

    store = SharedSessionStore(session_state)
    descriptor = store.get_artifact_descriptor(data_table_id)
    assert descriptor is not None
    assert descriptor.title == "Saved"
    assert descriptor.row_count == 3
    assert recorded["artifact_id"] == data_table_id
    assert recorded["artifact_type"] == ArtifactType.DATATABLE
    assert recorded["provenance"] is provenance


def test_agno_system_bind_current_execution_run_id_sets_session_state() -> None:
    raw_agent = SimpleNamespace(session_state=None)
    system = _TestAgnoSystem(
        agent=cast("Any", raw_agent),
        runtime_provider=cast("Any", MagicMock()),
        project_id="550e8400-e29b-41d4-a716-446655440000",
    )
    system.bind_current_execution_run_id("run-123")

    assert (
        raw_agent.session_state[KONTEXT_SESSION_NAMESPACE][
            KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY
        ]
        == "run-123"
    )


def test_agno_system_bind_current_execution_run_id_clears_stale_session_state() -> None:
    session_state = create_kontext_session_state()
    session_state[KONTEXT_SESSION_NAMESPACE][KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY] = (
        "stale-run"
    )
    raw_agent = SimpleNamespace(session_state=session_state)
    system = _TestAgnoSystem(
        agent=cast("Any", raw_agent),
        runtime_provider=cast("Any", MagicMock()),
        project_id="550e8400-e29b-41d4-a716-446655440000",
    )
    system.bind_current_execution_run_id(None)

    assert (
        KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY
        not in raw_agent.session_state[KONTEXT_SESSION_NAMESPACE]
    )
