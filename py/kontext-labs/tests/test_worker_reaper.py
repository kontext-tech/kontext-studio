"""Unit tests for orphaned worker/kernel reaping."""

from __future__ import annotations

from kontext.labs.worker_reaper import (
    Orphan,
    ProcessSnapshot,
    _parse_ps_snapshot,
    reap_orphaned_processes,
    select_orphans,
)


def _snapshot(pid: int, parent: int, command: str) -> ProcessSnapshot:
    return ProcessSnapshot(pid=pid, parent_pid=parent, command=command)


WORKER = "Python -m kontext.labs.local_worker"
HARNESS = "/repo/py/kontext-kernel/src/kontext/kernel/harness.py"
KERNEL_INVOKED = f"/repo/.venv/bin/python -I {HARNESS} /some/ws/kernel-connection.json"


def test_selects_orphaned_worker_with_parent_gone() -> None:
    snapshots = [
        _snapshot(100, 50, WORKER),  # parent 50 not in table -> orphan
        _snapshot(200, 100, WORKER),  # parent 100 alive -> live generation
    ]
    orphans = select_orphans(snapshots, this_pid=300)
    assert orphans == [Orphan(pid=100, kind="worker")]


def test_selects_orphaned_kernel_children() -> None:
    snapshots = [
        _snapshot(400, 1, KERNEL_INVOKED),  # orphaned by its worker
        _snapshot(9000, 1, "zsh"),  # user shell (never a reap candidate)
        _snapshot(99, 9000, WORKER),  # live worker, parent shell alive
        _snapshot(500, 99, KERNEL_INVOKED),  # live worker's kernel -> keep
    ]
    orphans = select_orphans(snapshots, this_pid=1)
    assert orphans == [Orphan(pid=400, kind="kernel")]


def test_skips_this_process_and_kernel_harness_without_isolation_flag() -> None:
    snapshots = [
        _snapshot(700, 1, WORKER),  # this pid -> skipped
        _snapshot(901, 1, f"-m {HARNESS} /ws/kernel-connection.json"),  # no -I
    ]
    assert select_orphans(snapshots, this_pid=700) == []


def test_never_kills_processes_with_live_parents() -> None:
    snapshots = [
        _snapshot(50, 1, "uv run kontext serve"),  # live server
        _snapshot(100, 50, WORKER),  # live server's worker
        _snapshot(600, 100, KERNEL_INVOKED),  # live worker's kernel
    ]
    assert select_orphans(snapshots, this_pid=2) == []


def test_parser_ignores_malformed_rows() -> None:
    parsed = _parse_ps_snapshot("  1234   1 Python -m kontext.labs.local_worker\njunk\n\n")
    assert parsed == [ProcessSnapshot(pid=1234, parent_pid=1, command=WORKER)]


def test_reap_terminates_every_orphan() -> None:
    killed: list[int] = []
    orphans = [Orphan(pid=11, kind="worker"), Orphan(pid=22, kind="kernel")]

    def fake_scan() -> list[Orphan]:
        return orphans

    def fake_terminate(pid: int, grace: float) -> None:
        killed.append(pid)

    reaped = reap_orphaned_processes(scan=fake_scan, terminate=fake_terminate, grace_seconds=1.0)
    assert reaped == orphans
    assert killed == [11, 22]


def test_reap_skips_orphans_that_disappeared_before_the_kill() -> None:
    """Re-verification must not signal a pid that changed between scan and kill."""
    killed: list[int] = []
    scans = iter(
        [
            [Orphan(pid=11, kind="worker"), Orphan(pid=22, kind="kernel")],
            [Orphan(pid=22, kind="kernel")],  # 11 exited (or its pid was recycled)
        ]
    )

    def fake_scan() -> list[Orphan]:
        return next(scans)

    def fake_terminate(pid: int, grace: float) -> None:
        killed.append(pid)

    reaped = reap_orphaned_processes(scan=fake_scan, terminate=fake_terminate, grace_seconds=1.0)
    assert reaped == [Orphan(pid=22, kind="kernel")]
    assert killed == [22]
