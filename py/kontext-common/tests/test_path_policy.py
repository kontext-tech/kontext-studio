from __future__ import annotations

import os
from pathlib import Path

import pytest

from kontext.common.utils.path_policy import (
    PathAccessDeniedError,
    ensure_within_allowed_roots,
    get_allowed_roots,
    is_within_allowed_roots,
)


@pytest.fixture()
def storage_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "storage"
    monkeypatch.setenv("FILE_STORAGE_PATH", str(root))
    monkeypatch.delenv("KONTEXT_ALLOWED_PATHS", raising=False)
    return root.resolve()


def test_allowed_roots_default_to_storage(storage_root: Path) -> None:
    assert get_allowed_roots() == (storage_root,)


def test_allowed_roots_include_env_entries(
    storage_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extra = tmp_path / "extra"
    extra.mkdir()
    monkeypatch.setenv("KONTEXT_ALLOWED_PATHS", os.pathsep.join([str(extra), ""]))

    roots = get_allowed_roots()

    assert storage_root in roots
    assert extra.resolve() in roots
    # A trailing separator must not produce an empty root.
    assert Path("") not in roots


def test_ensure_within_returns_canonical_path(storage_root: Path) -> None:
    target = storage_root / "projects" / "p-one" / ".." / "p-one" / "file.txt"

    assert ensure_within_allowed_roots(target) == (storage_root / "projects" / "p-one" / "file.txt")


def test_ensure_within_rejects_parent_traversal(storage_root: Path) -> None:
    with pytest.raises(PathAccessDeniedError):
        ensure_within_allowed_roots(storage_root / ".." / "elsewhere")


def test_ensure_within_rejects_absolute_path_outside_roots(storage_root: Path) -> None:
    with pytest.raises(PathAccessDeniedError):
        ensure_within_allowed_roots(Path("/etc/passwd"))


def test_ensure_within_accepts_explicit_roots(tmp_path: Path) -> None:
    explicit = tmp_path / "other"
    explicit.mkdir()

    assert ensure_within_allowed_roots(explicit / "file.txt", roots=(explicit,)) == (
        explicit / "file.txt"
    )

    with pytest.raises(PathAccessDeniedError):
        ensure_within_allowed_roots(explicit / "file.txt", roots=(tmp_path / "elsewhere",))


def test_is_within_allowed_roots(storage_root: Path) -> None:
    assert is_within_allowed_roots(storage_root / "a" / "b")
    assert not is_within_allowed_roots(Path("/some/other/place"))
