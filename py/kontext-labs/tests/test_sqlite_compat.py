"""Tests for the local SQLite runtime compatibility guard."""

from __future__ import annotations

import argparse
import sqlite3

import pytest

from kontext.labs.sqlite_compat import ensure_supported_sqlite


@pytest.mark.parametrize(
    "version",
    [(3, 45, 2), (3, 50, 4), (3, 51, 2), (3, 54, 1)],
)
def test_accepts_supported_sqlite_versions(
    monkeypatch: pytest.MonkeyPatch, version: tuple[int, int, int]
) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", version)

    ensure_supported_sqlite()


@pytest.mark.parametrize("version", [(3, 51, 0), (3, 51, 1)])
def test_rejects_deadlocking_sqlite_versions(
    monkeypatch: pytest.MonkeyPatch, version: tuple[int, int, int]
) -> None:
    monkeypatch.setattr(sqlite3, "sqlite_version_info", version)
    monkeypatch.setattr(sqlite3, "sqlite_version", ".".join(map(str, version)))

    with pytest.raises(RuntimeError) as excinfo:
        ensure_supported_sqlite()

    message = str(excinfo.value)
    assert f"SQLite {'.'.join(map(str, version))}" in message
    assert "3.51.2" in message
    assert "uv tool install --managed-python" in message


def test_serve_exits_cleanly_on_unsafe_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CLI should print the guidance rather than a traceback."""

    def _raise() -> None:
        raise RuntimeError("unsafe sqlite")

    monkeypatch.setattr("kontext.labs.cli.ensure_supported_sqlite", _raise)

    from kontext.labs.cli import _cmd_serve

    args = argparse.Namespace(
        dist_dir=None,
        lake_path=None,
        host="127.0.0.1",
        port=8000,
        open=False,
        reload=False,
    )

    with pytest.raises(SystemExit) as excinfo:
        _cmd_serve(args)

    assert "unsafe sqlite" in str(excinfo.value)
