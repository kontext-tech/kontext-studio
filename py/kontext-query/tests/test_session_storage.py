from __future__ import annotations

from pathlib import Path

from kontext.common.query.session_storage import (
    get_project_sessions_directory,
    get_session_database_path,
)


def test_session_storage_uses_projects_prefix(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "storage"))

    db_path = get_session_database_path("Project-123", "session-456", persistent=True)
    assert db_path is not None

    assert db_path == str(
        tmp_path / "storage" / "projects" / "project-123" / "sessions" / "session-456.db"
    )
    assert Path(db_path).parent.is_dir()


def test_project_sessions_directory_uses_projects_prefix(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "storage"))

    sessions_dir = get_project_sessions_directory("Project-123")

    assert sessions_dir == str(tmp_path / "storage" / "projects" / "project-123" / "sessions")
