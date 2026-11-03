"""Cooperative cancellation registry for in-process job runs.

Jobs run inside the API/worker process in local mode, so a database status
change alone cannot stop in-flight work. This module provides a process-local
registry that lets a caller signal cancellation to a running job, and lets
jobs observe it cooperatively via :class:`~kontext.jobs.job_context.JobContext`.

Scope is deliberately process-local: it coordinates a run with the worker that
is executing it, mirroring how the local worker owns execution topology.
"""

from __future__ import annotations

import asyncio


class JobCancelledError(Exception):
    """Raised when a running job observes that it has been cancelled."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Job run {run_id} was cancelled")
        self.run_id = run_id


class JobCancellationRegistry:
    """Process-local map of running job runs to cancellation signals."""

    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}

    def register(self, run_id: str) -> asyncio.Event:
        """Register a running run and return its cancellation signal."""
        event = self._events.get(run_id)
        if event is None:
            event = asyncio.Event()
            self._events[run_id] = event
        return event

    def unregister(self, run_id: str) -> None:
        """Remove a run once it is no longer executing."""
        self._events.pop(run_id, None)

    def request_cancel(self, run_id: str) -> bool:
        """Signal cancellation for a running run.

        Returns ``True`` when a running registration was signalled, ``False``
        when the run is not executing in this process (the caller should still
        persist the cancelled status).
        """
        event = self._events.get(run_id)
        if event is None:
            return False
        event.set()
        return True

    def is_cancelled(self, run_id: str) -> bool:
        event = self._events.get(run_id)
        return event is not None and event.is_set()

    async def wait_for_cancellation(self, run_id: str) -> None:
        """Block until *run_id* is cancelled.

        Returns immediately if the run is not registered, so callers can await
        it alongside their work without hanging when no registration exists.
        """
        event = self._events.get(run_id)
        if event is None:
            return
        await event.wait()


# Module-level singleton so producers (API cancel path) and consumers (worker)
# share one registry without threading a dependency through every call.
_registry = JobCancellationRegistry()


def get_cancellation_registry() -> JobCancellationRegistry:
    """Return the process-local cancellation registry singleton."""
    return _registry
