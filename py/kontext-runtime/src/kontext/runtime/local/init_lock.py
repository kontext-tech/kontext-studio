"""Cross-process lock for local database initialization.

The API and the worker are separate processes that both start against the same
SQLite file. Local schema/seed setup (``run_local_migrations`` +
``seed_default_*``) is not safe to run concurrently: two processes can race on
``CREATE TABLE``/``ALTER TABLE`` or both INSERT the default profile and hit the
``local_profile.email`` unique constraint.

This module serializes that setup with an advisory file lock so exactly one
process initializes at a time. It is a *startup* lock only — held for the few
seconds of migration/seed, never for the process lifetime.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_SECONDS = 60.0
_POLL_INTERVAL_SECONDS = 0.05


@contextmanager
def local_init_lock(
    data_dir: Path,
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> Iterator[None]:
    """Acquire an exclusive cross-process lock around local DB initialization.

    Blocks up to *timeout_seconds* for another process to finish initializing.
    If the lock cannot be acquired in time, logs a warning and proceeds anyway
    rather than hanging startup forever — seeding is independently made
    idempotent, so proceeding is the lesser evil.
    """
    lock_path = data_dir / "local-init.lock"
    data_dir.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+")  # noqa: SIM115 - closed in finally
    try:
        acquired = _acquire(handle, timeout_seconds=timeout_seconds)
        if not acquired:
            logger.warning(
                "Timed out waiting for the local init lock at %s; "
                "continuing without it (seeding is idempotent).",
                lock_path,
            )
        try:
            yield
        finally:
            if acquired:
                _release(handle)
    finally:
        with contextlib.suppress(OSError):
            handle.close()


def _acquire(handle, *, timeout_seconds: float) -> bool:
    if os.name == "nt":  # pragma: no cover - Windows-only path
        return _acquire_windows(handle, timeout_seconds=timeout_seconds)
    return _acquire_posix(handle, timeout_seconds=timeout_seconds)


def _acquire_posix(handle, *, timeout_seconds: float) -> bool:
    import fcntl

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(_POLL_INTERVAL_SECONDS)


def _acquire_windows(handle, *, timeout_seconds: float) -> bool:  # pragma: no cover
    import msvcrt

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(_POLL_INTERVAL_SECONDS)


def _release(handle) -> None:
    if os.name == "nt":  # pragma: no cover - Windows-only path
        import msvcrt

        with contextlib.suppress(OSError):
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
        return

    import fcntl

    with contextlib.suppress(OSError):
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
