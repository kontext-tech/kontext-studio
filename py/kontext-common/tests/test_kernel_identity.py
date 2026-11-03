"""Tests for session-kernel identity construction and parsing."""

from __future__ import annotations

from kontext.common.python_execution.kernel_identity import (
    chat_session_kernel_id,
    parse_session_kernel_id,
    query_session_kernel_id,
)


def test_chat_and_query_ids_round_trip() -> None:
    chat = parse_session_kernel_id(chat_session_kernel_id("abc-123"))
    assert chat.namespace == "chat"
    assert chat.record_id == "abc-123"

    query = parse_session_kernel_id(query_session_kernel_id("def-456"))
    assert query.namespace == "query"
    assert query.record_id == "def-456"


def test_bare_id_is_a_notebook() -> None:
    ref = parse_session_kernel_id("11111111-1111-1111-1111-111111111111")
    assert ref.namespace == "notebook"
    assert ref.record_id == "11111111-1111-1111-1111-111111111111"
