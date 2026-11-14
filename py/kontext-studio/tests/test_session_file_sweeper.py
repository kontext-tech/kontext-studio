"""Tests for the orphaned query-session file sweeper."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from kontext.studio import local_worker


def test_sweep_project_session_files_removes_orphans_and_keeps_live(
    tmp_path: Path, monkeypatch
) -> None:
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    live_id = "11111111-1111-1111-1111-111111111111"
    orphan_id = "22222222-2222-2222-2222-222222222222"
    live_file = sessions_dir / f"{live_id}.db"
    orphan_file = sessions_dir / f"{orphan_id}.db"
    orphan_wal = sessions_dir / f"{orphan_id}.db.wal"
    for path in (live_file, orphan_file, orphan_wal):
        path.write_bytes(b"x")

    monkeypatch.setattr(
        local_worker,
        "_expected_session_db_names",
        lambda project_id: {f"{live_id}.db"},
    )
    monkeypatch.setattr(
        "kontext.common.query.session_storage.get_project_sessions_directory",
        lambda project_id: str(sessions_dir),
    )
    monkeypatch.setattr(local_worker, "_SESSION_FILE_SWEEP_GRACE_SECONDS", 0.0)

    removed = local_worker._sweep_project_session_files("project-1", now=time.time())

    assert removed == 2
    assert live_file.exists()
    assert not orphan_file.exists()
    assert not orphan_wal.exists()


def test_sweep_project_session_files_respects_grace_period(tmp_path: Path, monkeypatch) -> None:
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    orphan_file = sessions_dir / "33333333-3333-3333-3333-333333333333.db"
    orphan_file.write_bytes(b"x")

    monkeypatch.setattr(local_worker, "_expected_session_db_names", lambda project_id: set())
    monkeypatch.setattr(
        "kontext.common.query.session_storage.get_project_sessions_directory",
        lambda project_id: str(sessions_dir),
    )

    # A freshly written file is within the grace window and must survive.
    removed = local_worker._sweep_project_session_files("project-1", now=time.time())
    assert removed == 0
    assert orphan_file.exists()


@pytest.mark.asyncio
async def test_sweep_project_result_stores_removes_unreferenced(
    tmp_path: Path, monkeypatch
) -> None:
    from kontext.storage import clear_storage_provider_cache

    clear_storage_provider_cache()
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(tmp_path / "storage"))

    from kontext.storage import get_storage_provider

    get_storage_provider(force_new=True)
    project_id = "project-1"
    store_dir = tmp_path / "storage" / "projects" / project_id / "resources" / ".data"
    store_dir.mkdir(parents=True)
    referenced = store_dir / "referenced.parquet"
    orphan = store_dir / "orphan.parquet"
    referenced.write_bytes(b"a")
    orphan.write_bytes(b"b")

    from datetime import timedelta

    monkeypatch.setattr(local_worker, "_RESULT_STORE_RETENTION", timedelta(0))
    monkeypatch.setattr(
        local_worker,
        "_referenced_result_stores",
        lambda pid: {"referenced.parquet"},
    )

    removed = await local_worker._sweep_project_result_stores(project_id, now=time.time())

    assert removed == 1
    assert referenced.exists()
    assert not orphan.exists()


@pytest.mark.asyncio
async def test_sweep_project_result_stores_respects_grace(tmp_path: Path, monkeypatch) -> None:
    from kontext.storage import clear_storage_provider_cache, get_storage_provider

    clear_storage_provider_cache()
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(tmp_path / "storage"))
    get_storage_provider(force_new=True)

    project_id = "project-1"
    store_dir = tmp_path / "storage" / "projects" / project_id / "resources" / ".data"
    store_dir.mkdir(parents=True)
    fresh = store_dir / "fresh.parquet"
    fresh.write_bytes(b"b")

    monkeypatch.setattr(local_worker, "_referenced_result_stores", lambda pid: set())

    removed = await local_worker._sweep_project_result_stores(project_id, now=time.time())
    assert removed == 0
    assert fresh.exists()


def test_referenced_result_stores_reads_descriptor_data_path(tmp_path: Path, monkeypatch) -> None:
    """The referenced-set is derived from live ``.dt`` descriptors, not filenames."""

    class _FakeResult:
        def scalars(self):
            return self

        def all(self):
            uri = tmp_path / "storage" / "projects" / "p1" / "resources" / ".dts" / "descriptor.dt"
            uri.parent.mkdir(parents=True, exist_ok=True)
            uri.write_text(
                json.dumps({"metadata": {"dataPath": ".data/abc.parquet"}}), encoding="utf-8"
            )
            return [f"file://{uri}"]

    class _FakeSession:
        def execute(self, _stmt):
            return _FakeResult()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "kontext.data.database.get_sync_db_session",
        lambda: _FakeSession(),
    )
    from kontext.storage import clear_storage_provider_cache

    clear_storage_provider_cache()
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(tmp_path / "storage"))

    referenced = local_worker._referenced_result_stores("11111111-1111-1111-1111-111111111111")

    assert referenced == {"abc.parquet"}
