import pytest

from kontext.agent.client_policy import sanitize_chat_messages_for_client
from kontext.agent.tools import (
    ToolAction,
    register_tool,
    reset_default_tool_registry_for_tests,
)
from kontext.schema import (
    ArtifactType,
    ChatMessage,
    ChatMessageSegment,
    ChatMessageStatus,
    ChatMessageType,
    ChatToolCallSegment,
    NotebookMutationResult,
    ToolCallResult,
    ToolCallStatus,
)


@pytest.fixture(autouse=True)
def clear_tool_registry():
    reset_default_tool_registry_for_tests()
    yield
    reset_default_tool_registry_for_tests()


def _make_tool_segment(tool_name: str, *, include_details: bool = True) -> ChatMessageSegment:
    seg = ChatToolCallSegment(
        segment_type="tool_call",
        tool_name=tool_name,
        tool_args={"a": 1} if include_details else None,
        result=ToolCallResult(root="ok") if include_details else None,
        status=ToolCallStatus.COMPLETED,
        tool_call_id="tc_1",
        tool_call_error=None,
        error=None,
    )
    return ChatMessageSegment(seg)


def test_non_local_drops_non_visible_tool_calls_and_strips_details_for_visible():
    register_tool(
        name="visible_tool",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        emit_tool_call=True,
    )
    register_tool(
        name="hidden_tool",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        emit_tool_call=False,
    )

    msg = ChatMessage(
        id="m1",
        type=ChatMessageType.ASSISTANT,
        status=ChatMessageStatus.COMPLETED,
        segments=[
            _make_tool_segment("hidden_tool"),
            _make_tool_segment("visible_tool"),
        ],
    )

    sanitized = sanitize_chat_messages_for_client([msg], environment="production")
    assert len(sanitized) == 1
    assert len(sanitized[0].segments) == 1

    tool_seg = sanitized[0].segments[0].root
    assert isinstance(tool_seg, ChatToolCallSegment)
    assert tool_seg.segment_type == "tool_call"
    assert tool_seg.tool_name == "visible_tool"
    assert tool_seg.tool_args is None
    assert tool_seg.result is None


def test_non_local_matches_tool_meta_by_display_name():
    register_tool(
        name="add_data_table",
        display_name="Create Data Table",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        emit_tool_call=True,
    )

    msg = ChatMessage(
        id="m1",
        type=ChatMessageType.ASSISTANT,
        status=ChatMessageStatus.COMPLETED,
        segments=[_make_tool_segment("Create Data Table")],
    )

    sanitized = sanitize_chat_messages_for_client([msg], environment="production")
    assert len(sanitized) == 1
    assert len(sanitized[0].segments) == 1
    tool_seg = sanitized[0].segments[0].root
    assert isinstance(tool_seg, ChatToolCallSegment)
    assert tool_seg.tool_name == "Create Data Table"
    assert tool_seg.tool_args is None
    assert tool_seg.result is None


def test_local_dev_keeps_tool_call_details():
    register_tool(
        name="any_tool",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        emit_tool_call=False,
    )

    msg = ChatMessage(
        id="m1",
        type=ChatMessageType.ASSISTANT,
        status=ChatMessageStatus.COMPLETED,
        segments=[_make_tool_segment("any_tool")],
    )

    sanitized = sanitize_chat_messages_for_client([msg], environment="local")
    assert len(sanitized[0].segments) == 1
    tool_seg = sanitized[0].segments[0].root
    assert isinstance(tool_seg, ChatToolCallSegment)
    assert tool_seg.tool_args == {"a": 1}
    assert getattr(tool_seg.result, "root", tool_seg.result) == "ok"


def test_non_local_drops_reasoning_segments():
    from kontext.schema import ChatReasoningSegment, ChatTextSegment

    msg = ChatMessage(
        id="m1",
        type=ChatMessageType.ASSISTANT,
        status=ChatMessageStatus.COMPLETED,
        segments=[
            ChatMessageSegment(ChatReasoningSegment(content="internal thought")),
            ChatMessageSegment(ChatTextSegment(content="hello world")),
        ],
    )

    sanitized = sanitize_chat_messages_for_client([msg], environment="production")
    assert len(sanitized[0].segments) == 1
    assert isinstance(sanitized[0].segments[0].root, ChatTextSegment)
    assert sanitized[0].segments[0].root.content == "hello world"


def test_local_dev_keeps_reasoning_segments():
    from kontext.schema import ChatReasoningSegment

    msg = ChatMessage(
        id="m1",
        type=ChatMessageType.ASSISTANT,
        status=ChatMessageStatus.COMPLETED,
        segments=[
            ChatMessageSegment(ChatReasoningSegment(content="internal thought")),
        ],
    )

    sanitized = sanitize_chat_messages_for_client([msg], environment="local")
    assert len(sanitized[0].segments) == 1
    assert isinstance(sanitized[0].segments[0].root, ChatReasoningSegment)
    assert sanitized[0].segments[0].root.content == "internal thought"
