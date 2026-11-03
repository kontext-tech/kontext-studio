"""Tests for the application composition layer (blueprints + dispatch)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from kontext.agent import BaseAgenticSystem, InMemorySessionPersistence, StreamOptions
from kontext.agent import harness as agent_harness
from kontext.agentic import adapters

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from kontext.agent import AgentSpec
    from kontext.agent.harness import AgentCreationContext
    from kontext.common.contracts import AgentConfig, ModelRuntime
    from kontext.common.protocols import AgentRuntimeProviderProtocol
    from kontext.schema import ProjectModel, SimpleRunEvent


class StubAgenticSystem(BaseAgenticSystem):
    agent_definition = cast(
        "Any",
        SimpleNamespace(
            name="Stub Agent",
            description="Stub agent for adapter tests",
            icon="StubIcon",
        ),
    )

    async def stream_response(
        self,
        message: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        options: StreamOptions | None = None,
    ) -> AsyncGenerator[SimpleRunEvent, None]:
        _ = (message, session_id, user_id, options)
        if False:
            yield cast("SimpleRunEvent", None)

    def get_token_usage(self, session_id: str | None = None) -> tuple[int, int] | None:
        _ = session_id
        return None


def _build_context() -> AgentCreationContext:
    return adapters.AgentCreationContext(
        config=cast("AgentConfig", SimpleNamespace()),
        project=cast("ProjectModel", SimpleNamespace(id="project-id")),
        runtime_provider=cast("AgentRuntimeProviderProtocol", SimpleNamespace()),
        model=cast("ModelRuntime", SimpleNamespace()),
        session_persistence=InMemorySessionPersistence(),
    )


def _build_spec() -> AgentSpec:
    from kontext.agent import AgentDescriptor, AgentKind, AgentSpec

    return AgentSpec(
        descriptor=AgentDescriptor(
            id=AgentKind.SQL, name="Stub", icon="StubIcon", description="stub"
        ),
        instructions="do things",
    )


async def _stub_blueprint(_context: AgentCreationContext) -> AgentSpec:
    return _build_spec()


class DummyAdapter:
    def __init__(self, name: str, result: BaseAgenticSystem | None = None) -> None:
        self.name = name
        self.result = result if result is not None else StubAgenticSystem()
        self.calls: list[tuple[AgentSpec, AgentCreationContext]] = []

    def loggers(self) -> tuple[str, ...]:
        return (self.name,)

    async def create_agentic_system(
        self,
        *,
        spec: AgentSpec,
        context: AgentCreationContext,
    ) -> BaseAgenticSystem:
        self.calls.append((spec, context))
        return self.result


@pytest.fixture()
def empty_blueprints(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the module-global blueprint registry from the real catalogue."""
    monkeypatch.setattr(adapters, "_BLUEPRINTS", {})
    monkeypatch.setattr(adapters, "_BLUEPRINTS_LOADED", True)


def test_blueprint_registry_normalizes_legacy_kinds(empty_blueprints: None) -> None:
    adapters.register_agent_blueprint("sql", _stub_blueprint)
    adapters.register_agent_blueprint("team", _stub_blueprint)

    assert adapters.get_agent_blueprint("sql") is _stub_blueprint
    # Legacy/coordinating strings normalize onto the coordinator blueprint.
    assert adapters.get_agent_blueprint("unified") is _stub_blueprint


def test_blueprint_registry_raises_for_unknown_kind(empty_blueprints: None) -> None:
    with pytest.raises(LookupError, match="No agent blueprint registered"):
        adapters.get_agent_blueprint("sql")


@pytest.mark.asyncio
async def test_create_agentic_system_dispatches_to_selected_adapter(
    monkeypatch: pytest.MonkeyPatch, empty_blueprints: None
) -> None:
    registry = agent_harness.AgentHarnessRegistry()
    primary = DummyAdapter("primary")
    secondary = DummyAdapter("secondary", result=StubAgenticSystem(name="Secondary"))
    registry.register(primary, make_default=True)
    registry.register(secondary)
    adapters.register_agent_blueprint("sql", _stub_blueprint)
    monkeypatch.setattr(agent_harness, "_HARNESS_REGISTRY", registry)
    monkeypatch.setattr(agent_harness, "_default_framework_name", lambda: "primary")
    monkeypatch.setattr(agent_harness, "_load_harness_entry_points", lambda: None)

    context = _build_context()

    result = await adapters.create_agentic_system(
        context=context,
        agent_type="sql",
        framework="secondary",
    )

    assert result is secondary.result
    assert primary.calls == []
    assert len(secondary.calls) == 1
    assert secondary.calls[0][1] is context
