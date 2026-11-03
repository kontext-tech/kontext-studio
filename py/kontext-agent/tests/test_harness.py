"""Tests for the harness SPI (registry, default selection, entry points)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from kontext.agent import BaseAgenticSystem, InMemorySessionPersistence, StreamOptions
from kontext.agent import harness as agent_harness

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
            description="Stub agent for harness tests",
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
    return agent_harness.AgentCreationContext(
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


def test_registry_uses_first_adapter_as_default() -> None:
    registry = agent_harness.AgentHarnessRegistry()
    alpha = DummyAdapter("alpha")
    beta = DummyAdapter("beta")

    registry.register(alpha)
    registry.register(beta)

    assert registry.get() is alpha
    assert registry.get("beta") is beta
    assert registry.names() == ("alpha", "beta")


def test_registry_can_override_default_adapter() -> None:
    registry = agent_harness.AgentHarnessRegistry()
    alpha = DummyAdapter("alpha")
    beta = DummyAdapter("beta")

    registry.register(alpha)
    registry.register(beta, make_default=True)

    assert registry.get() is beta


def test_registry_raises_for_missing_adapter() -> None:
    registry = agent_harness.AgentHarnessRegistry()

    with pytest.raises(LookupError, match="No agent framework adapter"):
        registry.get()

    registry.register(DummyAdapter("alpha"))
    with pytest.raises(LookupError, match="Unknown agent framework adapter"):
        registry.get("missing")


def test_get_framework_adapter_resolves_registered_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = agent_harness.AgentHarnessRegistry()
    monkeypatch.setattr(agent_harness, "_HARNESS_REGISTRY", registry)
    monkeypatch.setattr(agent_harness, "_default_framework_name", lambda: "fake")
    monkeypatch.setattr(agent_harness, "_load_harness_entry_points", lambda: None)

    agent_harness.register_framework_adapter(DummyAdapter("fake"))

    adapter = agent_harness.get_framework_adapter()

    assert adapter.name == "fake"


def test_get_framework_adapter_lazy_loads_via_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entry-point harnesses register without editing this module."""

    class ZeroArgAdapter:
        # `_register_adapter_object` instantiates the loaded class with no
        # arguments, so the test double must be zero-arg constructible.
        name = "fake"

        def loggers(self) -> tuple[str, ...]:
            return ("fake",)

        async def create_agentic_system(self, *, spec, context):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    registry = agent_harness.AgentHarnessRegistry()
    monkeypatch.setattr(agent_harness, "_HARNESS_REGISTRY", registry)
    monkeypatch.setattr(agent_harness, "_default_framework_name", lambda: "fake")

    class _FakeEntryPoint:
        name = "fake"

        def load(self):
            return ZeroArgAdapter

    monkeypatch.setattr(
        agent_harness,
        "entry_points",
        lambda group: (
            [_FakeEntryPoint()] if group == agent_harness.HARNESS_ENTRY_POINT_GROUP else []
        ),
    )

    adapter = agent_harness.get_framework_adapter()

    assert adapter.name == "fake"


def test_seed_harness_logger_env_merges_logger_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("KONTEXT_AGENT_FRAMEWORK_LOGGERS", raising=False)
    monkeypatch.setattr(agent_harness, "_HARNESS_REGISTRY", agent_harness.AgentHarnessRegistry())
    monkeypatch.setattr(agent_harness, "_load_harness_entry_points", lambda: None)
    monkeypatch.setattr(agent_harness, "_default_framework_name", lambda: "fake")
    agent_harness.register_framework_adapter(DummyAdapter("fake"))

    agent_harness.seed_harness_logger_env()

    assert "fake" in agent_harness.get_harness_loggers()
