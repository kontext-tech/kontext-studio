"""Agno persisted sessions -> neutral `ChatMessage` conversion."""

from __future__ import annotations

import contextlib
import json
from itertools import groupby

from agno.agent import Message
from kontext.agent.tools import ToolRegistry, ToolResultParser
from kontext.schema import (
    ChatMessage as SchemaChatMessage,
)
from kontext.schema import (
    ChatMessageSegment,
    ChatMessageStatus,
    ChatMessageType,
    ChatTextSegment,
    ToolCall,
    ToolCallResult,
)


def agno_messages_to_chat_messages(
    agno_messages: list[Message],
    *,
    registry: ToolRegistry | None = None,
    session_id: str | None = None,
) -> list[SchemaChatMessage]:
    """Convert Agno messages to frontend-compatible ChatMessage objects.

    Segments are the schema's discriminated union (`segmentType`): text, toolCall,
    error, object, reasoning. Tool-role messages are merged into the assistant
    tool-call segments that issued them, and consecutive assistant messages are
    grouped into one so a tool call and its follow-up text render as a message.
    """
    chat_messages: list[SchemaChatMessage] = []
    tool_parser = ToolResultParser(registry=registry)

    # 1. Extract tool results into a typed map for easy lookup
    tool_results: dict[str, ToolCall] = {}
    for msg in agno_messages:
        if msg.role == "tool" and msg.tool_call_id:
            raw_error = getattr(msg, "tool_call_error", None)
            if isinstance(raw_error, str) and raw_error:
                tool_error = raw_error
            elif raw_error:
                tool_error = msg.get_content_string() or "Tool call failed"
            else:
                tool_error = None
            tool_results[str(msg.tool_call_id)] = ToolCall(
                tool_call_id=str(msg.tool_call_id),
                result=ToolCallResult(root=msg.get_content_string()),
                tool_call_error=tool_error,
            )

    # 2. Convert messages to raw ChatMessage objects
    raw_messages: list[SchemaChatMessage] = []

    for msg in agno_messages:
        # Skip tool messages as they are merged into assistant messages
        if msg.role == "tool":
            continue

        # Map role to ChatMessageType
        if msg.role == "user":
            msg_type = ChatMessageType.USER
        elif msg.role == "assistant":
            msg_type = ChatMessageType.ASSISTANT
        else:
            msg_type = ChatMessageType.SYSTEM

        segments: list[ChatMessageSegment] = []
        content = msg.get_content_string()
        if content:
            segments.append(
                ChatMessageSegment(ChatTextSegment(segment_type="text", content=content))
            )

        if msg.tool_calls:
            for tc in msg.tool_calls:
                # Handle both dictionary and object formats (Agno vs historical JSON)
                if isinstance(tc, dict):
                    tc_id = tc.get("id")
                    function = tc.get("function", {})
                else:
                    tc_id = getattr(tc, "id", None)
                    function = getattr(tc, "function", {})

                if isinstance(function, dict):
                    tool_name = function.get("name")
                    args = function.get("arguments")
                else:
                    tool_name = getattr(function, "name", None)
                    args = getattr(function, "arguments", None)

                # Parse arguments if they are a string
                if isinstance(args, str) and args.strip():
                    with contextlib.suppress(Exception):
                        args = json.loads(args)

                # Ensure args is a dict or None for ToolResultParser
                if not isinstance(args, dict):
                    args = None

                # Get tool result and error status from our typed map
                result_info = tool_results.get(str(tc_id)) if tc_id else None

                tool_segments = tool_parser.convert_tool_to_segments(
                    tool_name=tool_name,
                    tool_args=args,
                    result=result_info.result if result_info else None,
                    tool_call_id=str(tc_id) if tc_id else None,
                    tool_call_error=result_info.tool_call_error if result_info else None,
                    session_id=session_id,
                )
                segments.extend(tool_segments)

        raw_messages.append(
            SchemaChatMessage(
                id=msg.id, type=msg_type, status=ChatMessageStatus.COMPLETED, segments=segments
            )
        )

    # 3. Grouping logic: merge consecutive assistant messages
    for msg_type, group in groupby(raw_messages, key=lambda m: m.type):
        if msg_type == ChatMessageType.ASSISTANT:
            group_list = list(group)
            merged_msg = group_list[0]
            for other_msg in group_list[1:]:
                merged_msg.segments.extend(other_msg.segments)
            chat_messages.append(merged_msg)
        else:
            chat_messages.extend(group)

    return chat_messages
