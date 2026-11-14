"""Reap previous-generation local workers (and their kernels) on startup.

The worker runs detached from its server (``start_new_session=True``) so the
server watchdog can restart a crashed worker. That leaves one hazard: when the
server restarts, the old worker keeps polling the same job queue as an orphan
process. Two generations then race for every job, and an orphan may run code
loaded before a redeploy — which historically produced kernels that died at
spawn under resource limits the new code had already fixed.

Jupyter solves the same problem by treating runtime pid/connection files as
authoritative: stale processes are detected and cleaned up when a new
supervisor starts. The equivalent here is command-line based liveness: a
previous-generation process is *orphaned* when its parent (the server that
spawned it) is gone. A starting worker terminates those orphans before
serving; workers whose parent is alive (another running server) are left
alone.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

ORPHAN_REAP_GRACE_SECONDS = 3.0

_WORKER_COMMAND_MARKER = "-m kontext.studio.local_worker"
_KERNEL_COMMAND_MARKER = "kontext/kernel/harness.py"


@dataclass(frozen=True)
class ProcessSnapshot:
    """One process row from the platform's process table."""

    pid: int
    parent_pid: int | None
    command: str


class Orphan(NamedTuple):
    pid: int
    kind: str  # "worker" | "kernel"


def _parse_ps_snapshot(ps_output: str) -> list[ProcessSnapshot]:
    """Parse ``ps -axo pid=,ppid=,command=`` output into snapshots."""
    snapshots: list[ProcessSnapshot] = []
    for line in ps_output.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        parts = trimmed.split(None, 2)
        if len(parts) < 3:
            continue
        pid_text, parent_text, command = parts
        if not pid_text.isdigit() or not parent_text.isdigit():
            continue
        snapshots.append(
            ProcessSnapshot(pid=int(pid_text), parent_pid=int(parent_text), command=command)
        )
    return snapshots


def _read_ps_snapshot() -> list[ProcessSnapshot]:
    """Collect the process table via ``ps`` (available on macOS and Linux)."""
    ps_path = "/bin/ps" if os.path.exists("/bin/ps") else "ps"
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        proc = subprocess.run(
            [ps_path, "-axo", "pid=,ppid=,command="],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        if proc.returncode == 0:
            return _parse_ps_snapshot(proc.stdout)
    return []


def select_orphans(
    snapshots: list[ProcessSnapshot],
    *,
    this_pid: int,
) -> list[Orphan]:
    """Return previous-generation worker/kernel processes whose parent is gone.

    Process reparenting makes this safe for double-claim races: a worker whose
    parent is still alive belongs to another running server and is untouched,
    as is any process spawned by a live worker (its kernel's parent is that
    live worker).
    """
    alive = {snapshot.pid for snapshot in snapshots}
    orphans: list[Orphan] = []
    for snapshot in snapshots:
        if snapshot.pid in (this_pid, 1):
            continue
        if snapshot.parent_pid not in (None, 0, 1) and snapshot.parent_pid in alive:
            continue
        kind: str | None = None
        if _WORKER_COMMAND_MARKER in snapshot.command:
            kind = "worker"
        elif _KERNEL_COMMAND_MARKER in snapshot.command and "-I" in snapshot.command:
            kind = "kernel"
        if kind is not None:
            orphans.append(Orphan(pid=snapshot.pid, kind=kind))
    return orphans


def _scan_orphans_posix() -> list[Orphan]:
    return select_orphans(_read_ps_snapshot(), this_pid=os.getpid())


def _scan_orphans_windows() -> list[Orphan]:  # pragma: no cover - Windows-only
    """Scan via CIM; orphan means the parent process no longer exists."""
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30.0,
        )
        if proc.returncode != 0:
            return []

        rows = json.loads(proc.stdout or "[]")
        if isinstance(rows, dict):  # single row comes back as an object
            rows = [rows]
        snapshots = [
            ProcessSnapshot(
                pid=int(row["ProcessId"] or 0),
                parent_pid=int(row["ParentProcessId"] or 0) or None,
                command=str(row.get("CommandLine") or ""),
            )
            for row in rows
        ]
        return select_orphans(snapshots, this_pid=os.getpid())
    return []


def scan_orphans() -> list[Orphan]:
    """Return orphaned previous-generation processes on this machine."""
    try:
        return _scan_orphans_windows() if os.name == "nt" else _scan_orphans_posix()
    except Exception:
        return []


def _terminate(pid: int, *, grace_seconds: float) -> None:
    """Terminate *pid*, escalating to kill when it does not exit in time."""
    if os.name == "nt":  # pragma: no cover - Windows-only path
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=10.0,
                check=False,
            )
        return

    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        with contextlib.suppress(OSError):
            os.kill(pid, 0)
            time.sleep(0.05)
            continue
        return
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        os.kill(pid, signal.SIGKILL)


def reap_orphaned_processes(
    *,
    scan: Callable[[], list[Orphan]] = scan_orphans,
    terminate: Callable[[int, float], None] = lambda pid, grace: _terminate(
        pid, grace_seconds=grace
    ),
    grace_seconds: float = ORPHAN_REAP_GRACE_SECONDS,
) -> list[Orphan]:
    """Terminate orphaned previous-generation workers/kernels; return the reaped set.

    Orphans are re-verified against a fresh scan immediately before signalling, so
    a process that exited (and whose pid was recycled by an unrelated process) in
    the scan/kill window is not signalled by mistake. This narrows, but does not
    fully close, the pid-reuse window; a start-time check would be required to
    close it completely.
    """
    orphans = scan()
    still_orphaned = {(orphan.pid, orphan.kind) for orphan in scan()}
    reaped: list[Orphan] = []
    for orphan in orphans:
        if (orphan.pid, orphan.kind) not in still_orphaned:
            continue
        terminate(orphan.pid, grace_seconds)
        reaped.append(orphan)
    return reaped
