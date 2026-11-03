"""Shared context models for chat-session orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from kontext.auth import AuthManager
from kontext.schema import ChatRequest, ChatSessionModel, ProjectModel


@dataclass(frozen=True)
class ChatAccessContext:
    """Transport-agnostic authorization context for chat-session workflows."""

    project_id: UUID
    user_id: UUID | None = None
    effective_owner_id: UUID | None = None
    project_scope: bool = False
    project: ProjectModel | None = None
    resource: ChatSessionModel | None = None
    auth_manager: AuthManager | None = None


@dataclass(frozen=True)
class ChatStreamContext:
    """Transport-agnostic context for a chat streaming request."""

    request: ChatRequest
    access: ChatAccessContext
    headers: Mapping[str, str]
