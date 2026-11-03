"""Framework-neutral agent runtime contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass

from kontext.schema import SimpleRunEvent, ToolCall

from .metadata import AgentDescriptor


@dataclass(frozen=True)
class StreamOptions:
    """Options for streaming an agent run.

    `tool_outputs` + `run_id` resume a paused run whose required tools were
    executed externally (HITL). `emit_tool_call_events` is the client-visibility
    policy for tool-call events.
    """

    tool_outputs: Sequence[ToolCall] | None = None
    run_id: str | None = None
    emit_tool_call_events: bool = True


class BaseAgenticSystem(ABC):
    """Framework-neutral agent system contract."""

    # NOTE: `stream_response` implementations are async generators (see below).

    agent_definition: AgentDescriptor

    def __init__(
        self,
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
    ) -> None:
        self.name = name or self.agent_definition.name
        self.description = description or self.agent_definition.description
        self.icon = icon or self.agent_definition.icon

    def bind_current_execution_run_id(self, current_execution_run_id: str | None) -> None:
        """Expose the active execution-run ID to downstream tool calls."""
        _ = current_execution_run_id

    @abstractmethod
    def stream_response(
        self,
        message: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        options: StreamOptions | None = None,
    ) -> AsyncGenerator[SimpleRunEvent, None]:
        """Stream the agent response as `SimpleRunEvent` objects.

        With `options.tool_outputs` the run resumes a paused run instead of
        starting a new one. Implementations are async generators; declaring this
        as a plain method returning `AsyncGenerator` matches how call sites
        consume it (`async for event in agent.stream_response(...)`).
        """
        ...

    @abstractmethod
    def get_token_usage(self, session_id: str | None = None) -> tuple[int, int] | None:
        """Get token usage statistics for a specific session."""
