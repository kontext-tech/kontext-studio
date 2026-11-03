"""Harness SPI: the contract every agent-framework adapter implements.

This module is the *plugin boundary*. A harness distribution (``kontext-harness-
agno``, a future ADK adapter, ...) imports only this module (plus the neutral
runtime primitives in :mod:`kontext.agent`) to:

- receive an :class:`AgentCreationContext` describing what to materialize,
- register itself through the ``kontext.agent_harnesses`` entry-point group,
- hand back a :class:`~kontext.agent.BaseAgenticSystem`.

Blueprints — how an :class:`~kontext.agent.AgentKind` maps to an
:class:`~kontext.agent.AgentSpec` — are application concerns and live in
``kontext-agentic``. Keeping the two registries apart is what stops a harness
adapter from depending on the whole application layer.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Protocol

from kontext.common.constants import ModelEnvVars

from .persistence import SessionPersistence
from .spec import AgentSpec
from .system import BaseAgenticSystem

if TYPE_CHECKING:
    from kontext.common.contracts import AgentConfig, ModelRuntime
    from kontext.common.protocols import AgentRuntimeProviderProtocol
    from kontext.schema import (
        AttachedDataSource,
        ProjectModel,
    )

__all__ = [
    "HARNESS_ENTRY_POINT_GROUP",
    "AgentCreationContext",
    "AgentFrameworkAdapter",
    "get_framework_adapter",
    "get_harness_loggers",
    "register_framework_adapter",
    "seed_harness_logger_env",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentCreationContext:
    """Framework-neutral context required to construct an agentic system."""

    config: AgentConfig
    project: ProjectModel
    runtime_provider: AgentRuntimeProviderProtocol
    # Binding plus run-scoped credentials, resolved by composition. Adapters
    # consume it instead of reading the process-global model store.
    model: ModelRuntime
    # Platform-owned run-state store. The composition root builds it (it owns
    # the storage implementation); adapters only receive the port.
    session_persistence: SessionPersistence
    session_id: str | None = None
    user_id: str | None = None
    query_session_id: str | None = None
    catalog_connection_id: str | None = None
    default_namespace: str | None = None
    default_entity_id: str | None = None
    engine_type: str | None = None
    attached_data_sources: list[AttachedDataSource] | None = None
    attached_data_summary: str | None = None


class AgentFrameworkAdapter(Protocol):
    """Contract for framework-specific agent-system harnesses."""

    name: str

    def loggers(self) -> tuple[str, ...]:
        """Logger names owned by this harness, for logging normalization."""
        ...

    async def create_agentic_system(
        self,
        *,
        spec: AgentSpec,
        context: AgentCreationContext,
    ) -> BaseAgenticSystem: ...


class AgentHarnessRegistry:
    """Registry of framework harnesses."""

    def __init__(self) -> None:
        self._adapters: dict[str, AgentFrameworkAdapter] = {}
        self._default_name: str | None = None

    def register(
        self,
        adapter: AgentFrameworkAdapter,
        *,
        make_default: bool = False,
    ) -> None:
        self._adapters[adapter.name] = adapter
        if make_default or self._default_name is None:
            self._default_name = adapter.name

    def get(self, name: str | None = None) -> AgentFrameworkAdapter:
        adapter_name = name or self._default_name
        if adapter_name is None:
            raise LookupError("No agent framework adapter has been registered")
        try:
            return self._adapters[adapter_name]
        except KeyError as exc:
            raise LookupError(f"Unknown agent framework adapter: {adapter_name!r}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))


# Entry-point group a harness distribution registers under. The Agno harness is
# declared in its own pyproject; a future `kontext-harness-adk` package
# registers the same way and becomes selectable via KONTEXT_AGENT_FRAMEWORK
# without editing this module.
HARNESS_ENTRY_POINT_GROUP = "kontext.agent_harnesses"
_HARNESS_REGISTRY = AgentHarnessRegistry()


def _default_framework_name() -> str:
    return os.getenv(ModelEnvVars.AGENT_FRAMEWORK, "agno")


def _register_adapter_object(obj: object, name: str) -> None:
    """Register a harness produced by an entry point or module lookup."""

    adapter = obj() if isinstance(obj, type) else obj
    adapter_name = getattr(adapter, "name", name)
    if not hasattr(adapter, "create_agentic_system"):
        return
    if adapter_name not in _HARNESS_REGISTRY.names():
        _HARNESS_REGISTRY.register(adapter)  # type: ignore[arg-type]


def _load_harness_entry_points() -> None:
    """Register harness adapters declared via package entry points.

    Re-runs on every call: the scan and ``load()`` are cheap after the first
    import, registration is guarded per name, and a memo flag would let stale
    state (or a test-patched registry) hide from later lookups.
    """
    for entry_point in entry_points(group=HARNESS_ENTRY_POINT_GROUP):
        try:
            if entry_point.name in _HARNESS_REGISTRY.names():
                continue
            _register_adapter_object(entry_point.load(), entry_point.name)
        except Exception:  # pragma: no cover - defensive: a bad plugin must not break startup
            logger.warning("Failed to load agent harness entry point %s", entry_point.name)


def register_framework_adapter(
    adapter: AgentFrameworkAdapter,
    *,
    make_default: bool = False,
) -> None:
    """Register a framework harness implementation."""

    _HARNESS_REGISTRY.register(adapter, make_default=make_default)


def get_framework_adapter(name: str | None = None) -> AgentFrameworkAdapter:
    """Return a registered framework harness by name.

    Harnesses are discovered through the ``kontext.agent_harnesses`` entry
    point group; an unknown name raises ``LookupError``.
    """

    framework_name = name or _default_framework_name()
    _load_harness_entry_points()
    return _HARNESS_REGISTRY.get(framework_name)


def get_harness_loggers(framework: str | None = None) -> tuple[str, ...]:
    """Return the active harness's logger names for logging normalization.

    Used by composition roots to seed ``KONTEXT_AGENT_FRAMEWORK_LOGGERS`` so the
    common logging layer does not need to know any harness by name.
    """

    return get_framework_adapter(framework).loggers()


def seed_harness_logger_env(framework: str | None = None) -> None:
    """Merge the active harness's logger names into the logging env var.

    Composition roots call this before ``configure_structured_logging`` so the
    common logging layer stays harness-neutral. Callers do not need the
    application layer — only this contract module.
    """

    existing = {
        name.strip()
        for name in os.getenv(ModelEnvVars.AGENT_FRAMEWORK_LOGGERS, "").split(",")
        if name.strip()
    }
    merged = sorted(existing | set(get_harness_loggers(framework)))
    os.environ[ModelEnvVars.AGENT_FRAMEWORK_LOGGERS] = ",".join(merged)
