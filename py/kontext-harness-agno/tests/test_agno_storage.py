"""Tests for `NeutralBackedDb` — the harness-storage facade (A2 core).

The facade implements the session-storage surface agno exercises over the
neutral `SessionPersistence` port: the platform stores each agno session row
as an opaque JSON blob; the facade keeps an in-memory working set and proves:

- write-through: every agno session/run mutation lands in the port,
- read-through hydration: a brand-new facade (simulated process restart)
  reconstructs the session from the port,
- no harness-owned file is ever created (the per-project Agno SQLite file is
  retired).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from agno.db.base import SessionType

from kontext.agent.persistence import InMemorySessionPersistence, SessionPersistence
from kontext.harness.agno.storage import NeutralBackedDb


@pytest.fixture()
def store() -> InMemorySessionPersistence:
    return InMemorySessionPersistence()


@pytest.fixture()
def db(store: InMemorySessionPersistence) -> NeutralBackedDb:
    return NeutralBackedDb(store, label="test")


def test_facade_complies_with_persistence_protocol(db: NeutralBackedDb) -> None:
    assert isinstance(db.persistence, SessionPersistence)


@pytest.mark.asyncio
async def test_upsert_persists_run_record_through_port(
    db: NeutralBackedDb, store: InMemorySessionPersistence
) -> None:
    """A session upsert followed by a run upsert lands in the port."""
    db.upsert_session(_session_row("sess-1", user_id="user-1"))
    db.upsert_run(
        run={"run_id": "run-1", "status": "paused", "messages": [], "tools": []},
        session_id="sess-1",
    )
    await db.persist_now("sess-1")

    stored = await store.load_harness_state("sess-1")
    assert stored is not None
    row = json.loads(stored)
    assert row["session_id"] == "sess-1"
    assert [run["run_id"] for run in (row.get("runs") or [])] == ["run-1"]
    assert row["runs"][0]["status"] == "paused"


@pytest.mark.asyncio
async def test_new_facade_hydrates_session_from_port(
    db: NeutralBackedDb, store: InMemorySessionPersistence
) -> None:
    """A brand-new facade (fresh process) rebuilds the session from the port."""
    import asyncio

    session = _session_row("sess-1", runs=[{"run_id": "run-1", "status": "completed"}])
    db.upsert_session(session)
    db.upsert_run(run={"run_id": "run-1", "status": "completed"}, session_id="sess-1")
    await db.persist_now("sess-1")

    # Adapter contract: preload before the turn (or read on a worker thread,
    # the production to_thread path). Both must serve the durable row.
    fresh = NeutralBackedDb(store, label="test-restart")
    await fresh.preload("sess-1")
    served = fresh.get_session("sess-1")
    assert served is not None
    assert served.session_id == "sess-1"

    worker = NeutralBackedDb(store, label="test-worker")
    served_worker = await asyncio.to_thread(worker.get_session, "sess-1")
    assert served_worker is not None
    assert served_worker.session_id == "sess-1"


def test_get_session_without_store_is_in_memory_only(
    store: InMemorySessionPersistence,
) -> None:
    """Without a port implementation the facade degrades to in-memory."""
    bare = NeutralBackedDb(None)
    bare.upsert_session(_session_row("sess-x"))
    assert bare.get_session("sess-x") is not None
    assert bare.persistence is None


@pytest.mark.asyncio
async def test_preload_is_idempotent(db: NeutralBackedDb) -> None:
    session = _session_row("sess-1")
    db.upsert_session(session)
    await db.preload("sess-1")  # warm: no-op
    assert db.get_session("sess-1") is not None
    await db.preload("missing-session")  # cold, no store row: no-op miss


@pytest.mark.asyncio
async def test_write_through_preserves_order_even_with_a_slow_store() -> None:
    """A slow first write must not overwrite a newer snapshot.

    The facade queues fire-and-forget writes on one serialized worker, so the
    durable blob reflects the last mutation rather than whichever port call
    finished last.
    """

    class _DelayedFirstWrite(InMemorySessionPersistence):
        calls = 0

        async def save_harness_state(self, session_id: str, state_json: str) -> None:
            type(self).calls += 1
            if type(self).calls == 1:
                await asyncio.sleep(0.05)
            await super().save_harness_state(session_id, state_json)

    store = _DelayedFirstWrite()
    db = NeutralBackedDb(store, label="ordered")
    db.upsert_session(_session_row("sess-1", user_id="first"))
    db.rename_session("sess-1", SessionType.AGENT, "new-name")
    await db.persist_now("sess-1")

    stored = await store.load_harness_state("sess-1")
    assert stored is not None
    assert json.loads(stored)["session_data"]["session_name"] == "new-name"


@pytest.mark.asyncio
async def test_persist_now_flushes_writes_queued_on_another_loop() -> None:
    """The pause seam runs on the request loop after an agent-loop turn.

    Agno mutates the row on the agent thread's own event loop; the request loop
    then flushes the pause snapshot. That flush must not await a task bound to
    the agent loop, and it must still write the newest row.
    """

    class _SlowFirstWrite(InMemorySessionPersistence):
        calls = 0

        async def save_harness_state(self, session_id: str, state_json: str) -> None:
            type(self).calls += 1
            if type(self).calls == 1:
                await asyncio.sleep(0.05)
            await super().save_harness_state(session_id, state_json)

    store = _SlowFirstWrite()
    db = NeutralBackedDb(store, label="cross-loop")

    def agent_loop_turn() -> None:
        async def run() -> None:
            db.upsert_session(_session_row("sess-1", user_id="first"))

        asyncio.run(run())

    await asyncio.to_thread(agent_loop_turn)
    db.rename_session("sess-1", SessionType.AGENT, "new-name")
    await db.persist_now("sess-1")

    stored = await store.load_harness_state("sess-1")
    assert stored is not None
    assert json.loads(stored)["session_data"]["session_name"] == "new-name"


def test_no_harness_file_is_created(
    db: NeutralBackedDb, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The per-project Agno SQLite file is retired: no db file path is used."""
    import agno.db.sqlite.sqlite as agno_sqlite

    def fail_sqlite(*args: object, **kwargs: object) -> None:
        raise AssertionError("Agno SqliteDb must not be instantiated by the adapter")

    monkeypatch.setattr(agno_sqlite, "SqliteDb", fail_sqlite)
    db.upsert_session(_session_row("sess-1"))
    db.upsert_run(run={"run_id": "run-1"}, session_id="sess-1")
    assert not any(tmp_path.iterdir())


def _session_row(
    session_id: str,
    *,
    user_id: str | None = None,
    runs: list[dict[str, object]] | None = None,  # type: ignore[type-var]
) -> object:
    from agno.session.agent import AgentSession

    # runs is tolerated loosely here on purpose: agno's public constructor
    # wants RunOutput objects, but the facade stores whatever agno hands it
    # (dicts from run.to_dict() on the write path).
    return AgentSession(
        session_id=session_id,
        user_id=user_id,
        runs=runs,  # type: ignore[arg-type]
        session_data={},
    )
