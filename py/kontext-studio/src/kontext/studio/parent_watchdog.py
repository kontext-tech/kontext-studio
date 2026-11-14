"""Parent-death monitoring for desktop-managed processes.

The desktop shell owns the server process; the server owns the worker. If the
shell is force-quit, the server must not outlive it, and if the server dies the
worker must not leave kernels behind. Both use the same poll-based monitor so
the behavior is identical on macOS and Windows.
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Callable

PARENT_PID_ENV = "KONTEXT_PARENT_PID"

_DEFAULT_POLL_INTERVAL_SECONDS = 1.0


def parent_pid_from_env() -> int | None:
    """Return the configured parent PID, or ``None`` when unset/invalid."""
    raw = os.getenv(PARENT_PID_ENV, "").strip()
    if not raw:
        return None
    try:
        pid = int(raw)
    except ValueError:
        return None
    return pid if pid > 0 else None


def process_exists(pid: int) -> bool:
    """Return whether *pid* is still running.

    ``os.kill(pid, 0)`` is the POSIX probe. Windows has no signal-0 equivalent;
    opening the process with ``SYNCHRONIZE`` and asking whether it has already
    exited is the reliable check.
    """
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        return _windows_process_exists(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _windows_process_exists(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    synchronize = 0x00100000
    wait_timeout = 0x00000102
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
    finally:
        kernel32.CloseHandle(handle)


def start_parent_watchdog(
    on_parent_gone: Callable[[], None],
    *,
    watch_stdin: bool = False,
    poll_interval_seconds: float = _DEFAULT_POLL_INTERVAL_SECONDS,
) -> Callable[[], None]:
    """Start watching the parent and optionally stdin.

    Returns a stop function. The callback fires at most once. A stdin EOF is
    treated as the shell closing the pipe, which is the normal desktop quit
    path even when the shell exits without sending a signal.
    """
    parent_pid = parent_pid_from_env()
    if parent_pid is None and not watch_stdin:
        return lambda: None

    stop_event = threading.Event()
    fired = threading.Event()

    def _fire() -> None:
        if fired.is_set():
            return
        fired.set()
        on_parent_gone()

    def _watch_parent() -> None:
        if parent_pid is None:
            return
        while not stop_event.wait(poll_interval_seconds):
            if not process_exists(parent_pid):
                _fire()
                return

    def _watch_stdin() -> None:
        try:
            while not stop_event.is_set():
                line = sys.stdin.readline()
                if not line:
                    break
        except Exception:
            pass
        if not stop_event.is_set():
            _fire()

    if parent_pid is not None:
        threading.Thread(
            target=_watch_parent,
            name="kontext-parent-watchdog",
            daemon=True,
        ).start()
    if watch_stdin:
        threading.Thread(
            target=_watch_stdin,
            name="kontext-stdin-watchdog",
            daemon=True,
        ).start()

    return stop_event.set
