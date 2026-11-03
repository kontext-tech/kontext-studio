"""Application composition: agent blueprints + harness resolution.

Two things are deliberately separate:

- **Harness SPI** (:mod:`kontext.agent.harness`) — the plugin contract an
  adapter implements. It lives in the neutral contract package so a harness
  distribution never depends on this application layer.
- **Blueprints** (this module) — how an :class:`~kontext.agent.AgentKind` maps
  to a neutral :class:`~kontext.agent.AgentSpec`. Blueprints own instructions
  and tools and never touch a harness SDK.

``create_agentic_system`` glues them: resolve harness -> resolve blueprint ->
build spec -> materialize. Swapping harnesses is therefore a registry/composition
change, not a change to any blueprint.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from importlib import import_module

from kontext.agent import (
    AgentKind,
    AgentSpec,
    BaseAgenticSystem,
    normalize_agent_kind,
)
from kontext.agent.harness import AgentCreationContext, get_framework_adapter

__all__ = [
    "AgentBlueprint",
    "AgentCreationContext",
    "create_agentic_system",
    "get_agent_blueprint",
    "register_agent_blueprint",
]

AgentBlueprint = Callable[[AgentCreationContext], Awaitable[AgentSpec]]

_BLUEPRINTS: dict[AgentKind, AgentBlueprint] = {}


def register_agent_blueprint(kind: AgentKind | str, blueprint: AgentBlueprint) -> None:
    """Register a neutral blueprint that builds an :class:`AgentSpec` for a kind."""

    _BLUEPRINTS[normalize_agent_kind(kind)] = blueprint


_BLUEPRINTS_LOADED = False


def _ensure_blueprints_loaded() -> None:
    global _BLUEPRINTS_LOADED
    if not _BLUEPRINTS_LOADED:
        _BLUEPRINTS_LOADED = True
        import_module("kontext.agentic.blueprints")


def get_agent_blueprint(kind: AgentKind | str | None) -> AgentBlueprint:
    """Return the registered blueprint for an agent kind."""

    _ensure_blueprints_loaded()
    normalized = normalize_agent_kind(kind)
    try:
        return _BLUEPRINTS[normalized]
    except KeyError as exc:
        raise LookupError(f"No agent blueprint registered for kind: {normalized!r}") from exc


async def create_agentic_system(
    *,
    context: AgentCreationContext,
    agent_type: AgentKind | str | None,
    framework: str | None = None,
) -> BaseAgenticSystem:
    """Create an agentic system using the selected framework harness."""

    harness = get_framework_adapter(framework)
    blueprint = get_agent_blueprint(agent_type)
    spec = await blueprint(context)
    return await harness.create_agentic_system(spec=spec, context=context)
