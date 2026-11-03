"""Wiring tests for query-owned job dispatch helpers.

``dispatch_cleanup_session_job`` delegates the job/run/dispatch choreography to
``create_job_run_and_maybe_dispatch``; these tests pin the arguments it must
forward so a "system owns everything" rewrite cannot silently drop the caller's
owner (which changes job ownership and listing per user).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

import kontext.query.jobs.dispatch as dispatch_module
from kontext.query.jobs.cleanup_session_job import CleanupSessionJob
from kontext.query.jobs.dispatch import dispatch_cleanup_session_job


@pytest.mark.asyncio
async def test_cleanup_dispatch_forwards_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_dispatch(**kwargs: Any) -> tuple[Any, bool]:
        captured.update(kwargs)
        return MagicMock(id=str(uuid4())), True

    monkeypatch.setattr(dispatch_module, "create_job_run_and_maybe_dispatch", fake_dispatch)
    project_id, owner_id, session_id = uuid4(), uuid4(), uuid4()

    await dispatch_cleanup_session_job(
        queue_client=MagicMock(),
        project_id=project_id,
        session_ids=[session_id],
        owner_id=owner_id,
    )

    assert captured["project_id"] == project_id
    assert captured["owner_id"] == owner_id
    assert captured["job_class"] is CleanupSessionJob
    assert captured["job_params"].session_id == str(session_id)
