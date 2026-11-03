"""Framework-neutral execution context helpers for Kontext agents."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from .tool_results import InMemoryToolResultSidecar, ToolResultSidecar

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionContext:
    """Framework-neutral context for tool execution state.

    ``tool_results`` holds typed payloads keyed by explicit result identity
    (transient/durable artifact ids), shared across tool calls of the same
    session, typed by the :class:`ToolResultSidecar` port. Harness adapters
    own the concrete store and inject it at scope creation; the in-memory
    default exists for scope helpers and tests.
    """

    project_id: str
    session_id: str | None = None
    tool_results: ToolResultSidecar = field(default_factory=InMemoryToolResultSidecar)


@dataclass
class AgentContext:
    """Framework-neutral context for an agent run/action."""

    project_id: str
    session_id: str


@runtime_checkable
class RuntimeToolContext(Protocol):
    """Framework-neutral runtime context passed to tool methods."""

    session_state: dict[str, Any] | None

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        """Treat runtime tool context as an arbitrary object for call validation."""
        from pydantic_core import core_schema

        return core_schema.any_schema()


# The contextvar is the fast, loop-local view; the session-id-keyed tool
# registry is the canonical storage (it outlives one event loop and one
# request, which is required for sidecar payloads read outside a run's
# scope). Both are installed/uninstalled together via `agent_context_scope`.
_agent_context_var: ContextVar[AgentContext | None] = ContextVar("agent_context", default=None)
_tool_context_var: ContextVar[ToolExecutionContext | None] = ContextVar(
    "tool_context", default=None
)

_tool_registry: dict[str, ToolExecutionContext] = {}


def get_tool_context(session_id: str | None = None) -> ToolExecutionContext | None:
    """Get the current tool execution context."""
    ctx = _tool_context_var.get()
    if ctx is None and session_id:
        ctx = _tool_registry.get(session_id)
    return ctx


def get_tool_sidecar(session_id: str | None = None) -> ToolResultSidecar | None:
    """Get the session's tool-result sidecar, if a tool context exists."""
    ctx = get_tool_context(session_id)
    return ctx.tool_results if ctx is not None else None


@contextmanager
def agent_context_scope(
    ctx: AgentContext,
    tool_ctx: ToolExecutionContext | None = None,
) -> Generator[AgentContext, None, None]:
    """Scope both agent and tool execution context."""
    token = _agent_context_var.set(ctx)

    if tool_ctx is None:
        tool_ctx = ToolExecutionContext(project_id=ctx.project_id, session_id=ctx.session_id)

    tool_token = _tool_context_var.set(tool_ctx)

    if ctx.session_id:
        _tool_registry[ctx.session_id] = tool_ctx

    try:
        yield ctx
    finally:
        _agent_context_var.reset(token)
        _tool_context_var.reset(tool_token)


def unregister_session_context(session_id: str | None) -> None:
    """Remove contexts from the cross-thread registry.

    Dropping the :class:`ToolExecutionContext` releases its sidecar entries —
    typed payloads stop being retained once the session's runs are done.
    """
    if session_id:
        _tool_registry.pop(session_id, None)


def get_session_state(context: RuntimeToolContext | None) -> dict[str, Any] | None:
    """Resolve a mutable session-state mapping from a runtime tool context."""
    if context is None:
        return None
    return getattr(context, "session_state", None)
