"""Client-visibility policy for streamed agent output.

This belongs to the neutral streaming contract, not to any application tool:
it decides which tool calls, arguments/results, and reasoning reach a client.
Adapters apply it while converting harness events; application transports apply
it to history reads.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

from kontext.common.constants import ModelEnvVars
from kontext.common.utils.environment import is_local_dev_environment
from kontext.schema import (
    ChatMessage,
    ChatMessageSegment,
    ChatReasoningSegment,
    ChatToolCallSegment,
)

from .tools import get_tool_meta, get_tool_meta_by_display_name

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "ToolCallClientPolicy",
    "get_tool_call_client_policy",
    "sanitize_chat_messages_for_client",
    "should_emit_reasoning_to_client",
    "should_emit_tool_call_to_client",
    "should_include_tool_call_details_for_client",
]

ToolCallClientPolicy = Literal["auto", "off", "safe", "full"]


def get_tool_call_client_policy(*, environment: str | None = None) -> ToolCallClientPolicy:
    """Resolve the client-facing tool-call policy.

    Priority:
    1) Explicit function argument via ``environment``
    2) Explicit env override via PROJECT_AGENT_TOOL_CALL_CLIENT_POLICY
    3) Auto mode: local/dev -> full, otherwise -> safe

    Modes:
    - full: emit all tool calls with args/results (debug)
    - safe: emit only ToolMeta.emit_tool_call tools; strip args/results
    - off: emit no tool calls to clients
    """

    if environment is not None:
        return "full" if is_local_dev_environment(environment) else "safe"  # type: ignore[return-value]

    explicit = os.getenv(ModelEnvVars.PROJECT_AGENT_TOOL_CALL_CLIENT_POLICY)
    if explicit:
        value = explicit.strip().lower()
        if value in ("auto", "off", "safe", "full"):
            return value  # type: ignore[return-value]

    return "full" if is_local_dev_environment(environment) else "safe"  # type: ignore[return-value]


def should_include_tool_call_details_for_client(*, environment: str | None = None) -> bool:
    return get_tool_call_client_policy(environment=environment) == "full"


def should_emit_reasoning_to_client(*, environment: str | None = None) -> bool:
    """Policy for reasoning/thinking visibility to clients.

    - full: emit reasoning events.
    - any other: suppress reasoning from client.
    """
    return get_tool_call_client_policy(environment=environment) == "full"


def should_emit_tool_call_to_client(
    tool_name: str | None, *, environment: str | None = None
) -> bool:
    """Policy for tool-call visibility to clients.

    - full: emit all tool calls.
    - safe: emit only tool calls explicitly marked as user-visible in ToolMeta.
    - off: emit no tool calls.
    """

    policy = get_tool_call_client_policy(environment=environment)
    if policy == "off":
        return False
    if policy == "full":
        return True
    if not tool_name:
        return False
    # `tool_name` may be either the internal tool identifier (preferred) or a display label
    # depending on which code path produced the segment.
    meta = get_tool_meta(tool_name) or get_tool_meta_by_display_name(tool_name)
    return bool(meta and meta.emit_tool_call)


def sanitize_chat_messages_for_client(
    messages: Iterable[ChatMessage], *, environment: str | None = None
) -> list[ChatMessage]:
    """Sanitize chat history messages for client consumption.

    Ensures consistent behavior with streaming event policy:
    - Local dev: return messages unchanged.
    - Non-local:
      - Drop tool-call segments for tools not marked `emit_tool_call=True`.
      - Strip tool-call args/results (but keep status/error) for emitted tool calls.
      - Preserve non-tool segments (text/artifact/error/object).
    """
    policy = get_tool_call_client_policy(environment=environment)
    if policy == "full":
        return list(messages)

    sanitized: list[ChatMessage] = []
    for msg in messages:
        msg_copy = msg.model_copy(deep=True)
        new_segments: list[ChatMessageSegment] = []

        for seg in msg_copy.segments:
            inst = seg.root

            # Drop reasoning segments (policy is never "full" here; that case
            # returned early above).
            if isinstance(inst, ChatReasoningSegment):
                continue

            if not isinstance(inst, ChatToolCallSegment):
                new_segments.append(seg)
                continue

            if policy == "off":
                continue

            if not inst.tool_name or not should_emit_tool_call_to_client(
                inst.tool_name, environment=environment
            ):
                continue

            # Resolve tool meta to check if result should be preserved even in safe mode
            # Pylance hint: inst.tool_name is truthy here due to the check above.
            tool_name = inst.tool_name
            meta = get_tool_meta(tool_name) or get_tool_meta_by_display_name(tool_name)
            keep_result = meta.emit_result if meta else False

            stripped = inst.model_copy(deep=True)
            stripped.tool_args = None  # Always strip args in safe mode unless full policy

            # For security, suppress results on failed tool calls in production
            is_failed = bool(inst.tool_call_error)
            if not keep_result or is_failed:
                stripped.result = None
            new_segments.append(ChatMessageSegment(stripped))

        msg_copy.segments = new_segments
        sanitized.append(msg_copy)

    return sanitized
