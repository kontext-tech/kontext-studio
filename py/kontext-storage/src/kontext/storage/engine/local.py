"""
Local filesystem implementation of the StorageEngine.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import StorageEngine

_IS_WINDOWS = platform.system() == "Windows"


class _FileLock:
    """Thin cross-platform advisory file-lock using a separate ``.lock`` file."""

    def __init__(self, path: Path) -> None:
        self._lock_path = path.with_suffix(path.suffix + ".lock")
        self._fd: int | None = None

    def __enter__(self) -> _FileLock:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fd = os.open(str(self._lock_path), os.O_CREAT | os.O_RDWR)
        if _IS_WINDOWS:
            import msvcrt

            msvcrt.locking(self._fd, msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
        else:
            import fcntl

            fcntl.flock(self._fd, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._fd is not None:
            if _IS_WINDOWS:
                import msvcrt

                with contextlib.suppress(OSError):
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None


def _read_json(path: Path) -> Any:
    """Read and parse a JSON file; return ``None`` if it does not exist."""
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    """Atomically write *data* as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


_PROJECT_SUBDIRS = [
    "config",
    "data/raw",
    "data/embeddings",
    "results",
    "logs",
]

_PROJECT_COLLECTION_FILES = [
    "agent_sessions",
    "artifacts",
    "chat_sessions",
    "chat_session_artifacts",
    "events",
    "files",
    "job_run_logs",
    "job_runs",
    "job_triggers",
    "jobs",
    "llm_providers",
    "queries",
    "query_sessions",
]


class LocalStorageEngine(StorageEngine):
    """File-based lake storage engine."""

    def __init__(self, lake_root: str | Path | None = None) -> None:
        if lake_root is None:
            lake_root = os.environ.get("KONTEXT_LAKE_PATH", str(Path.home() / ".kontext"))
        self._root = Path(lake_root).resolve()
        self._lock = threading.RLock()

    @property
    def root(self) -> Path:
        """Absolute path of the lake root directory."""
        return self._root

    def _global_path(self, name: str) -> Path:
        return self._root / f"{name}.json"

    def _collection_path(self, collection: str, project_id: str) -> Path:
        return self._root / "projects" / project_id / "config" / f"{collection}.json"

    def _project_dir(self, project_id: str) -> Path:
        return self._root / "projects" / project_id

    def get_global(self, name: str) -> dict[str, Any] | list[Any] | None:
        path = self._global_path(name)
        with _FileLock(path):
            return _read_json(path)

    def put_global(self, name: str, data: dict[str, Any] | list[Any]) -> None:
        path = self._global_path(name)
        with _FileLock(path):
            _write_json(path, data)

    def _load_collection(self, path: Path) -> list[dict[str, Any]]:
        data = _read_json(path)
        if data is None:
            return []
        if isinstance(data, list):
            return data
        return []

    def get(self, collection: str, record_id: str, *, project_id: str) -> dict[str, Any] | None:
        path = self._collection_path(collection, project_id)
        with self._lock, _FileLock(path):
            records = self._load_collection(path)
            for rec in records:
                if rec.get("id") == record_id:
                    return rec
            return None

    def list(
        self,
        collection: str,
        *,
        project_id: str,
        filters: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        path = self._collection_path(collection, project_id)
        with self._lock, _FileLock(path):
            records = self._load_collection(path)

        result = self._apply_filters(records, filters)
        if offset:
            result = result[offset:]
        if limit is not None:
            result = result[:limit]
        return result

    def count(
        self, collection: str, *, project_id: str, filters: dict[str, Any] | None = None
    ) -> int:
        path = self._collection_path(collection, project_id)
        with self._lock, _FileLock(path):
            records = self._load_collection(path)
        return len(self._apply_filters(records, filters))

    def create(self, collection: str, data: dict[str, Any], *, project_id: str) -> dict[str, Any]:
        path = self._collection_path(collection, project_id)
        record = dict(data)
        if "id" not in record:
            record["id"] = str(uuid4())
        with self._lock, _FileLock(path):
            records = self._load_collection(path)
            records.append(record)
            _write_json(path, records)
        return record

    def update(
        self, collection: str, record_id: str, data: dict[str, Any], *, project_id: str
    ) -> dict[str, Any]:
        path = self._collection_path(collection, project_id)
        with self._lock, _FileLock(path):
            records = self._load_collection(path)
            for i, rec in enumerate(records):
                if rec.get("id") == record_id:
                    rec.update(data)
                    records[i] = rec
                    _write_json(path, records)
                    return rec
            raise KeyError(
                f"Record {record_id!r} not found in {collection!r} (project {project_id})"
            )

    def delete(self, collection: str, record_id: str, *, project_id: str) -> bool:
        path = self._collection_path(collection, project_id)
        with self._lock, _FileLock(path):
            records = self._load_collection(path)
            new_records = [r for r in records if r.get("id") != record_id]
            if len(new_records) == len(records):
                return False
            _write_json(path, new_records)
            return True

    def query(
        self, collection: str, *, project_id: str, predicate: Any | None = None
    ) -> list[dict[str, Any]]:
        path = self._collection_path(collection, project_id)
        with self._lock, _FileLock(path):
            records = self._load_collection(path)
        if predicate is None:
            return records
        return [r for r in records if predicate(r)]

    def ensure_project_structure(self, project_id: str) -> None:
        proj_dir = self._project_dir(project_id)
        for sub in _PROJECT_SUBDIRS:
            (proj_dir / sub).mkdir(parents=True, exist_ok=True)
        for coll_name in _PROJECT_COLLECTION_FILES:
            coll_path = proj_dir / "config" / f"{coll_name}.json"
            if not coll_path.exists():
                _write_json(coll_path, [])

    def project_exists(self, project_id: str) -> bool:
        return self._project_dir(project_id).is_dir()

    def get_project_data_path(self, project_id: str, subdir: str = "") -> str:
        base = self._project_dir(project_id) / "data"
        if subdir:
            base = base / subdir
        return str(base)

    @staticmethod
    def _apply_filters(
        records: list[dict[str, Any]], filters: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        if not filters:
            return list(records)
        result: list[dict[str, Any]] = []
        for rec in records:
            if all(rec.get(k) == v for k, v in filters.items()):
                result.append(rec)
        return result


__all__ = ["LocalStorageEngine", "_read_json", "_write_json"]
