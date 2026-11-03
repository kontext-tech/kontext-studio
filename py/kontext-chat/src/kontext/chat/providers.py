"""Chat-session service provider abstractions."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping
from typing import Protocol
from uuid import UUID

from kontext.agent import BaseAgenticSystem
from kontext.common.protocols import IChatSessionProtocol, RuntimeProviderProtocol
from kontext.data import ChatSessionTokenUsageDataService
from kontext.schema import (
    ChatMessage,
    ChatRequest,
    ChatSessionModel,
    ProjectModel,
    SimpleRunEvent,
    ToolCall,
    TriggerActorModel,
)


class ChatRuntimeProviderFactoryProtocol(Protocol):
    """Factory for runtime providers used by chat streaming workflows."""

    async def create_runtime_provider(
        self,
        *,
        project_id: UUID | str,
        headers: Mapping[str, str],
    ) -> RuntimeProviderProtocol: ...


class ChatAgentWorkflowProtocol(Protocol):
    """AI adapter surface required by `kontext-chat` streaming workflows."""

    async def create_agent(
        self,
        chat_request: ChatRequest,
        runtime_provider: RuntimeProviderProtocol,
        project: ProjectModel,
        user_id: str | None = None,
        session: ChatSessionModel | None = None,
    ) -> BaseAgenticSystem: ...

    async def load_session_messages(
        self,
        chat_request: ChatRequest,
        runtime_provider: RuntimeProviderProtocol,
        project: ProjectModel,
        user_id: str | None = None,
        session: ChatSessionModel | None = None,
    ) -> list[ChatMessage]: ...

    def resolve_emit_tool_call_events(
        self,
        runtime_provider: RuntimeProviderProtocol,
        session: ChatSessionModel | None,
    ) -> bool: ...

    def stream_agent_response(
        self,
        agent: BaseAgenticSystem,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        *,
        emit_tool_call_events: bool = True,
        tool_outputs: list[ToolCall] | None = None,
        run_id: str | None = None,
        current_execution_run_id: str | None = None,
        chat_session_service: IChatSessionProtocol | None = None,
        token_usage_service: ChatSessionTokenUsageDataService | None = None,
    ) -> AsyncGenerator[str, None]: ...


class ChatExecutionTrackerProtocol(Protocol):
    """Optional execution-run persistence for streamed chat workflows."""

    async def resolve_waiting_run_id(
        self,
        *,
        project_id: UUID,
        chat_session_id: UUID,
        agent_runtime_run_id: str | None = None,
    ) -> UUID | None: ...

    async def create_run(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        chat_session_id: UUID,
        triggered_by: TriggerActorModel,
        engine_type: str | None = None,
    ) -> UUID: ...

    async def mark_run_running(
        self,
        *,
        project_id: UUID,
        platform_run_id: UUID,
        chat_session_id: UUID,
        agent_runtime_run_id: str | None = None,
        message: str = "Agent execution running",
    ) -> None: ...

    async def persist_event(
        self,
        *,
        project_id: UUID,
        platform_run_id: UUID,
        chat_session_id: UUID,
        event: SimpleRunEvent,
    ) -> SimpleRunEvent: ...
