"""Neutral-backed Agno session storage (the A2 authority switch).

`NeutralBackedDb` implements the session-storage surface Agno exercises
(sessions/runs) on top of the platform-owned `kontext.agent.persistence.
SessionPersistence` port, so Agno internals — history windows, session
summaries, pause-state rehydration, metrics — keep working while the
per-project Agno SQLite file is retired. The platform stores each Agno
session row as an opaque JSON blob (`save_harness_state`); it is
harness-internal and never interpreted by the platform.

Semantics:

- the in-memory maps inherited from `InMemoryDb` are the working set Agno
  reads and writes; every mutation is persisted through the port
  (write-through) and every fresh session is loaded back from the port
  (read-through hydrate). The port is the durable authority: a new
  `NeutralBackedDb` over the same store reconstructs the full session, which
  is what makes pause/resume survive process restarts.

- every operation is loop-safe. `preload()` (awaited by the adapter at the
  start of each streaming turn) makes the working set warm before Agno touches
  the store, so Agno's sync db calls on the event loop serve memory and never
  block. All writes, from any thread or loop, go through one serialized worker;
  `persist_now()` awaits the completion of the write it queues, so a pause
  flush also flushes every earlier snapshot.

- memories/evals/traces/knowledge keep `InMemoryDb`'s inherited in-memory
  behavior: documented no-ops for this adapter (enabled features do not touch
  them).
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any

from agno.db.base import SessionType
from agno.db.in_memory import InMemoryDb
from kontext.agent.persistence import SessionPersistence

__all__ = ["NeutralBackedDb"]

_logger = logging.getLogger(__name__)


@dataclass
class _SaveJob:
    persistence: SessionPersistence
    session_id: str
    state_json: str
    future: Future[None]


#: One daemon worker serializes every harness-state write, whichever thread or
#: event loop produced it. The agent turn runs on its own loop while the request
#: loop flushes the pause blob; chaining tasks per loop made that flush gather a
#: future owned by another loop, so the paused run was never persisted.
_persist_queue: queue.Queue[_SaveJob] = queue.Queue()


def _persist_worker() -> None:
    while True:
        job = _persist_queue.get()
        try:
            asyncio.run(job.persistence.save_harness_state(job.session_id, job.state_json))
        except BaseException as exc:
            job.future.set_exception(exc)
        else:
            job.future.set_result(None)
        finally:
            _persist_queue.task_done()


threading.Thread(target=_persist_worker, name="agno-harness-persist", daemon=True).start()


def _submit_save(persistence: SessionPersistence, session_id: str, state_json: str) -> Future[None]:
    future: Future[None] = Future()
    _persist_queue.put(_SaveJob(persistence, session_id, state_json, future))
    return future


class NeutralBackedDb(InMemoryDb):
    """Agno session storage over the neutral `SessionPersistence` port."""

    def __init__(
        self,
        persistence: SessionPersistence | None = None,
        *,
        label: str = "agno",
    ) -> None:
        super().__init__()
        self.persistence = persistence
        self.label = label

    # ------------------------------------------------------------------
    # Blob serialization and hydration
    # ------------------------------------------------------------------

    def _serialize_row(self, session_id: str) -> str | None:
        row = self._sessions.get(session_id)
        if row is None:
            return None
        return json.dumps(row, default=str)

    def _hydrate_row(self, session_id: str, state_json: str | None) -> bool:
        """Load a persisted session row into the in-memory working set."""
        if not state_json:
            return False
        try:
            row = json.loads(state_json)
        except (TypeError, ValueError):
            _logger.warning(
                "[%s] harness state for session %s is not valid JSON; ignoring",
                self.label,
                session_id,
            )
            return False
        if not isinstance(row, dict):
            return False
        self._sessions[session_id] = row
        self._run_object_cache.pop(session_id, None)
        return True

    # ------------------------------------------------------------------
    # Port bridge (loop safety)
    # ------------------------------------------------------------------

    def _persist_row(self, session_id: str) -> None:
        """Queue the current row for the serialized persistence worker.

        Sync callers (Agno mutations) must not block; the in-memory row is
        already updated. Serializing now captures the snapshot that is later
        written, and the single worker preserves submission order so an older
        snapshot can never land after a newer one.
        """
        if self.persistence is None:
            return
        state_json = self._serialize_row(session_id)
        if state_json is None:
            return

        future = _submit_save(self.persistence, session_id, state_json)
        future.add_done_callback(self._on_save_done)

    def _on_save_done(self, future: Future[None]) -> None:
        """Surface background write failures instead of losing them."""
        if future.cancelled():
            return
        error = future.exception()
        if error is not None:
            _logger.warning("[%s] harness-state write failed: %s", self.label, error)

    # ------------------------------------------------------------------
    # Durable async surface (awaited by the adapter before agno runs)
    # ------------------------------------------------------------------

    async def preload(self, session_id: str) -> None:
        """Hydrate the working set from the port before a turn reads it."""
        if self.persistence is None or session_id in self._sessions:
            return
        state_json = await self.persistence.load_harness_state(session_id)
        self._hydrate_row(session_id, state_json)

    async def persist_now(self, session_id: str) -> None:
        """Await the durable write of the session row (flush earlier writes).

        Called at the pause seam so the persist-before-surface rule covers the
        harness-internal blob as well as the platform-facing rows: a crash
        after the pause is surfaced can never lose the paused run. The shared
        single worker runs this snapshot after every earlier queued write, and
        `await` may be used from any event loop.
        """
        if self.persistence is None or session_id not in self._sessions:
            return
        state_json = self._serialize_row(session_id)
        if state_json is None:
            return
        future = _submit_save(self.persistence, session_id, state_json)
        await asyncio.wrap_future(future)

    # ------------------------------------------------------------------
    # Sync overrides (what agno actually calls)
    # ------------------------------------------------------------------

    def get_session(  # type: ignore[override]
        self,
        session_id: str,
        session_type: SessionType | None = None,
        user_id: str | None = None,
        deserialize: bool | None = True,
        runs_limit: int | None = None,
    ) -> Any:
        """Serve the session, hydrating durably when off the event loop.

        On the event loop this never blocks: the working set must already be
        warm via `preload` (the adapter preloads each turn's session), and a
        cold miss then reads no harness data — an acceptable degradation for
        the metrics-only sync callers (e.g. `get_session_metrics`).
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            if self.persistence is not None and session_id not in self._sessions:
                state_json = asyncio.run(self.persistence.load_harness_state(session_id))
                self._hydrate_row(session_id, state_json)
        return super().get_session(
            session_id=session_id,
            session_type=session_type,
            user_id=user_id,
            deserialize=deserialize,
            runs_limit=runs_limit,
        )

    def upsert_session(self, session: Any, deserialize: bool | None = True) -> Any:  # type: ignore[override]
        result = super().upsert_session(session, deserialize=deserialize)
        if result is not None:
            session_id = self._row_session_id(session)
            if session_id:
                self._persist_row(session_id)
        return result

    def upsert_run(  # type: ignore[override]
        self,
        run: Any,
        session_id: str,
        user_id: str | None = None,
        run_index: int | None = None,
    ) -> None:
        super().upsert_run(run=run, session_id=session_id, user_id=user_id, run_index=run_index)
        if session_id in self._sessions:
            self._persist_row(session_id)

    # `delete_session` is intentionally not overridden: chat-session deletion
    # is platform-owned (`ChatSessionDataService` cascades the neutral rows in
    # one transaction). A harness-side delete must never wipe platform history.

    def rename_session(  # type: ignore[override]
        self,
        session_id: str,
        session_type: SessionType | None,
        session_name: str,
        user_id: str | None = None,
        deserialize: bool | None = True,
    ) -> Any:
        result = super().rename_session(
            session_id,
            session_type,
            session_name,
            user_id=user_id,
            deserialize=deserialize,
        )
        if result is not None and session_id in self._sessions:
            self._persist_row(session_id)
        return result

    @staticmethod
    def _row_session_id(session: Any) -> str | None:
        session_id = getattr(session, "session_id", None)
        if session_id is None and isinstance(session, dict):
            session_id = session.get("session_id")
        return str(session_id) if session_id else None
