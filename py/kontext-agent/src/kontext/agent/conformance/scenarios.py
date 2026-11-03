"""Adapter conformance suite (neutral contract layer).

Every agent harness adapter must satisfy the same observable runtime contract:
how runs stream, how tool calls are surfaced, how the tool-call budget is
enforced, and how externally-executed (HITL) tools pause and resume. This
package encodes that contract as scenarios plus assertion helpers so any
adapter can be verified by running the same suite.

Adapters wire themselves in by providing a *builder* — a callable that turns a
:class:`Scenario` into a `BaseAgenticSystem` with deterministic script-driven
model responses. Model scripting is deliberately adapter-owned (each harness
has its own model plumbing); the neutral layer owns scenario semantics and the
assertions.

Reference wiring: `py/kontext-harness-agno/tests/test_conformance.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from kontext.common.constants.tool_names import (
    DELEGATE_TASK_TO_MEMBER_TOOL_NAME,
    DELEGATION_TOOL_NAMES,
)
from kontext.schema import (
    ArtifactType,
    ChatMessage,
    RunEvent,
    RunPausedEventData,
    SimpleRunEvent,
    ToolCall,
    ToolCallCompletedEventData,
    ToolCallResult,
)

from ..context import get_session_state
from ..persistence import SessionPersistence
from ..shared_session_store import SharedSessionStore
from ..system import BaseAgenticSystem, StreamOptions
from ..toolkits import ToolCallable
from ..tools import get_tool_meta, tool_meta

__all__ = [
    "ConformanceBuilder",
    "MakeScenarioTool",
    "ModelStep",
    "RunTrace",
    "Scenario",
    "ScenarioMember",
    "ScenarioTool",
    "assert_coordinator_delegation_contract",
    "assert_hitl_pause_and_resume_contract",
    "assert_leaf_streaming_contract",
    "assert_missing_argument_contract",
    "assert_persistence_reflection_contract",
    "assert_restart_recovery_contract",
    "assert_tool_call_limit_contract",
    "assert_tool_call_roundtrip_contract",
    "collect_events",
    "completed_tool_calls",
    "error_resume_outputs",
    "event_types",
    "make_scenario_tool",
    "make_session_state_read_tool",
    "make_session_state_write_tool",
    "paused_tool_calls",
    "resume_outputs",
    "run_scenario",
]


# ---------------------------------------------------------------------------
# Scenario vocabulary
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScenarioTool:
    """A tool the adapter must expose, declared as plain neutral metadata."""

    name: str
    callable: ToolCallable


@dataclass(frozen=True)
class ModelStep:
    """One deterministic model turn: either a tool call or terminal text."""

    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    final_text: str | None = None

    @classmethod
    def call(cls, tool_name: str, **arguments: Any) -> ModelStep:
        return cls(tool_name=tool_name, arguments=arguments)

    @classmethod
    def done(cls, text: str = "Done.") -> ModelStep:
        return cls(final_text=text)

    @classmethod
    def delegate(cls, member: str, task: str) -> ModelStep:
        """A coordinator delegation step (canonical delegation tool name).

        ``member`` is the scenario's logical member name; each adapter maps it
        to its own member identifier when it materializes the composed system.
        """
        return cls(
            tool_name=DELEGATE_TASK_TO_MEMBER_TOOL_NAME,
            arguments={"member_id": member, "task": task},
        )


@dataclass(frozen=True)
class ScenarioMember:
    """A member agent the coordinator may delegate to (composition contract)."""

    name: str
    instruction: str = "Complete the delegated task using the provided tools."
    tools: tuple[ScenarioTool, ...] = ()
    script: tuple[ModelStep, ...] = ()


@dataclass(frozen=True)
class Scenario:
    """A conformance scenario: tools, script, knobs, and resume phases."""

    name: str
    tools: tuple[ScenarioTool, ...] = ()
    script: tuple[ModelStep, ...] = ()
    # Composition members: non-empty means the scenario is a coordinator.
    members: tuple[ScenarioMember, ...] = ()
    message: str = "Run the task."
    instruction: str = "Complete the task using the provided tools."
    session_id: str = "conformance-session"
    user_id: str = "conformance-user"
    tool_call_limit: int | None = None
    # Resume phases (HITL): each entry is one resume with the given outputs.
    resumes: tuple[tuple[ToolCall, ...], ...] = ()
    # Mutable record of executed tool names (closed over by the tool callables).
    recorded_calls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RunTrace:
    """Events observed for one scenario: initial run plus each resume."""

    initial: tuple[SimpleRunEvent, ...]
    resumed: tuple[tuple[SimpleRunEvent, ...], ...]

    @property
    def all_events(self) -> Iterable[SimpleRunEvent]:
        yield from self.initial
        for phase in self.resumed:
            yield from phase


ConformanceBuilder = Callable[[Scenario], BaseAgenticSystem]

MakeScenarioTool = Callable[[str], ScenarioTool]


# ---------------------------------------------------------------------------
# Scenario tool construction (neutral declarations, adapter-agnostic)
# ---------------------------------------------------------------------------


def make_scenario_tool(
    recorded: list[str],
    name: str,
    *,
    parameters: Sequence[str] = ("query",),
    external_execution: bool = False,
) -> ScenarioTool:
    """Declare a conformance tool; execution appends ``name`` to ``recorded``.

    The callable is generated with explicit ``str`` parameters (``parameters``
    are required, in order) so argument-validation contracts are observable —
    a ``**kwargs`` signature would silently swallow missing arguments. Tools
    return JSON strings (no declared result class) so results ride the neutral
    `ToolCallResult` string root unchanged.

    The metadata is registered into the default tool registry because the
    client-visibility policy resolves `ToolMeta` through it. ``name`` must be
    conformance-unique (``conf_`` prefix) so registrations never collide with
    product tools across test sessions. Conformance scenarios run under the
    adapter's full client-visibility mode so tool-call events are observable.
    """
    payload = json.dumps({"success": True, "tool": name})
    src = (
        f"def {name}({', '.join(f'{param}: str' for param in parameters)}):\n"
        f"    recorded.append({name!r})\n"
        "    return __payload\n"
    )
    namespace: dict[str, Any] = {"recorded": recorded, "__payload": payload, "str": str}
    exec(compile(src, f"<conformance:{name}>", "exec"), namespace)
    tool_callable = namespace[name]

    decorated = tool_meta(
        display_name=name,
        external_execution=external_execution,
        description=f"Conformance tool {name}.",
    )(tool_callable)
    return ScenarioTool(name=name, callable=decorated)


def make_session_state_write_tool(
    recorded: list[str],
    name: str = "conf_publish_member_artifact",
    *,
    alias: str = "latest_member_artifact",
) -> ScenarioTool:
    """Declare a tool that publishes an artifact into shared session state.

    The member side of the composition contract: the coordinator must observe
    what this writes via the same session-state store.
    """

    def publish(artifact_id: str, title: str, run_context: Any = None) -> str:
        store = SharedSessionStore.from_session_state(get_session_state(run_context))
        if store is None:
            recorded.append(f"{name}:no-session-state")
            return json.dumps({"success": False, "error": "session state unavailable"})
        store.upsert_artifact_descriptor(
            artifact_id=artifact_id,
            artifact_type=ArtifactType.DATATABLE,
            title=title,
            row_count=1,
        )
        store.register_artifact_alias(alias, artifact_id)
        recorded.append(name)
        return json.dumps({"success": True, "artifact_id": artifact_id})

    publish.__name__ = name
    publish.__qualname__ = name
    decorated = tool_meta(display_name=name, description=f"Conformance tool {name}.")(publish)
    return ScenarioTool(name=name, callable=decorated)


def make_session_state_read_tool(
    recorded: list[str],
    name: str = "conf_resolve_member_artifact",
    *,
    alias: str = "latest_member_artifact",
) -> ScenarioTool:
    """Declare a tool that resolves an artifact the member published.

    Appends ``<name>:<resolved-artifact-id>`` (or ``:missing``) to ``recorded``
    so the contract can assert cross-agent shared-state visibility.
    """

    def resolve(alias: str, run_context: Any = None) -> str:
        store = SharedSessionStore.from_session_state(get_session_state(run_context))
        resolved = store.resolve_artifact_id(alias) if store is not None else None
        descriptor = (
            store.get_artifact_descriptor(resolved)
            if store is not None and resolved is not None
            else None
        )
        recorded.append(f"{name}:{resolved or 'missing'}")
        return json.dumps(
            {
                "success": resolved is not None,
                "artifact_id": resolved,
                "title": descriptor.title if descriptor is not None else None,
            }
        )

    resolve.__name__ = name
    resolve.__qualname__ = name
    decorated = tool_meta(display_name=name, description=f"Conformance tool {name}.")(resolve)
    return ScenarioTool(name=name, callable=decorated)


# ---------------------------------------------------------------------------
# Execution helpers
# ---------------------------------------------------------------------------


async def collect_events(
    system: BaseAgenticSystem,
    scenario: Scenario,
    *,
    tool_outputs: Sequence[ToolCall] | None = None,
) -> list[SimpleRunEvent]:
    """Stream one run (or resume) from ``system`` for ``scenario``."""
    options = StreamOptions(tool_outputs=tool_outputs)
    return [
        event
        async for event in system.stream_response(
            scenario.message,
            session_id=scenario.session_id,
            user_id=scenario.user_id,
            options=options,
        )
    ]


async def run_scenario(builder: ConformanceBuilder, scenario: Scenario) -> RunTrace:
    """Build one system and drive the scenario's initial run + resume phases."""
    system = builder(scenario)
    initial = await collect_events(system, scenario)
    resumed: list[tuple[SimpleRunEvent, ...]] = []
    for phase_outputs in scenario.resumes:
        resumed.append(tuple(await collect_events(system, scenario, tool_outputs=phase_outputs)))
    return RunTrace(initial=tuple(initial), resumed=tuple(tuple(phase) for phase in resumed))


# ---------------------------------------------------------------------------
# Event inspection helpers
# ---------------------------------------------------------------------------


def event_types(events: Iterable[SimpleRunEvent]) -> list[RunEvent]:
    return [event.event_type for event in events]


def _event_data(event: SimpleRunEvent) -> Any:
    return getattr(event.event_data, "root", None)


def paused_tool_calls(events: Iterable[SimpleRunEvent]) -> list[ToolCall]:
    """Tool calls carried by RUNPAUSED events (the HITL resume payload)."""
    calls: list[ToolCall] = []
    for event in events:
        if event.event_type is not RunEvent.RUNPAUSED:
            continue
        data = _event_data(event)
        if isinstance(data, RunPausedEventData) and data.tool_calls:
            calls.extend(data.tool_calls)
    return calls


def completed_tool_calls(events: Iterable[SimpleRunEvent]) -> list[ToolCall]:
    """Tool calls carried by TOOLCALLCOMPLETED events."""
    calls: list[ToolCall] = []
    for event in events:
        if event.event_type is not RunEvent.TOOLCALLCOMPLETED:
            continue
        data = _event_data(event)
        if isinstance(data, ToolCallCompletedEventData) and data.tool is not None:
            calls.append(data.tool)
    return calls


def resume_outputs(
    tool_calls: Iterable[ToolCall], *, result: str = "external result"
) -> tuple[ToolCall, ...]:
    """Build the client-side resume payload for observed paused calls."""
    return tuple(
        ToolCall(
            tool_call_id=call.tool_call_id,
            tool_name=call.tool_name,
            result=ToolCallResult(root=result),
        )
        for call in tool_calls
    )


def error_resume_outputs(
    tool_calls: Iterable[ToolCall], *, error: str = "sandbox failed"
) -> tuple[ToolCall, ...]:
    """Build the client-side resume payload reporting a client-side failure."""
    return tuple(
        ToolCall(tool_call_id=call.tool_call_id, tool_name=call.tool_name, tool_call_error=error)
        for call in tool_calls
    )


# ---------------------------------------------------------------------------
# Contracts (the adapter conformance suite)
# ---------------------------------------------------------------------------


async def assert_leaf_streaming_contract(builder: ConformanceBuilder) -> RunTrace:
    """A leaf agent must stream a completed run without errors or pauses."""
    scenario = Scenario(name="leaf-streaming", script=(ModelStep.done(),))
    trace = await run_scenario(builder, scenario)
    types = event_types(trace.initial)
    assert RunEvent.RUNCOMPLETED in types, types
    assert RunEvent.RUNERROR not in types, types
    assert RunEvent.RUNPAUSED not in types, types
    return trace


async def assert_tool_call_roundtrip_contract(builder: ConformanceBuilder) -> RunTrace:
    """A scripted tool call must be executed once and surfaced as completed."""
    recorded: list[str] = []
    scenario = Scenario(
        name="tool-roundtrip",
        tools=(
            make_scenario_tool(recorded, "conf_search_catalog"),
            make_scenario_tool(recorded, "conf_execute_sql"),
        ),
        script=(ModelStep.call("conf_search_catalog", query="sales"), ModelStep.done()),
        recorded_calls=recorded,
    )
    trace = await run_scenario(builder, scenario)
    types = event_types(trace.initial)
    assert RunEvent.TOOLCALLCOMPLETED in types, types
    assert RunEvent.RUNCOMPLETED in types, types
    assert RunEvent.RUNERROR not in types, types
    calls = completed_tool_calls(trace.initial)
    assert calls and calls[0].tool_name == "conf_search_catalog"
    assert recorded == ["conf_search_catalog"]
    return trace


async def assert_missing_argument_contract(builder: ConformanceBuilder) -> RunTrace:
    """A tool invoked without required args must run with a structured failure:
    the tool body never executes and the run still completes."""
    recorded: list[str] = []
    scenario = Scenario(
        name="missing-argument",
        tools=(make_scenario_tool(recorded, "conf_search_catalog"),),
        script=(ModelStep.call("conf_search_catalog"), ModelStep.done()),
        recorded_calls=recorded,
    )
    trace = await run_scenario(builder, scenario)
    types = event_types(trace.initial)
    assert RunEvent.TOOLCALLCOMPLETED in types, types
    assert RunEvent.RUNCOMPLETED in types, types
    assert recorded == [], "the tool body must not run on missing args"
    calls = completed_tool_calls(trace.initial)
    assert calls, types
    tool = calls[0]
    root = getattr(tool.result, "root", None) if tool.result else None
    failure_message = tool.tool_call_error or (str(root) if root else "")
    assert "Missing required arguments" in failure_message, (tool.tool_call_error, root)
    return trace


async def assert_tool_call_limit_contract(
    builder: ConformanceBuilder, *, limit: int = 1
) -> RunTrace:
    """The configured tool-call budget must be enforced by the harness."""
    recorded: list[str] = []
    scenario = Scenario(
        name="tool-call-limit",
        tools=(
            make_scenario_tool(recorded, "conf_search_catalog"),
            make_scenario_tool(recorded, "conf_execute_sql"),
        ),
        script=(
            ModelStep.call("conf_search_catalog", query="sales"),
            ModelStep.call("conf_execute_sql", sql="SELECT 1"),
            ModelStep.done(),
        ),
        tool_call_limit=limit,
        recorded_calls=recorded,
    )
    trace = await run_scenario(builder, scenario)
    assert recorded == ["conf_search_catalog"], recorded
    types = event_types(trace.initial)
    assert RunEvent.RUNCOMPLETED in types, types
    return trace


async def assert_hitl_pause_and_resume_contract(builder: ConformanceBuilder) -> RunTrace:
    """External-execution tools pause instead of running the server body, and
    resume to completion with client-produced results (success and failure).

    Verdicts that must hold:
    - the pause carries the pending tool calls (with ids) on the wire event;
    - the tool body never executes server-side;
    - both a success payload and a client-error payload resume to completion.
    """
    traces: list[tuple[SimpleRunEvent, ...]] = []
    for session_id, resume_kind in (
        ("hitl-success-session", "success"),
        ("hitl-error-session", "error"),
    ):
        recorded: list[str] = []
        scenario = Scenario(
            name=f"hitl-{resume_kind}",
            session_id=session_id,
            tools=(
                make_scenario_tool(recorded, "conf_execute_python_code", external_execution=True),
            ),
            script=(
                ModelStep.call("conf_execute_python_code", notebook_id="nb-1", code="print(1)"),
                ModelStep.done(),
            ),
            recorded_calls=recorded,
        )
        system = builder(scenario)
        pause_events = await collect_events(system, scenario)
        pause_types = event_types(pause_events)
        assert RunEvent.RUNPAUSED in pause_types, pause_types
        assert RunEvent.RUNERROR not in pause_types, pause_types
        assert recorded == [], "external-execution tool bodies must not run server-side"

        paused_calls = paused_tool_calls(pause_events)
        assert paused_calls, pause_types
        assert paused_calls[0].tool_name == "conf_execute_python_code"
        assert paused_calls[0].tool_call_id, "paused calls must carry ids for resume"

        outputs = (
            resume_outputs(paused_calls, result=json.dumps({"success": True}))
            if resume_kind == "success"
            else error_resume_outputs(paused_calls, error="sandbox failed")
        )
        resumed = await collect_events(system, scenario, tool_outputs=outputs)
        resumed_types = event_types(resumed)
        assert RunEvent.RUNCOMPLETED in resumed_types, resumed_types
        assert RunEvent.RUNPAUSED not in resumed_types, resumed_types
        assert RunEvent.RUNERROR not in resumed_types, resumed_types
        traces.append(tuple(pause_events) + tuple(resumed))
    return RunTrace(initial=(), resumed=tuple(traces))


async def assert_persistence_reflection_contract(
    build_with_store: Callable[[Scenario], tuple[BaseAgenticSystem, SessionPersistence]],
) -> None:
    """The neutral store must reflect the run (persist-before-surface).

    Verdicts that must hold:
    - a paused run persists the harness blob before the pause is surfaced
      (persist-before-surface rule) and also snapshots the partial
      conversation (store-only history stays intact across a mid-pause reload);
    - a completed run persists the authoritative conversation snapshot in wire
      shape (`ChatMessage` JSON round-trips), including the executed tool call.
    """
    pause_recorded: list[str] = []
    pause_scenario = Scenario(
        name="persist-pause",
        session_id="persist-session",
        tools=(
            make_scenario_tool(pause_recorded, "conf_execute_python_code", external_execution=True),
        ),
        script=(
            ModelStep.call("conf_execute_python_code", notebook_id="nb-1"),
            ModelStep.done(),
        ),
        recorded_calls=pause_recorded,
    )
    system, store = build_with_store(pause_scenario)
    pause_events = await collect_events(system, pause_scenario)
    assert RunEvent.RUNPAUSED in event_types(pause_events)
    assert await store.load_harness_state(pause_scenario.session_id) is not None, (
        "the paused run's harness state must be durable before the pause surfaces"
    )
    paused_snapshot = await store.list_messages(pause_scenario.session_id)
    assert paused_snapshot, "paused run must snapshot the partial conversation"

    complete_recorded: list[str] = []
    complete_scenario = Scenario(
        name="persist-complete",
        session_id="persist-complete-session",
        tools=(make_scenario_tool(complete_recorded, "conf_search_catalog"),),
        script=(
            ModelStep.call("conf_search_catalog", query="sales"),
            ModelStep.done(),
        ),
        recorded_calls=complete_recorded,
    )
    complete_system, complete_store = build_with_store(complete_scenario)
    complete_events = await collect_events(complete_system, complete_scenario)
    assert RunEvent.RUNCOMPLETED in event_types(complete_events)

    persisted = await complete_store.list_messages(complete_scenario.session_id)
    assert persisted, "completed runs must snapshot the conversation"
    assert complete_recorded == ["conf_search_catalog"], complete_recorded
    for record in persisted:
        message = ChatMessage.model_validate_json(record.message_json)
        assert message.id
    flattened = "\n".join(record.message_json for record in persisted)
    assert "conf_search_catalog" in flattened, "the executed tool call must be in history"


def _delegation_wire_names() -> set[str]:
    """Delegation names accepted on the wire: canonical or registered display.

    The canonical names are the contract; the neutral tool registry also
    carries their display labels, which adapters may surface instead (the
    client resolves both to the same delegation UI).
    """
    names = set(DELEGATION_TOOL_NAMES)
    for canonical in DELEGATION_TOOL_NAMES:
        meta = get_tool_meta(canonical)
        if meta is not None and meta.display_name:
            names.add(meta.display_name)
    return names


async def assert_coordinator_delegation_contract(
    build_with_store: Callable[[Scenario], tuple[BaseAgenticSystem, SessionPersistence]],
) -> None:
    """A coordinator composition must honor the delegation contract.

    The scenario declares one member; the adapter scripts its composer so the
    coordinator delegates, the member works, and the coordinator reads what the
    member published. Verdicts that must hold:

    - the run completes with no error/pause and the delegation tool call is
      surfaced on the wire;
    - the delegated member executes its own tools (membership is real, not
      simulated) and its activity reaches the live stream;
    - shared session state written by the member is visible to the
      coordinator's subsequent tool call (same store across members);
    - history replay carries the coordinator's delegation call and the
      member's output (`persist_member_responses`); member-internal tool
      messages stay harness-internal.
    """
    recorded: list[str] = []
    member_lookup = make_scenario_tool(recorded, "conf_member_lookup")
    member_publish = make_session_state_write_tool(recorded)
    coordinator_read = make_session_state_read_tool(recorded)

    member = ScenarioMember(
        name="member-1",
        tools=(member_lookup, member_publish),
        script=(
            ModelStep.call("conf_member_lookup", query="sales"),
            ModelStep.call(
                member_publish.name,
                artifact_id="artifact-member-1",
                title="Member artifact",
            ),
            ModelStep.done("Member finished."),
        ),
    )
    scenario = Scenario(
        name="coordinator-delegation",
        session_id="coordinator-session",
        tools=(coordinator_read,),
        members=(member,),
        script=(
            ModelStep.delegate(member.name, "Look up sales and publish the artifact."),
            ModelStep.call(coordinator_read.name, alias="latest_member_artifact"),
            ModelStep.done("Coordinator done."),
        ),
        recorded_calls=recorded,
    )
    system, store = build_with_store(scenario)
    events = await collect_events(system, scenario)
    types = event_types(events)
    assert RunEvent.RUNCOMPLETED in types, types
    assert RunEvent.RUNERROR not in types, types
    assert RunEvent.RUNPAUSED not in types, types

    calls = completed_tool_calls(events)
    delegation_names = _delegation_wire_names()
    delegation = [call.tool_name for call in calls if call.tool_name in delegation_names]
    assert delegation, [call.tool_name for call in calls]
    assert any(call.tool_name == "conf_member_lookup" for call in calls), [
        call.tool_name for call in calls
    ]

    assert "conf_member_lookup" in recorded, recorded
    assert member_publish.name in recorded, recorded

    reads = [entry for entry in recorded if entry.startswith(f"{coordinator_read.name}:")]
    assert reads and reads[0].endswith(":artifact-member-1"), recorded

    persisted = await store.list_messages(scenario.session_id)
    flattened = "\n".join(record.message_json for record in persisted)
    assert "delegate_task_to_member" in flattened, "delegation must persist in history"
    assert "Member finished." in flattened, "member output must persist in history"


async def assert_restart_recovery_contract(build: Callable[[], BaseAgenticSystem]) -> None:
    """A paused run must be resumable by a fresh system over the same store.

    The builder must return a *new* system (fresh harness-internal state) on
    every call while the durable store identity persists across calls — the
    honest in-process equivalent of a process restart. Verdicts that must
    hold:

    - the run pauses on an external-execution tool (run id + pending calls
      surfaced on the wire);
    - the recovery build has no prior in-process knowledge of the session yet
      still resumes it to completion with the client's tool outputs;
    - no second pause or error is emitted during the resumed turn.
    """
    recorded: list[str] = []
    scenario = Scenario(
        name="restart-recovery",
        session_id="restart-recovery-session",
        tools=(make_scenario_tool(recorded, "conf_execute_python_code", external_execution=True),),
        script=(
            ModelStep.call("conf_execute_python_code", notebook_id="nb-9"),
            ModelStep.done(),
        ),
        recorded_calls=recorded,
    )

    paused_system = build()
    pause_events = await collect_events(paused_system, scenario)
    pause_types = event_types(pause_events)
    assert RunEvent.RUNPAUSED in pause_types, pause_types
    paused_calls = paused_tool_calls(pause_events)
    assert paused_calls, "the pause must carry pending tool calls"

    # "Restart": a fresh system whose durable store holds the paused run but
    # whose in-process harness state is empty.
    recovered_system = build()
    outputs = resume_outputs(paused_calls, result=json.dumps({"success": True}))
    resumed = await collect_events(recovered_system, scenario, tool_outputs=outputs)
    resumed_types = event_types(resumed)
    assert RunEvent.RUNCOMPLETED in resumed_types, resumed_types
    assert RunEvent.RUNPAUSED not in resumed_types, resumed_types
    assert RunEvent.RUNERROR not in resumed_types, resumed_types
