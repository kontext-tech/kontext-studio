"""Internal agent metadata models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentKind(StrEnum):
    SQL = "sql"
    CHART = "chart"
    NOTEBOOK = "notebook"
    PYTHON = "python"
    # A coordinating agent that owns member agents. This replaces the old
    # "team" concept: "team" is a harness detail (Agno `Team`), not a neutral
    # runtime type. `TEAM` is kept as an alias so persisted agent-type strings
    # and existing call sites keep resolving.
    COORDINATOR = "team"
    TEAM = "team"


@dataclass(frozen=True)
class AgentDescriptor:
    id: AgentKind | str
    name: str
    icon: str
    description: str
