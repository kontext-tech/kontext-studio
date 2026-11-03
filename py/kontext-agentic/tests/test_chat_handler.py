from __future__ import annotations

from typing import Any, cast
from unittest.mock import MagicMock

from kontext.agent import (
    KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY,
    KONTEXT_SESSION_NAMESPACE,
    SharedSessionStore,
    create_kontext_session_state,
)
from kontext.agentic.chat_handler import (
    DEFAULT_CHAT_AGENT_WORKFLOW,
    ChatHandler,
    chat_handler,
)
from kontext.chat import ChatAgentWorkflowProtocol


def test_bind_current_execution_run_id_delegates_to_agent() -> None:
    handler = ChatHandler()
    agent = MagicMock()

    handler._bind_current_execution_run_id(
        agent=cast("Any", agent),
        current_execution_run_id="run-123",
    )

    agent.bind_current_execution_run_id.assert_called_once_with("run-123")


def test_shared_session_store_bind_sets_current_execution_run_id() -> None:
    session_state = create_kontext_session_state()

    SharedSessionStore(session_state).bind_current_execution_run_id("run-123")

    assert (
        session_state[KONTEXT_SESSION_NAMESPACE][KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY]
        == "run-123"
    )


def test_shared_session_store_bind_clears_current_execution_run_id() -> None:
    session_state = create_kontext_session_state()
    session_state[KONTEXT_SESSION_NAMESPACE][KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY] = (
        "stale-run"
    )

    SharedSessionStore(session_state).bind_current_execution_run_id(None)

    assert (
        KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY not in session_state[KONTEXT_SESSION_NAMESPACE]
    )


# ---------------------------------------------------------------------------
# Workflow-port contract (kontext-chat)
# ---------------------------------------------------------------------------


def test_default_workflow_is_the_chat_handler() -> None:
    assert DEFAULT_CHAT_AGENT_WORKFLOW is chat_handler


def test_chat_handler_matches_workflow_surface() -> None:
    handler = ChatHandler()
    for method in (
        "create_agent",
        "load_session_messages",
        "resolve_emit_tool_call_events",
        "stream_agent_response",
    ):
        assert callable(getattr(handler, method))
    # Structural conformance to the kontext-chat workflow port is verified by
    # pyright at these annotations; type drift fails typecheck. Runtime-provider
    # factories are a composition concern owned by kontext.api.services.runtime,
    # so ChatHandler no longer satisfies the factory port.
    workflow: ChatAgentWorkflowProtocol = handler
    _ = workflow
