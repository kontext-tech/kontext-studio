"""Wire the Agno adapter into the neutral conformance suite.

The scenarios/assertions live in `kontext.agent.conformance` (no harness SDK);
this module only provides the adapter plumbing: a deterministic scripted Agno
model interpreting the scenario script, tool adaptation, and agent
materialization. Every other adapter dist can reuse the same pattern, which is
what makes conformance an apples-to-apples verification of the neutral
runtime contract.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import AsyncIterator, Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest
from agno.models.base import Model
from agno.models.response import ModelResponse

from kontext.agent import (
    AgentDescriptor,
    AgentKind,
    BaseAgenticSystem,
    FrameworkToolkit,
    InMemorySessionPersistence,
    SessionPersistence,
)
from kontext.agent.conformance import (
    ModelStep,
    Scenario,
    assert_coordinator_delegation_contract,
    assert_hitl_pause_and_resume_contract,
    assert_leaf_streaming_contract,
    assert_missing_argument_contract,
    assert_persistence_reflection_contract,
    assert_restart_recovery_contract,
    assert_tool_call_limit_contract,
    assert_tool_call_roundtrip_contract,
    make_scenario_tool,
)
from kontext.agent.tools import create_tool_registry, register_tools_from_callables
from kontext.common.constants.tool_names import DELEGATION_TOOL_NAMES
from kontext.common.contracts import AgentConfig, ModelRuntime, ResolvedModelConfig
from kontext.harness.agno import materialize
from kontext.harness.agno.storage import NeutralBackedDb
from kontext.harness.agno.system import AgnoAgenticSystem

_PROJECT_ID = "1eb96811-39fe-47a4-7e25-08de0be1d149"


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


@pytest.fixture(autouse=True)
def _full_tool_call_visibility(monkeypatch: pytest.MonkeyPatch):
    """Conformance scenarios observe the full client-visibility surface.

    Tool-call visibility policy is product behavior (pinned by agentic tests);
    the conformance contract inspects tool events, so this module pins the
    `full` policy explicitly.
    """
    monkeypatch.setenv("PROJECT_AGENT_TOOL_CALL_CLIENT_POLICY", "full")


@pytest.fixture(autouse=True)
def _isolated_stream_executor(monkeypatch: pytest.MonkeyPatch):
    """Use a per-test stream pool and reap its thread at teardown.

    Mirrors `test_agno_hitl_notebook.py`: the production pool is a process-global
    singleton whose idle worker would otherwise surface in live-thread checks.
    """
    import kontext.harness.agno.run as run_module

    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="agno-conformance")
    monkeypatch.setattr(run_module, "_agent_stream_executor", executor)
    yield
    executor.shutdown(wait=True, cancel_futures=True)


@dataclass
class _ScriptedScenarioModel(Model):
    """Interpret a conformance `Scenario` script as an Agno model."""

    script: tuple[Any, ...] = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        self._step = 0

    def _next(self) -> ModelResponse:
        steps = self.script
        if self._step < len(steps):
            step = steps[self._step]
            self._step += 1
            if step.final_text is not None:
                return ModelResponse(content=step.final_text)
            return ModelResponse(
                content="",
                tool_calls=[
                    {
                        "id": f"call-{self._step}",
                        "type": "function",
                        "function": {
                            "name": step.tool_name,
                            "arguments": json.dumps(step.arguments or {}),
                        },
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


def _member_agent_id(member_name: str) -> str:
    return f"agent-1-{member_name}"


def _combined_script(scenario: Scenario) -> tuple[Any, ...]:
    """Merge the coordinator/member scripts into one deterministic sequence.

    The scripted model is shared across the coordinator and its members
    (adapter-owned scripting), so the combined script follows the real call
    order: coordinator steps up to (and including) the delegation, the member's
    script, then the coordinator's remaining steps. The delegation step's
    logical member name is rewritten to the materialized member agent id.
    """
    if not scenario.members:
        return scenario.script
    assert len(scenario.members) == 1, "this adapter's scripted model supports one member"
    member = scenario.members[0]
    steps = list(scenario.script)
    delegate_index = next(
        (i for i, step in enumerate(steps) if step.tool_name in DELEGATION_TOOL_NAMES),
        None,
    )
    assert delegate_index is not None, "coordinator scenarios must script a delegation step"
    merged = [*steps[: delegate_index + 1], *member.script, *steps[delegate_index + 1 :]]
    return tuple(
        dataclasses.replace(
            step,
            arguments={**(step.arguments or {}), "member_id": _member_agent_id(member.name)},
        )
        if step.arguments and step.arguments.get("member_id") == member.name
        else step
        for step in merged
    )


def _build_system(
    scenario: Scenario,
    *,
    monkeypatch: pytest.MonkeyPatch,
    persistence: SessionPersistence | None = None,
    store: InMemorySessionPersistence | None = None,
) -> BaseAgenticSystem:
    """Materialize one scenario as an Agno-backed system (the adapter's role).

    `store` is the InMemorySessionPersistence the harness-state blob persists
    into; passing the SAME store across system builds emulates a process
    restart (fresh agno agent + facade, durable store retained)."""
    model = _ScriptedScenarioModel(id="scripted", script=_combined_script(scenario))
    monkeypatch.setattr(materialize, "create_model", lambda **_: model)
    # The facade and the platform-facing port must share one store, otherwise
    # a scenario's snapshot assertions would read an unrelated backend.
    shared_store = store if store is not None else persistence
    if shared_store is None:
        shared_store = InMemorySessionPersistence()

    all_tools = [tool.callable for tool in scenario.tools]
    for member in scenario.members:
        all_tools.extend(tool.callable for tool in member.tools)
    tool_registry = register_tools_from_callables(
        all_tools,
        registry=create_tool_registry(namespace="agno"),
    )
    config_kwargs: dict[str, Any] = {"summary": False}
    if scenario.tool_call_limit is not None:
        config_kwargs["tool_call_limit"] = scenario.tool_call_limit
    config = AgentConfig(**config_kwargs)
    session_db = NeutralBackedDb(shared_store)

    if scenario.members:
        members: list[Any] = [
            materialize.create_agno_agent(
                agent_id=_member_agent_id(member.name),
                name=member.name,
                tools=(
                    [
                        FrameworkToolkit(
                            name=f"conformance-{member.name}",
                            tools=[tool.callable for tool in member.tools],
                        )
                    ]
                    if member.tools
                    else []
                ),
                instructions=member.instruction,
                config=config,
                db=session_db,
                model=_model_runtime(),
                session_id=scenario.session_id,
                user_id=scenario.user_id,
            )
            for member in scenario.members
        ]
        agent = materialize.create_agno_team(
            team_id="agent-1",
            name="Coordinator",
            members=members,
            instructions=scenario.instruction,
            config=config,
            db=session_db,
            model=_model_runtime(),
            session_id=scenario.session_id,
            user_id=scenario.user_id,
            share_member_interactions=True,
            tools=(
                [
                    FrameworkToolkit(
                        name="conformance",
                        tools=[tool.callable for tool in scenario.tools],
                    )
                ]
                if scenario.tools
                else None
            ),
        )
    else:
        agent = materialize.create_agno_agent(
            agent_id="agent-1",
            name="Agent",
            tools=[FrameworkToolkit(name="conformance", tools=list(all_tools))],
            instructions=scenario.instruction,
            config=config,
            db=session_db,
            model=_model_runtime(),
            session_id=scenario.session_id,
            user_id=scenario.user_id,
        )
    if scenario.tool_call_limit is not None:
        assert agent.tool_call_limit == scenario.tool_call_limit
    return AgnoAgenticSystem(
        agent,
        runtime_provider=MagicMock(),
        project_id=_PROJECT_ID,
        tool_registry=tool_registry,
        descriptor=AgentDescriptor(
            id=AgentKind.SQL,
            name="Conformance System",
            description="Adapter under conformance test",
            icon="Conformance",
        ),
        persistence=persistence,
        session_db=session_db,
    )


def _pending_system_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[Scenario], tuple[BaseAgenticSystem, SessionPersistence]]:
    def build_with_store(scenario: Scenario) -> tuple[BaseAgenticSystem, SessionPersistence]:
        store = InMemorySessionPersistence()
        system = _build_system(
            scenario,
            monkeypatch=monkeypatch,
            persistence=store,
            store=store,
        )
        return system, store

    return build_with_store


def _pending_scenario() -> Scenario:
    """A scenario whose script pauses on an external-execution tool."""
    recorded: list[str] = []
    return Scenario(
        name="persistence-reflection",
        session_id="persist-session",
        tools=(
            make_scenario_tool(recorded, "conf_search_catalog"),
            make_scenario_tool(recorded, "conf_execute_python_code", external_execution=True),
        ),
        script=(
            ModelStep.call("conf_execute_python_code", notebook_id="nb-1"),
            ModelStep.done(),
        ),
        recorded_calls=recorded,
    )


def _conformance_builder(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a scenario -> AgnoAgenticSystem factory."""

    def build(scenario: Scenario) -> BaseAgenticSystem:
        return _build_system(scenario, monkeypatch=monkeypatch)

    return build


@pytest.mark.asyncio
async def test_conformance_leaf_streaming(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _conformance_builder(monkeypatch)
    await assert_leaf_streaming_contract(builder)


@pytest.mark.asyncio
async def test_conformance_tool_call_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _conformance_builder(monkeypatch)
    await assert_tool_call_roundtrip_contract(builder)


@pytest.mark.asyncio
async def test_conformance_missing_argument(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _conformance_builder(monkeypatch)
    await assert_missing_argument_contract(builder)


@pytest.mark.asyncio
async def test_conformance_tool_call_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _conformance_builder(monkeypatch)
    await assert_tool_call_limit_contract(builder, limit=1)


@pytest.mark.asyncio
async def test_conformance_hitl_pause_and_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    builder = _conformance_builder(monkeypatch)
    await assert_hitl_pause_and_resume_contract(builder)


@pytest.mark.asyncio
async def test_conformance_persistence_reflection(monkeypatch: pytest.MonkeyPatch) -> None:
    build_with_store = _pending_system_builder(monkeypatch)
    await assert_persistence_reflection_contract(build_with_store)


@pytest.mark.asyncio
async def test_conformance_coordinator_delegation(monkeypatch: pytest.MonkeyPatch) -> None:
    build_with_store = _pending_system_builder(monkeypatch)
    await assert_coordinator_delegation_contract(build_with_store)


@pytest.mark.asyncio
async def test_conformance_restart_recovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """DoD scenario: a fresh process resumes the paused run from the neutral
    store (new agno agent + facade, same durable store). The scripted model is
    rebuilt per system; the recovery build continues where the paused run left
    off (the client's tool result is in history, so the model answers without
    re-calling the tool)."""
    import dataclasses

    shared_store = InMemorySessionPersistence()
    recorded: list[str] = []
    initial_script = (
        ModelStep.call("conf_execute_python_code", notebook_id="nb-9"),
        ModelStep.done(),
    )
    scenario = Scenario(
        name="restart-recovery",
        session_id="restart-recovery-session",
        tools=(make_scenario_tool(recorded, "conf_execute_python_code", external_execution=True),),
        script=initial_script,
        recorded_calls=recorded,
    )

    build_count = {"n": 0}

    def build() -> BaseAgenticSystem:
        build_count["n"] += 1
        # Fresh system, fresh scripted model: the recovery build must see the
        # post-pause conversation state (tool executed) and answer.
        script = initial_script if build_count["n"] == 1 else (ModelStep.done(),)
        return _build_system(
            dataclasses.replace(scenario, script=script),
            monkeypatch=monkeypatch,
            persistence=shared_store,
            store=shared_store,
        )

    await assert_restart_recovery_contract(build)
