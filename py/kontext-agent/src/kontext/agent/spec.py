"""Framework-neutral agent specifications.

An :class:`AgentSpec` is the declarative description of an agentic system: what
it is (descriptor + instructions), what it can do (tools), and how it composes
(``members``). It carries no harness objects.

The key modelling decision is that *composition is a field, not a type*. A
coordinator/team is simply an ``AgentSpec`` whose ``members`` is non-empty:

- ``members == ()``  -> a leaf agent (Agno ``Agent``, ADK ``LlmAgent``)
- ``members != ()``  -> a coordinating agent (Agno ``Team``,
  ADK ``LlmAgent(sub_agents=...)``)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .metadata import AgentDescriptor, AgentKind
from .toolkits import FrameworkToolkit

if TYPE_CHECKING:
    from kontext.common.contracts import AgentConfig

# A tool is either a neutral toolkit or a bare callable with runtime metadata.
AgentTool = FrameworkToolkit | Callable[..., Any]


@dataclass(frozen=True)
class AgentSpec:
    """Declarative, harness-neutral description of an agentic system."""

    descriptor: AgentDescriptor
    instructions: str
    role: str | None = None
    tools: tuple[AgentTool, ...] = ()
    members: tuple[AgentSpec, ...] = ()
    # Neutral intent flags. Each harness realizes these its own way:
    # Agno maps them to Team kwargs; ADK maps them to sub-agent configuration.
    share_member_interactions: bool = False
    add_member_history: bool = False
    persist_member_responses: bool = False
    session_state: dict[str, Any] | None = None
    add_session_state_to_context: bool = False
    # Per-spec runtime-config override (e.g. a member built with a different
    # task profile). ``None`` inherits the composing context's config.
    config: AgentConfig | None = None


def normalize_agent_kind(agent_type: AgentKind | str | None) -> AgentKind:
    """Normalize an agent-type input to a canonical :class:`AgentKind`.

    Coordinating kinds (the legacy ``team`` string) normalize to
    :class:`AgentKind.COORDINATOR`. ``None`` also means the coordinator, which
    is the default chat entrypoint.
    """
    if isinstance(agent_type, AgentKind):
        normalized = agent_type
    elif isinstance(agent_type, str) and agent_type:
        try:
            normalized = AgentKind(agent_type)
        except ValueError:
            normalized = AgentKind.COORDINATOR
    else:
        normalized = AgentKind.COORDINATOR

    if normalized is AgentKind.TEAM:
        return AgentKind.COORDINATOR
    return normalized


def collect_tools(specs: Sequence[AgentSpec]) -> list[AgentTool]:
    """Flatten tools across a spec and its members (breadth-first)."""
    tools: list[AgentTool] = []
    queue: list[AgentSpec] = list(specs)
    while queue:
        spec = queue.pop(0)
        tools.extend(spec.tools)
        queue.extend(spec.members)
    return tools
