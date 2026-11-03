"""Shared context models for query orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from kontext.schema import QuerySessionModel


@dataclass(frozen=True)
class QueryAccessContext:
    """Transport-agnostic authorization context for query workflows."""

    project_id: UUID
    user_id: UUID
    actor_label: str | None = None
    effective_owner_id: UUID | None = None
    project_scope: bool = False
    resource: QuerySessionModel | None = None
