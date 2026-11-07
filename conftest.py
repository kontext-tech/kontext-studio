"""Workspace-wide pytest safety net.

Some third-party libraries create process-global
``concurrent.futures.ThreadPoolExecutor`` instances that are never shut down:

* ``pyiceberg.utils.concurrent.ExecutorFactory`` — a lazy singleton backed by a
  bare ``ThreadPoolExecutor()`` (no thread-name prefix), which is why the leaked
  threads show up as ``ThreadPoolExecutor-0_*``.
* ``lancedb.background_loop._EMBEDDING_EXECUTOR`` — a module-level pool created
  eagerly at import with ``thread_name_prefix="lancedb-embedding"``.

Their worker threads are non-daemon, so CPython joins them at interpreter
shutdown (``concurrent.futures.thread._python_exit``). If a worker is blocked —
a stuck parquet write, a model download, a wedged native call — that join never
returns. pytest has already reported results by then, so the CI step looks
"still in progress" until the hosted runner gives up.

This module, at session finish:

1. Arms a faulthandler watchdog first, so a wedge still produces a thread dump
   and a hard exit.
2. Shuts those pools down, but bounded: ``shutdown(wait=True)`` runs in a
   daemon helper thread with a short grace period, because a wedged worker
   never raises — it simply never returns.
3. Logs any non-daemon threads that still refuse to stop.

Cleanup is scoped to the known singletons above; it deliberately does not scan
the GC heap for other pools, which could destroy pools still in use.

The per-test guard in ``pyproject.toml`` (``faulthandler_timeout`` +
``faulthandler_exit_on_timeout``) covers a hang mid-test or during async loop
teardown, before ``pytest_sessionfinish`` is reached.
"""

from __future__ import annotations

import contextlib
import faulthandler
import os
import sys
import threading
from typing import Any

import pytest

_DEFAULT_SHUTDOWN_WATCHDOG_SECONDS = 120
_SHUTDOWN_WATCHDOG_ENV = "KONTEXT_PYTEST_SHUTDOWN_WATCHDOG_SECONDS"

# How long (seconds) to wait for a pool's workers to finish. A healthy pool
# reaps in milliseconds; a wedged one is handled by the faulthandler watchdog.
_EXECUTOR_SHUTDOWN_GRACE_SECONDS = 5.0

# Environment variables that local-mode startup mutates process-wide via
# ``kontext.runtime.local.config``. Tests that boot the local app (for example
# the kontext-studio server) leak these into later tests, flipping the whole
# process into local mode and changing auth/routing behavior. Snapshot and
# restore them around every test so a test's environment cannot leak into the
# next one, regardless of collection order.
_LOCAL_MODE_ENV_VARS = (
    "KONTEXT_LOCAL_MODE",
    "KONTEXT_DIST_DIR",
    "KONTEXT_LOCAL_CONSOLE_AUTO_AUTH",
    "PROJECT_DB_URL",
    "KONTEXT_PROJECT_DB_URL",
    "JWT_SECRET_KEY",
    "KONTEXT_JWT_SECRET_KEY",
    "JWT_ISSUER",
    "KONTEXT_JWT_ISSUER",
    "JWT_AUDIENCE",
    "KONTEXT_JWT_AUDIENCE",
    "LOG_LEVEL",
    "KONTEXT_LOG_LEVEL",
    "LOG_FORMAT",
    "KONTEXT_LOG_FORMAT",
)


def _reset_model_resolution_hooks() -> None:
    """Clear process-wide model-resolution hooks after each test.

    ``configure_model_resolution()`` registers a process-global store; a test
    that boots the local app leaves it registered, which would make later tests
    (that expect no store) behave differently. Reset defensively so a missing
    optional import never fails teardown.
    """
    with contextlib.suppress(Exception):
        from kontext.llm import reset_model_resolution_hooks

        reset_model_resolution_hooks()


@pytest.fixture(autouse=True)
def _isolate_local_mode_env() -> Any:
    """Restore local-mode environment variables after each test.

    Local mode is configured by writing to ``os.environ``; without this, a test
    that boots the local app leaks that configuration into the next test and
    makes behavior depend on collection order: environment variables and the
    process-wide model-resolution registry.

    (Settings determinism — ignoring a developer's ``.env.local`` and resetting
    the ``KontextConfig`` singleton — is handled by the ``pytest11`` plugin in
    ``py/kontext-common/src/kontext/common/pytest_plugin.py``, which loads in
    every pytest invocation regardless of which ``[tool.pytest.ini_options]``
    section defines the rootdir.)
    """
    saved = {name: os.environ.get(name) for name in _LOCAL_MODE_ENV_VARS}
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        _reset_model_resolution_hooks()


def _shutdown_executor(executor: Any) -> None:
    """Shut down *executor*, waiting (bounded) for its workers to stop.

    ``shutdown(wait=True)`` must always run in a helper thread: on a wedged
    worker it never raises, it just never returns, so a direct call would hang
    and ``contextlib.suppress`` could not help. If it is still stuck after the
    grace period we return; the watchdog (armed first in ``pytest_sessionfinish``)
    dumps every thread and hard-exits.
    """
    finished = threading.Event()

    def _join() -> None:
        with contextlib.suppress(Exception):
            executor.shutdown(wait=True, cancel_futures=True)
        finished.set()

    with contextlib.suppress(Exception):
        helper = threading.Thread(target=_join, name="conftest-executor-join", daemon=True)
        helper.start()
        if not finished.wait(timeout=_EXECUTOR_SHUTDOWN_GRACE_SECONDS):
            # Still wedged: stop accepting new work; the watchdog will terminate.
            with contextlib.suppress(Exception):
                executor.shutdown(wait=False, cancel_futures=True)


def _shutdown_leaked_executors() -> None:
    """Best-effort shutdown of the known third-party global thread pools.

    Only touches libraries the session already imported. Scoped deliberately:
    scanning the GC heap for every ``ThreadPoolExecutor`` could destroy pools
    still in use (including our own worker pool).
    """
    iceberg = sys.modules.get("pyiceberg.utils.concurrent")
    factory = getattr(iceberg, "ExecutorFactory", None) if iceberg is not None else None
    if factory is not None:
        executor = getattr(factory, "_instance", None)
        if executor is not None:
            with contextlib.suppress(Exception):
                factory._instance = None
            _shutdown_executor(executor)

    background_loop = sys.modules.get("lancedb.background_loop")
    if background_loop is not None:
        executor = getattr(background_loop, "_EMBEDDING_EXECUTOR", None)
        if executor is not None:
            _shutdown_executor(executor)


def _log_live_non_daemon_threads() -> None:
    """Diagnostics: log any live non-daemon thread that refused to stop.

    Runs after the shutdown above, so anything listed here genuinely leaked.
    """
    non_daemon = [
        t for t in threading.enumerate() if not t.daemon and t is not threading.main_thread()
    ]
    if not non_daemon:
        return
    message = ["[conftest] live non-daemon threads after shutdown:"]
    for thread in non_daemon:
        message.append(f"  - {thread.name!r} (alive={thread.is_alive()})")
    with contextlib.suppress(Exception):
        print("\n".join(message), file=sys.stderr, flush=True)


def _arm_shutdown_watchdog() -> None:
    try:
        grace = float(
            os.environ.get(_SHUTDOWN_WATCHDOG_ENV, str(_DEFAULT_SHUTDOWN_WATCHDOG_SECONDS))
        )
    except ValueError:
        grace = float(_DEFAULT_SHUTDOWN_WATCHDOG_SECONDS)
    if grace <= 0:
        return
    # `exit=True` hard-exits after dumping thread stacks, so a blocked join
    # cannot silently hang the job. `pytest_unconfigure` disables faulthandler
    # but does not cancel this timer. Use fd 2 directly: pytest's capture may
    # already be torn down, so `sys.stderr` is unsafe here.
    with contextlib.suppress(Exception):
        faulthandler.dump_traceback_later(grace, exit=True, file=2)


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    # Arm the watchdog first so a wedge in the steps below still dumps threads
    # and hard-exits instead of hanging silently.
    _arm_shutdown_watchdog()
    _shutdown_leaked_executors()
    _log_live_non_daemon_threads()
