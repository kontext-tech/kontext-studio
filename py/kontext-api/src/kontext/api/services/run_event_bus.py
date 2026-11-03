"""Per-run event fan-out for the SSE stream endpoint.

One shared poller per run fans run status and log batches out to every
subscriber, instead of every SSE connection polling the database on its own
schedule (I5.16): N concurrent viewers of a run now cost one polling loop,
not N.

A subscriber's delivery semantics are unchanged from the per-connection poll:
each batch carries the *full* current run status and log list, and the
subscriber deduplicates by event id — so a dropped batch (bounded queue, slow
consumer) is recovered by the next cycle's full snapshot.

Cross-process visibility needs no broker: the job worker writes run status
and logs to the project database, and the tailer reads the same tables. A
later Postgres deployment could add LISTEN/NOTIFY as an optional fast path
behind the same subscription port.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

from kontext.execution import (
    ExecutionRunService,
    build_log_event,
    build_status_event,
)
from kontext.schema import ExecutionEventModel, ExecutionRunStatus

#: How often the shared tailer re-reads run status and logs while at least one
#: subscriber is attached. Matches the per-connection interval it replaces.
TAIL_INTERVAL_SECONDS = 1.0

#: Watchdog for a stalled or dead tailer: if no batch arrives within this
#: window, the consumer loop re-checks its disconnect/deadline/terminal exit
#: conditions, and a dead tail task gets restarted before the next read.
TAIL_TIMEOUT_SECONDS = TAIL_INTERVAL_SECONDS * 2

#: Upper bound on how long the shared tailer may poll a run that never reaches
#: a terminal status; matches the per-connection bound it replaces.
TAIL_MAX_STREAM_SECONDS = 30 * 60

RUN_EVENT_TERMINAL_STATUSES = {
    ExecutionRunStatus("succeeded"),
    ExecutionRunStatus("failed"),
    ExecutionRunStatus("cancelled"),
    ExecutionRunStatus("timed_out"),
}

#: Batches are tiny (status + log list); drop-oldest keeps a stalled consumer
#: from growing memory, and the next cycle re-sends everything anyway.
_MAX_QUEUED_BATCHES = 4

#: Watchdog budget: after this many consecutive tail timeouts the consumer
#: stream ends rather than hanging an SSE connection against a persistently
#: failing tailer (~30s).
_MAX_CONSECUTIVE_TIMEOUTS = 30


@dataclass
class RunEventBatch:
    """One tail cycle: current run status plus the current log list."""

    status_event: ExecutionEventModel | None
    log_events: list[ExecutionEventModel] = field(default_factory=list)
    is_terminal: bool = False
    #: The run row disappeared (deleted / not visible) — consumers exit.
    run_missing: bool = False

    @classmethod
    def missing(cls) -> RunEventBatch:
        return cls(status_event=None, is_terminal=True, run_missing=True)


@dataclass
class _RunTail:
    """Shared tailer state for one run id."""

    task: asyncio.Task[None] | None = None
    subscribers: list[asyncio.Queue[RunEventBatch]] = field(default_factory=list)
    started_at: float = 0.0


class RunEventBus:
    """Registry of run subscriptions plus one shared tailer per active run."""

    def __init__(self) -> None:
        self._tails: dict[UUID, _RunTail] = {}
        self._locks: dict[UUID, asyncio.Lock] = {}
        self._service = ExecutionRunService()

    def _tail(self, run_id: UUID) -> _RunTail:
        tail = self._tails.get(run_id)
        if tail is None:
            tail = _RunTail()
            self._tails[run_id] = tail
            self._locks[run_id] = asyncio.Lock()
        return tail

    async def subscribe(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        limit: int,
        now: float | None = None,
    ) -> asyncio.Queue[RunEventBatch]:
        """Attach a subscriber queue and ensure the shared tailer is running."""
        queue: asyncio.Queue[RunEventBatch] = asyncio.Queue(maxsize=_MAX_QUEUED_BATCHES)
        tail = self._tail(run_id)
        async with self._locks[run_id]:
            tail.subscribers.append(queue)
            loop = asyncio.get_running_loop()
            if now is None:
                now = loop.time()
            if tail.task is None or tail.task.done():
                tail.started_at = now
                tail.task = asyncio.create_task(
                    self._tail_loop(run_id=run_id, project_id=project_id, limit=limit)
                )
        return queue

    async def unsubscribe(
        self,
        *,
        run_id: UUID,
        queue: asyncio.Queue[RunEventBatch],
    ) -> None:
        """Detach a subscriber; the tailer stops when the last one leaves."""
        tail = self._tail(run_id)
        async with self._locks[run_id]:
            if queue in tail.subscribers:
                tail.subscribers.remove(queue)
            last = not tail.subscribers
        if last:
            tail = self._tails.get(run_id)
            if tail is not None and tail.task is not None:
                tail.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tail.task
            self._tails.pop(run_id, None)
            self._locks.pop(run_id, None)

    async def _tail_loop(self, *, run_id: UUID, project_id: UUID, limit: int) -> None:
        """Poll status + logs once per interval and publish to subscribers."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + TAIL_MAX_STREAM_SECONDS
        try:
            while True:
                run = await self._service.get_run_async(project_id=project_id, run_id=run_id)
                if not run:
                    self._publish(run_id, RunEventBatch.missing())
                    return

                logs = await self._service.get_logs_async(
                    project_id=project_id,
                    run_id=run_id,
                    limit=limit,
                )
                is_terminal = run.status in RUN_EVENT_TERMINAL_STATUSES
                self._publish(
                    run_id,
                    RunEventBatch(
                        status_event=build_status_event(run),
                        log_events=[build_log_event(log) for log in logs],
                        is_terminal=is_terminal,
                    ),
                )
                if is_terminal:
                    return

                if loop.time() >= deadline:
                    return

                await asyncio.sleep(TAIL_INTERVAL_SECONDS)
        finally:
            # When the tail loop ends (terminal, missing, deadline) wake any
            # remaining subscribers with a terminal-ish empty batch so they
            # re-evaluate and exit instead of blocking on queue.get().
            tail = self._tails.get(run_id)
            if tail is not None:
                self._publish(
                    run_id,
                    RunEventBatch(
                        status_event=None,
                        log_events=[],
                        is_terminal=True,
                    ),
                )

    def _publish(self, run_id: UUID, batch: RunEventBatch) -> None:
        tail = self._tails.get(run_id)
        if tail is None:
            return
        for queue in list(tail.subscribers):
            if queue.full():
                # Drop the *oldest* cycle: the newest snapshot is always the
                # most complete one (and may carry the terminal marker a
                # stalled consumer needs to exit).
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(batch)

    def ensure_tailer(self, *, run_id: UUID, project_id: UUID, limit: int) -> None:
        """(Re)start the shared tailer if it is not running.

        Called by the consumer watchdog when a tail task died mid-run; callers
        must hold the per-run lock or be inside this module's stream helper.
        """
        tail = self._tails.get(run_id)
        if not tail or not tail.subscribers:
            return
        if tail.task is None or tail.task.done():
            tail.task = asyncio.create_task(
                self._tail_loop(run_id=run_id, project_id=project_id, limit=limit)
            )


#: Process-wide bus singleton (one tailer per run that has viewers).
RUN_EVENT_BUS = RunEventBus()


@contextlib.asynccontextmanager
async def stream_run_event_batches(
    *,
    run_id: UUID,
    project_id: UUID,
    limit: int,
    bus: RunEventBus | None = None,
) -> AsyncIterator[AsyncIterator[RunEventBatch]]:
    """Subscribe to the shared tailer for one run.

    Yields an async iterator of :class:`RunEventBatch` cycles. The iterator
    yields a terminal sentinel after too many consecutive watchdog timeouts
    (tailer repeatedly failing) so consumers exit instead of hanging.
    """
    bus = bus or RUN_EVENT_BUS
    queue = await bus.subscribe(run_id=run_id, project_id=project_id, limit=limit)
    try:

        async def _batches() -> AsyncIterator[RunEventBatch]:
            consecutive_timeouts = 0
            while True:
                try:
                    batch = await asyncio.wait_for(queue.get(), timeout=TAIL_TIMEOUT_SECONDS)
                except TimeoutError:
                    consecutive_timeouts += 1
                    if consecutive_timeouts > _MAX_CONSECUTIVE_TIMEOUTS:
                        # Tailer persistently failing: exit the stream instead
                        # of hanging the SSE connection forever.
                        yield RunEventBatch.missing()
                        return
                    async with bus._locks[run_id]:
                        bus.ensure_tailer(run_id=run_id, project_id=project_id, limit=limit)
                    continue
                consecutive_timeouts = 0
                yield batch

        yield _batches()
    finally:
        await bus.unsubscribe(run_id=run_id, queue=queue)
