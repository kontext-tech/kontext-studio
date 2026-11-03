"""Context and tool-result sidecar behavior tests."""

from __future__ import annotations

import logging

from kontext.agent import (
    AgentContext,
    InMemoryToolResultSidecar,
    ToolExecutionContext,
    ToolResultEntry,
    agent_context_scope,
)
from kontext.agent.context import get_tool_sidecar


def test_runtime_tool_context_can_be_used_with_validate_call():
    from pydantic import validate_call

    from kontext.agent import RuntimeToolContext

    @validate_call
    def entrypoint(run_context: RuntimeToolContext | None = None) -> bool:
        return run_context is None

    assert entrypoint() is True


def test_retrieve_sidecar_entry_missing_is_silent_when_quiet(caplog) -> None:
    """Missing sidecar lookups do not surface warning noise on the happy path."""
    caplog.set_level(logging.WARNING)

    with agent_context_scope(
        AgentContext(project_id="project-id", session_id="session-id"),
        ToolExecutionContext(project_id="project-id", session_id="session-id"),
    ):
        sidecar = get_tool_sidecar("session-id")

        assert sidecar is not None
        assert isinstance(sidecar, InMemoryToolResultSidecar)
        assert sidecar.get("missing-handle") is None

    assert "not found" not in caplog.text
    assert "Scratch result not found" not in caplog.text


def test_sidecar_entry_is_keyed_by_explicit_identity() -> None:
    sidecar = InMemoryToolResultSidecar()
    entry = ToolResultEntry(payload={"rows": [1, 2]}, artifact_type="datatable", title="Q1")

    sidecar.put("handle-1", entry)
    assert sidecar.get("handle-1") is entry

    # Aliases point at the same identity; re-registering under a new handle
    # never aliases old content-hash keys.
    sidecar.alias("alias-1", "handle-1")
    assert sidecar.get("alias-1") is entry

    # Same content, different identity: a distinct entry (no cross-aliasing).
    other = ToolResultEntry(payload={"rows": [1, 2]}, artifact_type="datatable", title="Q2")
    sidecar.put("handle-2", other)
    assert sidecar.get("handle-2") is other
    assert sidecar.get("handle-2") is not sidecar.get("handle-1")

    sidecar.drop_all()
    assert sidecar.get("handle-1") is None
