"""Tests for the local-init cross-process lock."""

from __future__ import annotations

from pathlib import Path

from kontext.runtime.local.init_lock import local_init_lock


def test_lock_creates_lock_file(tmp_path: Path) -> None:
    with local_init_lock(tmp_path):
        assert (tmp_path / "local-init.lock").exists()


def test_nested_lock_times_out_without_hanging(tmp_path: Path) -> None:
    """A second acquisition in the same process waits then proceeds (no hang).

    flock is per open file description, so a nested acquisition contends like a
    different process would. It must not hang forever.
    """
    with (
        local_init_lock(tmp_path, timeout_seconds=0.1),
        local_init_lock(tmp_path, timeout_seconds=0.1),
    ):
        assert True


def test_lock_times_out_when_held_elsewhere(tmp_path: Path) -> None:
    """A second holder that cannot acquire in time proceeds rather than hanging."""
    import fcntl

    lock_path = tmp_path / "local-init.lock"
    with open(lock_path, "a+") as holder:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Should return quickly (timeout) rather than raise.
        with local_init_lock(tmp_path, timeout_seconds=0.1):
            assert True
        fcntl.flock(holder.fileno(), fcntl.LOCK_UN)
