"""Process-wide per-session execution locks.

DuckDB session database files are single-writer: two workers opening the same
``{session_id}.db`` concurrently can hit lock errors or corrupt state. Because
each execution resolves its own engine instance, locking must key on the
session id rather than on the engine object.

Locking has two tiers:

- A per ``(session, loop)`` :class:`asyncio.Lock` queues same-loop waiters
  cheaply and thread-free. ``asyncio`` primitives are bound to the loop that
  first touched them, so a lock must not be shared across loops.
- A per-session :class:`threading.Lock` serializes the different event loops
  that legitimately execute the same session: the API server loop (query
  routes, notebook editors) and the per-run agent thread loops (agno executes
  parallel tool calls via ``asyncio.gather`` on its own loop). The thread lock
  is acquired non-blockingly with a short poll so the waiting coroutine stays
  cancellable: abandoning the wait never holds or leaks the lock.

Lock order is always loop lock first, then thread lock, so holders never wait
on the loop while holding the cross-loop lock and no cycle can form.

This lives in ``kontext-common`` so the query orchestration layer and the
in-process execution adapter share one lock table without depending on each
other.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from weakref import WeakKeyDictionary

# Poll interval while waiting for the cross-loop thread lock. Contended
# sessions wait at most this long past a release before proceeding.
_POLL_INTERVAL_SECONDS = 0.02

# Per-loop asyncio locks, keyed weakly by loop so short-lived loops (per-run
# agent threads, tests) do not accumulate entries. Mutation can happen from
# several agent threads at once, so guard it with a plain lock.
_loop_locks: WeakKeyDictionary[asyncio.AbstractEventLoop, dict[str, asyncio.Lock]] = (
    WeakKeyDictionary()
)
_loop_locks_guard = threading.Lock()
# Cross-loop mutexes, one per session key. Kept strong on purpose: a weak-
# valued table could hand out a different lock object to a latecomer while the
# real holder still owns the previous one.
_session_thread_locks: dict[str, threading.Lock] = {}
_thread_locks_guard = threading.Lock()


def get_session_lock(session_id: str) -> asyncio.Lock:
    """Return the execution lock for *session_id* on the running loop."""
    key = str(session_id)
    loop = asyncio.get_running_loop()
    with _loop_locks_guard:
        loop_table = _loop_locks.get(loop)
        if loop_table is None:
            loop_table = {}
            _loop_locks[loop] = loop_table
        lock = loop_table.get(key)
        if lock is None:
            lock = asyncio.Lock()
            loop_table[key] = lock
        return lock


@asynccontextmanager
async def session_execution_lock(session_id: str) -> AsyncIterator[None]:
    """Serialize execution against a single query session across all loops."""
    key = str(session_id)
    async with get_session_lock(key):
        thread_lock = _get_thread_lock(key)
        while not _acquire_nonblocking(thread_lock):
            # A pure sleep keeps the waiter cancellable without leaking an
            # acquisition that a background thread might still complete.
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        try:
            yield
        finally:
            thread_lock.release()


def _get_thread_lock(key: str) -> threading.Lock:
    with _thread_locks_guard:
        lock = _session_thread_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _session_thread_locks[key] = lock
        return lock


def _acquire_nonblocking(lock: threading.Lock) -> bool:
    return lock.acquire(blocking=False)
