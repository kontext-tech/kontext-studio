"""Tests for the local worker supervisor loop (concurrency, claiming)."""

from __future__ import annotations

import asyncio

import pytest

from kontext.common.jobs.transport import JobRunClaim
from kontext.studio import local_worker

pytestmark = pytest.mark.asyncio


def test_resolve_concurrency_default_and_overrides(monkeypatch) -> None:
    monkeypatch.delenv("KONTEXT_LOCAL_WORKER_CONCURRENCY", raising=False)
    assert local_worker._resolve_concurrency() == local_worker._DEFAULT_CONCURRENCY

    monkeypatch.setenv("KONTEXT_LOCAL_WORKER_CONCURRENCY", "4")
    assert local_worker._resolve_concurrency() == 4

    monkeypatch.setenv("KONTEXT_LOCAL_WORKER_CONCURRENCY", "0")
    assert local_worker._resolve_concurrency() == local_worker._DEFAULT_CONCURRENCY

    monkeypatch.setenv("KONTEXT_LOCAL_WORKER_CONCURRENCY", "nonsense")
    assert local_worker._resolve_concurrency() == local_worker._DEFAULT_CONCURRENCY


async def test_worker_runs_multiple_jobs_concurrently(monkeypatch) -> None:
    """With concurrency=3, three slow jobs run in parallel, not serially."""
    active = 0
    peak = 0
    started = asyncio.Event()
    release = asyncio.Event()

    class FakeTransport:
        def __init__(self) -> None:
            self._claim_count = 0

        async def claim_next(self, *, worker_identifier: str):
            self._claim_count += 1
            if self._claim_count <= 3:
                return JobRunClaim(run_id=f"run-{self._claim_count}", project_id="p")
            return None

    async def fake_execute(project_id: str, run_id: str) -> None:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        if active == 3:
            started.set()
        await release.wait()
        active -= 1

    monkeypatch.setattr(local_worker, "_execute_run", fake_execute)

    shutdown = asyncio.Event()
    task = asyncio.create_task(
        local_worker.run_local_worker(
            shutdown=shutdown,
            transport=FakeTransport(),
            concurrency=3,
        )
    )
    try:
        # All three slots must be busy at once for this to succeed.
        await asyncio.wait_for(started.wait(), timeout=10)
        assert peak == 3
    finally:
        release.set()
        shutdown.set()
        await asyncio.wait_for(task, timeout=10)
