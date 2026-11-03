"""Tests for the shared run-event tailer (run_event_bus).

The bus replaces per-SSE-connection database polling with one tailer per run
that fans full status+log batches out to every subscriber. These tests pin
the fan-out, terminal, missing-run, teardown, and drop-oldest contracts.
"""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from kontext.api.services.run_event_bus import (
    RUN_EVENT_BUS,
    TAIL_INTERVAL_SECONDS,
    RunEventBatch,
    RunEventBus,
    stream_run_event_batches,
)
from kontext.schema import ExecutionRunKind, ExecutionRunModel, ExecutionRunStatus


def _model_run(status: str) -> ExecutionRunModel:
    """A real ExecutionRunModel (build_status_event reads real fields)."""
    return ExecutionRunModel(
        id=str(uuid4()),
        kind=ExecutionRunKind("agent"),
        status=ExecutionRunStatus(status),
        created_at=datetime(2026, 10, 24, tzinfo=UTC),
    )


def _service(run_status: str | None = "running", logs: list[Any] | None = None) -> MagicMock:
    """A stubbed ExecutionRunService for one tail cycle."""
    service = MagicMock()
    if run_status is None:
        service.get_run_async = AsyncMock(return_value=None)
    else:
        service.get_run_async = AsyncMock(return_value=_model_run(run_status))
    service.get_logs_async = AsyncMock(return_value=logs or [])
    return service


def _stub_service(bus: RunEventBus, service: MagicMock) -> None:
    """Point the bus at a stubbed service (the tailer resolves lazily)."""
    bus._service = service


@pytest.fixture
def _reset_singleton() -> Iterator[None]:
    yield
    RUN_EVENT_BUS._tails.clear()
    RUN_EVENT_BUS._locks.clear()


@pytest.mark.asyncio
async def test_fan_out_to_all_subscribers() -> None:
    """Every subscriber receives the same tail cycles."""
    bus = RunEventBus()
    service = _service("running")
    _stub_service(bus, service)

    run_id, project_id = uuid4(), uuid4()
    q1 = await bus.subscribe(run_id=run_id, project_id=project_id, limit=100)
    q2 = await bus.subscribe(run_id=run_id, project_id=project_id, limit=100)

    async def _collect(queue: asyncio.Queue[RunEventBatch]) -> list[RunEventBatch]:
        batches: list[RunEventBatch] = []
        while len(batches) < 1 or not batches[-1].is_terminal:
            batches.append(await asyncio.wait_for(queue.get(), timeout=5))
            if len(batches) >= 5:
                break
        return batches

    t1 = asyncio.create_task(_collect(q1))
    t2 = asyncio.create_task(_collect(q2))
    # Flip to a terminal status so the shared tailer exits after the next cycle.
    await asyncio.sleep(TAIL_INTERVAL_SECONDS * 1.2)
    service.get_run_async = AsyncMock(return_value=_model_run("succeeded"))
    b1 = await asyncio.wait_for(t1, timeout=10)
    b2 = await asyncio.wait_for(t2, timeout=10)

    assert len(b1) == len(b2) >= 2
    assert not b1[0].run_missing and not b2[0].run_missing
    await bus.unsubscribe(run_id=run_id, queue=q1)
    await bus.unsubscribe(run_id=run_id, queue=q2)


@pytest.mark.asyncio
async def test_missing_run_yields_missing_batch() -> None:
    bus = RunEventBus()
    _stub_service(bus, _service(run_status=None))
    run_id, project_id = uuid4(), uuid4()
    batches: list[RunEventBatch] = []
    async with stream_run_event_batches(
        run_id=run_id, project_id=project_id, limit=100, bus=bus
    ) as it:
        async for batch in it:
            batches.append(batch)
            break
    assert len(batches) == 1
    assert batches[0].run_missing
    assert batches[0].is_terminal


@pytest.mark.asyncio
async def test_terminal_run_ends_tailer() -> None:
    bus = RunEventBus()
    _stub_service(bus, _service("succeeded"))
    run_id, project_id = uuid4(), uuid4()
    batches: list[RunEventBatch] = []
    async with stream_run_event_batches(
        run_id=run_id, project_id=project_id, limit=100, bus=bus
    ) as it:
        async for batch in it:
            batches.append(batch)
            if batch.is_terminal:
                break
    assert len(batches) == 1
    assert batches[0].is_terminal
    await asyncio.sleep(0.05)
    assert run_id not in bus._tails


@pytest.mark.asyncio
async def test_unsubscribe_stops_tailer_and_tears_down() -> None:
    bus = RunEventBus()
    _stub_service(bus, _service("running"))
    run_id, project_id = uuid4(), uuid4()
    q = await bus.subscribe(run_id=run_id, project_id=project_id, limit=100)
    await asyncio.sleep(TAIL_INTERVAL_SECONDS * 1.5)
    assert run_id in bus._tails
    await bus.unsubscribe(run_id=run_id, queue=q)
    assert run_id not in bus._tails
    assert run_id not in bus._locks


def test_publish_drop_oldest_keeps_recent_batches() -> None:
    """A stalled consumer keeps the most recent cycles, not the first ones."""
    bus = RunEventBus()
    run_id = uuid4()
    bus._tails[run_id] = bus._tail(run_id)
    tail = bus._tails[run_id]
    queue: asyncio.Queue[RunEventBatch] = asyncio.Queue(maxsize=2)
    tail.subscribers.append(queue)

    published = [RunEventBatch(status_event=None, is_terminal=index == 4) for index in range(5)]
    for batch in published:
        bus._publish(run_id, batch)

    assert queue.qsize() == 2
    retained = [queue.get_nowait(), queue.get_nowait()]
    assert retained[0] is published[3]
    assert retained[1] is published[4]
    assert retained[1].is_terminal


def test_batch_missing_classmethod() -> None:
    batch = RunEventBatch.missing()
    assert batch.run_missing
    assert batch.is_terminal
    assert batch.status_event is None
    assert batch.log_events == []


def test_tail_constants_unchanged() -> None:
    """The poll interval matches the per-connection interval it replaces."""
    assert TAIL_INTERVAL_SECONDS == 1.0
