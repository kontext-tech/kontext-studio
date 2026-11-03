"""Resource limits for kernel child processes.

A kernel executes user code, so it is launched with best-effort OS caps: POSIX
``rlimit`` values via ``preexec_fn`` (address space, CPU seconds, file size,
open files, processes) and, on Windows, a Job Object that kills the kernel when
the supervisor dies. Defaults target real-data cells (multi-GB pandas frames,
minutes-long fits); pass ``cpu_seconds=0`` to skip the cumulative CPU cap,
which session kernels do because one process serves every cell of a session.

Every limit is best-effort: a platform or sandbox that rejects ``setrlimit`` must
not prevent the kernel from starting.
"""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MEMORY_LIMIT_MB = 8192
DEFAULT_CPU_SECONDS = 600
DEFAULT_FILE_SIZE_LIMIT_BYTES = 1073741824
# Open-file cap for the kernel child. The harness needs room for its channel
# sockets plus transient fds while importing heavy libraries (numpy, pandas,
# duckdb map many shared objects during import), so this stays well above the
# default 64-fd floor some macOS/Linux configurations inherit.
DEFAULT_OPEN_FILE_LIMIT = 256
# Headroom above the caller's current task count for the kernel's own threads.
# RLIMIT_NPROC is enforced per real UID, not per process, so an absolute cap can
# sit below the number of tasks the user already owns (for example a shared CI
# account). See ``_count_user_tasks``.
_NPROC_HEADROOM = 128


def _count_user_tasks() -> int | None:
    """Best-effort count of tasks owned by the current real UID.

    ``RLIMIT_NPROC`` counts every task (process *and* thread) belonging to the
    real UID. An absolute cap such as 32 is therefore unsafe: on a shared user
    that already owns more tasks than that, the kernel child cannot create its
    own threads and dies during startup. Counting lets us raise the cap above
    current usage while still bounding runaway forks.

    Returns ``None`` when task accounting is unavailable (for example macOS,
    which has no ``/proc``), in which case the NPROC cap is skipped.
    """
    proc = Path("/proc")
    if not proc.is_dir():  # pragma: no cover - non-Linux
        return None

    uid = os.getuid()
    count = 0
    try:
        for entry in proc.iterdir():
            if not entry.name.isdigit():
                continue
            with suppress(OSError):
                if entry.stat().st_uid == uid:
                    count += 1
    except OSError:  # pragma: no cover - /proc read failure
        return None
    return count or None


@dataclass(frozen=True)
class ProcessLimits:
    """Resource caps applied to a launched kernel process.

    ``cpu_seconds`` bounds *cumulative* process CPU: right-sized for a one-shot
    kernel (the one-shot runner passes its wall timeout), but wrong for a
    long-lived session kernel, where one process serves every cell of a
    session and CPU accumulates — a cap there would kill the kernel mid-task
    and silently wipe the session namespace. Session spawns therefore pass
    ``cpu_seconds=0`` (per-cell wall timeouts plus interrupt escalation bound
    runaway cells instead, and the AS/NPROC/FSIZE caps stay active).
    """

    memory_limit_mb: int = DEFAULT_MEMORY_LIMIT_MB
    cpu_seconds: int = DEFAULT_CPU_SECONDS
    file_size_limit_bytes: int = DEFAULT_FILE_SIZE_LIMIT_BYTES


def _posix_preexec(limits: ProcessLimits) -> Any:
    import resource

    # Computed in the parent (before fork) because ``_count_user_tasks`` must not
    # run between fork and exec, where importing/locking is unsafe.
    current_tasks = _count_user_tasks()
    nproc_cap = None if current_tasks is None else current_tasks + _NPROC_HEADROOM

    def _preexec() -> None:
        os.setsid()
        # Skip RLIMIT_AS on darwin: macOS (like Windows) counts *virtual*
        # address space against the cap, and CPython/numpy reserve huge VA
        # ranges, so the cap can kill perfectly healthy kernels mid-import.
        # Linux keeps it: there the cap meaningfully bounds runaway heaps.
        if sys.platform != "darwin":  # pragma: no cover - platform branch
            with suppress(Exception):
                resource.setrlimit(
                    resource.RLIMIT_AS,
                    (
                        limits.memory_limit_mb * 1024 * 1024,
                        limits.memory_limit_mb * 1024 * 1024,
                    ),
                )
        if limits.cpu_seconds > 0:
            with suppress(Exception):
                resource.setrlimit(
                    resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds + 1)
                )
        with suppress(Exception):
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (limits.file_size_limit_bytes, limits.file_size_limit_bytes),
            )
        with suppress(Exception):
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        with suppress(Exception):
            resource.setrlimit(
                resource.RLIMIT_NOFILE, (DEFAULT_OPEN_FILE_LIMIT, DEFAULT_OPEN_FILE_LIMIT)
            )
        if nproc_cap is not None:
            with suppress(Exception):
                resource.setrlimit(resource.RLIMIT_NPROC, (nproc_cap, nproc_cap))

    return _preexec


def _popen_limit_kwargs(limits: ProcessLimits) -> dict[str, Any]:
    """Return ``Popen`` kwargs that impose *limits* (POSIX) or set up Windows."""
    if os.name == "nt":  # pragma: no cover - Windows-only
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"preexec_fn": _posix_preexec(limits)}


class WindowsJobObject:
    """A Windows Job Object that terminates the kernel when closed.

    Configured with ``KILL_ON_JOB_CLOSE`` so closing the handle (including on
    supervisor crash) tears down the kernel and anything it spawned.
    """

    def __init__(self, pid: int) -> None:  # pragma: no cover - Windows-only
        import ctypes
        from ctypes import wintypes

        win_dll = getattr(ctypes, "WinDLL", None)
        if win_dll is None:
            raise OSError("ctypes.WinDLL is unavailable on this platform")
        self._kernel32 = win_dll("kernel32", use_last_error=True)

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("ReadOperationCount", ctypes.c_uint64),
                ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64),
                ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64),
                ("OtherTransferCount", ctypes.c_uint64),
            ]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self._job = self._kernel32.CreateJobObjectW(None, None)
        if not self._job:
            raise OSError("Failed to create Windows Job Object")

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not self._kernel32.SetInformationJobObject(
            self._job,
            9,  # JobObjectExtendedLimitInformation
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            raise OSError("Failed to configure Windows Job Object")

        handle = self._kernel32.OpenProcess(0x0100 | 0x0001, False, pid)
        if not handle:
            raise OSError("Failed to open process for Windows Job Object")
        try:
            if not self._kernel32.AssignProcessToJobObject(self._job, handle):
                raise OSError("Failed to assign process to Windows Job Object")
        finally:
            self._kernel32.CloseHandle(handle)

    def terminate(self) -> None:  # pragma: no cover - Windows-only
        self._kernel32.TerminateJobObject(self._job, 1)

    def close(self) -> None:  # pragma: no cover - Windows-only
        if getattr(self, "_job", None):
            self._kernel32.CloseHandle(self._job)
            self._job = None


def popen_limit_kwargs(limits: ProcessLimits) -> dict[str, Any]:
    """Public wrapper for the Popen kwargs that impose *limits*."""
    return _popen_limit_kwargs(limits)


def attach_windows_job_object(
    process: subprocess.Popen[Any],
) -> WindowsJobObject | None:
    """Attach a Job Object to a just-launched Windows child, if possible."""
    if os.name != "nt":  # pragma: no cover - non-Windows
        return None
    with suppress(Exception):
        return WindowsJobObject(process.pid)
    return None
