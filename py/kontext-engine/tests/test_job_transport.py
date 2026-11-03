"""Tests for the local DB claim transport."""

from __future__ import annotations

import pytest

from kontext.common.jobs.transport import JobRunClaim
from kontext.engine.transports import LocalDbJobRunClaimTransport, StaticProjectIds

pytestmark = pytest.mark.asyncio


async def test_static_project_ids_returns_configured_ids() -> None:
    provider = StaticProjectIds(("a", "b"))
    assert await provider() == ["a", "b"]


async def test_transport_returns_first_claim_across_projects(monkeypatch) -> None:
    """The transport scans projects in order and returns the first claimed run."""
    seen: list[str] = []

    class _FakeRunService:
        def __init__(self, project_id: str) -> None:
            self._project_id = project_id

        def claim_next_queued_run_sync(self, *, worker_identifier: str):
            seen.append(self._project_id)

            class _Claimed:
                id = f"run-{self._project_id}"

            if self._project_id == "empty":
                return None
            return _Claimed()

    monkeypatch.setattr("kontext.data.JobRunDataService", _FakeRunService)

    transport = LocalDbJobRunClaimTransport(StaticProjectIds(("empty", "proj")))
    claim = await transport.claim_next(worker_identifier="worker-1")

    assert claim == JobRunClaim(run_id="run-proj", project_id="proj")
    assert seen == ["empty", "proj"]


async def test_transport_returns_none_when_all_projects_idle(monkeypatch) -> None:
    class _FakeRunService:
        def __init__(self, project_id: str) -> None:
            self._project_id = project_id

        def claim_next_queued_run_sync(self, *, worker_identifier: str):
            return None

    monkeypatch.setattr("kontext.data.JobRunDataService", _FakeRunService)

    transport = LocalDbJobRunClaimTransport(StaticProjectIds(("a", "b")))
    assert await transport.claim_next(worker_identifier="worker-1") is None
