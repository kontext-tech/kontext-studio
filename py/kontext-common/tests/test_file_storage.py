from __future__ import annotations

from pathlib import Path

import pytest

from kontext.common.utils.file_storage import (
    get_file_storage_path,
    get_project_storage_path,
)
from kontext.common.utils.path_policy import PathAccessDeniedError


def test_get_file_storage_path_defaults_to_home_kontext_storage(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("FILE_STORAGE_PATH", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    storage_path = get_file_storage_path()

    assert storage_path == str(tmp_path / ".kontext" / "storage")
    assert Path(storage_path).is_dir()


def test_get_file_storage_path_expands_user_home(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FILE_STORAGE_PATH", "~/custom-kontext-storage")
    monkeypatch.setenv("HOME", str(tmp_path))

    storage_path = get_file_storage_path()

    assert storage_path == str(tmp_path / "custom-kontext-storage")
    assert Path(storage_path).is_dir()


def test_get_project_storage_path_uses_projects_prefix(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "storage"))

    project_path = get_project_storage_path("project-123", "sessions", "query.db")

    assert project_path == str(
        tmp_path / "storage" / "projects" / "project-123" / "sessions" / "query.db"
    )
    assert (tmp_path / "storage" / "projects" / "project-123" / "sessions").is_dir()


def test_get_project_storage_path_rejects_parent_traversal(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("KONTEXT_ALLOWED_PATHS", raising=False)

    with pytest.raises(PathAccessDeniedError):
        get_project_storage_path("project-123", "..", "..", "..", "escaped.txt")


def test_get_project_storage_path_rejects_absolute_sub_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("KONTEXT_ALLOWED_PATHS", raising=False)

    with pytest.raises(PathAccessDeniedError):
        get_project_storage_path("project-123", "/etc/passwd")
