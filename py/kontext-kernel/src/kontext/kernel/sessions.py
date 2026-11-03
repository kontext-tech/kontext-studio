"""Persistent session-kernel manager.

A *session kernel* is a long-lived kernel process bound to a session id (a
notebook, chat session, or query session). Consecutive executions reuse the same
process, so variables defined in one cell are visible in the next — the
persistent-namespace behavior users expect from a notebook.

Contrast with a one-shot run kernel (:mod:`kontext.kernel.runner`),
which starts a fresh process per execution. Both use the same wire protocol and
the same :class:`~kontext.kernel.manager.ManagedKernel` lifecycle; only
the lifetime differs.

Kernels are evicted after an idle timeout so abandoned sessions do not leak
processes. Eviction is opportunistic on access plus a background reaper, so no
timer thread is required for correctness.

Session state is deliberately in-memory only: there is no snapshot/restore. An
evicted or crashed session simply starts a fresh namespace on next use.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import tempfile
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .limits import ProcessLimits
from .manager import KernelManager, ManagedKernel
from .protocol import EXECUTE_REPLY, SHELL

logger = logging.getLogger(__name__)

DEFAULT_IDLE_TIMEOUT_SECONDS = 900.0  # 15 minutes
DEFAULT_MAX_SESSIONS = 32

# How long a new execution waits under the lock for a busy kernel to settle
# (an interrupt usually lands within a second) before declaring it wedged.
_BUSY_SETTLE_SECONDS = 8.0


@dataclass
class _SessionEntry:
    kernel: ManagedKernel
    workspace: Path
    last_used: float = field(default_factory=time.monotonic)
    in_use: bool = False
    # Consecutive runner timeouts on this session. Two in a row means the
    # running cell ignored SIGINT; the kernel is then recreated (see
    # ``escalate_timeout``) instead of leaving the session wedged.
    timeout_streak: int = 0
    # Serializes executions on this kernel: a kernel has one namespace, so two
    # concurrent runs on the same session must not interleave.
    exec_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionKernelManager:
    """Own a pool of session kernels keyed by session id.

    A session kernel outlives any single execution, so the platform bridge is
    supplied per call to :meth:`execute` rather than bound at kernel startup.
    """

    def __init__(
        self,
        *,
        idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS,
        max_sessions: int = DEFAULT_MAX_SESSIONS,
        kernel_manager: KernelManager | None = None,
        workspace_root: Path | None = None,
        python_executable: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._idle_timeout = idle_timeout_seconds
        self._max_sessions = max_sessions
        self._kernel_manager = kernel_manager or KernelManager(python_executable=python_executable)
        self._workspace_root = workspace_root or Path(tempfile.gettempdir())
        self._env = env
        self._sessions: dict[str, _SessionEntry] = {}
        self._lock = asyncio.Lock()
        self._reaper_task: asyncio.Task[None] | None = None
        self._shutdown_tasks: set[asyncio.Task[None]] = set()

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Start the background idle reaper."""
        if self._reaper_task is None:
            self._reaper_task = asyncio.create_task(self._reap_loop())

    async def shutdown(self) -> None:
        """Stop the reaper and shut down every kernel."""
        if self._reaper_task is not None:
            self._reaper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reaper_task
            self._reaper_task = None

        async with self._lock:
            entries = list(self._sessions.values())
            self._sessions.clear()
        for entry in entries:
            await _teardown_entry(entry)

    # -- execution -----------------------------------------------------------

    async def execute(
        self,
        session_id: str,
        code: str,
        *,
        host_call_handler: Any = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute *code* in *session_id*'s kernel, reusing it if warm.

        ``host_call_handler`` is the per-execution platform bridge (SQL, files,
        data). It is set on the kernel for the duration of this execution and
        cleared afterwards, because a session kernel outlives any one job
        context.
        """
        entry = await self._ensure_kernel(session_id)
        # Serialize executions on one kernel: they share a single namespace.
        async with entry.exec_lock:
            # A busy kernel under the lock means the previous execution lost
            # its consumer (timed out or was cancelled at the runner) but is
            # still running. Give it a short grace window to settle — the
            # runner's interrupt typically lands within a second; a kernel
            # that stays busy is wedged and must fail fast instead of
            # silently queueing for the full collect timeout. Concurrent
            # *submissions* queue above on the lock as before.
            if entry.kernel.is_busy():
                deadline = time.monotonic() + _BUSY_SETTLE_SECONDS
                while entry.kernel.is_busy() and time.monotonic() < deadline:
                    await asyncio.sleep(0.1)
            if entry.kernel.is_busy():
                logger.warning("Session kernel for %s is busy; rejecting new execution", session_id)
                yield {
                    "msg_type": EXECUTE_REPLY,
                    "channel": SHELL,
                    "content": {
                        "status": "error",
                        "error": (
                            "Session kernel is busy: the previous Python execution is still "
                            "running and did not respond to interrupt. A retry that times out "
                            "again will recreate the session kernel automatically."
                        ),
                    },
                }
                return
            entry.kernel.set_host_call_handler(host_call_handler)
            try:
                completed = False
                try:
                    async for message in entry.kernel.execute(code):
                        yield message
                    completed = True
                finally:
                    if completed:
                        # A clean run clears the timeout escalation streak.
                        entry.timeout_streak = 0
                    entry.last_used = time.monotonic()
                    entry.in_use = False
            finally:
                entry.kernel.set_host_call_handler(None)

    async def escalate_timeout(self, session_id: str) -> bool:
        """Record a runner timeout and escalate on repeat offense.

        The first timeout for a session gets a best-effort SIGINT interrupt.
        A *second* consecutive timeout means the running cell ignored SIGINT:
        the kernel is shut down through the control channel — which works even
        while the main thread is wedged — and the session restarts with a fresh
        namespace on the next use.
        """
        async with self._lock:
            entry = self._sessions.get(session_id)
        if entry is None:
            return False
        entry.timeout_streak += 1
        if entry.timeout_streak < 2:
            await entry.kernel.interrupt()
            return False
        logger.warning(
            "Session kernel for %s ignored a second consecutive interrupt; recreating it",
            session_id,
        )
        await self.close_session(session_id)
        return True

    async def interrupt(self, session_id: str) -> bool:
        """Interrupt the running code in *session_id*, if the kernel is warm."""
        async with self._lock:
            entry = self._sessions.get(session_id)
        if entry is None:
            return False
        await entry.kernel.interrupt()
        return True

    async def close_session(self, session_id: str) -> bool:
        """Shut down and forget the kernel for *session_id*, removing its workspace."""
        async with self._lock:
            entry = self._sessions.pop(session_id, None)
        if entry is None:
            return False
        await _teardown_entry(entry)
        return True

    async def reap_missing_sessions(self, is_alive: Callable[[str], bool]) -> list[str]:
        """Close kernels whose session no longer exists according to *is_alive*.

        Called periodically by the supervisor so a deleted chat/notebook does
        not leave a kernel (and its workspace) running until the idle timeout.
        ``is_alive`` receives the session id and returns whether it still
        exists; this keeps the manager decoupled from any specific session
        store.
        """
        async with self._lock:
            candidate_ids = [
                session_id for session_id, entry in self._sessions.items() if not entry.in_use
            ]

        reaped: list[str] = []
        for session_id in candidate_ids:
            try:
                alive = await asyncio.to_thread(is_alive, session_id)
            except Exception:
                logger.exception("Liveness check failed for session %s", session_id)
                continue
            if not alive and await self.close_session(session_id):
                reaped.append(session_id)
        return reaped

    def active_session_ids(self) -> list[str]:
        """Return the ids of warm session kernels (for observability/tests)."""
        return [
            session_id for session_id, entry in self._sessions.items() if entry.kernel.is_alive()
        ]

    # -- internals -----------------------------------------------------------

    async def _ensure_kernel(self, session_id: str) -> _SessionEntry:
        async with self._lock:
            entry = self._sessions.get(session_id)
            if entry is not None and not entry.kernel.is_alive():
                # Process died (crash/OOM): log the diagnostics, drop it and
                # start fresh. Without this a crash-looped session would
                # restart silently and stay undiagnosable.
                entry.kernel.log_exit_diagnostics(context=f"for session {session_id}")
                self._sessions.pop(session_id, None)
                entry = None

            if entry is None:
                await self._evict_if_needed()
                entry = await self._start_kernel(session_id)
                self._sessions[session_id] = entry

            entry.in_use = True
            entry.last_used = time.monotonic()
            return entry

    async def _start_kernel(self, session_id: str) -> _SessionEntry:
        workspace = self._workspace_root / f"kontext-session-{_safe(session_id)}"
        # cpu_seconds=0 because RLIMIT_CPU is cumulative process CPU and one
        # process here serves every cell of the session (see ProcessLimits);
        # per-cell wall timeouts plus interrupt escalation bound runaway cells.
        kernel = await self._kernel_manager.start(
            workspace=workspace,
            env=self._env,
            connect_timeout=30,
            limits=ProcessLimits(cpu_seconds=0),
        )
        logger.info("Started session kernel for %s", session_id)
        return _SessionEntry(kernel=kernel, workspace=workspace)

    async def _evict_if_needed(self) -> None:
        """Evict idle kernels; if still at capacity, evict the least-recently-used."""
        self._evict_idle_locked()
        if len(self._sessions) < self._max_sessions:
            return

        # At capacity: drop the least-recently-used idle kernel.
        candidates = [sid for sid, entry in self._sessions.items() if not entry.in_use]
        if not candidates:
            raise RuntimeError(
                f"Session kernel limit ({self._max_sessions}) reached and all kernels are busy"
            )
        victim = min(candidates, key=lambda sid: self._sessions[sid].last_used)
        entry = self._sessions.pop(victim)
        logger.info("Evicting least-recently-used session kernel %s", victim)
        await _teardown_entry(entry)

    def _evict_idle_locked(self) -> list[str]:
        """Remove and return idle session ids (caller must hold the lock)."""
        now = time.monotonic()
        victims = [
            session_id
            for session_id, entry in self._sessions.items()
            if not entry.in_use and (now - entry.last_used) >= self._idle_timeout
        ]
        for session_id in victims:
            entry = self._sessions.pop(session_id)
            logger.info("Reaping idle session kernel %s", session_id)
            # Shutdown is async; schedule it without blocking the caller's lock.
            task = asyncio.ensure_future(_teardown_entry(entry))
            self._shutdown_tasks.add(task)
            self._shutdown_tasks = {t for t in self._shutdown_tasks if not t.done()}
        return victims

    async def _reap_loop(self) -> None:
        # Sweep at a fraction of the timeout so idle kernels are reaped promptly.
        interval = max(1.0, self._idle_timeout / 4)
        while True:
            await asyncio.sleep(interval)
            async with self._lock:
                self._evict_idle_locked()


async def _teardown_entry(entry: _SessionEntry) -> None:
    """Shut down a kernel and remove its workspace directory."""
    with contextlib.suppress(Exception):
        await entry.kernel.shutdown(timeout=5.0)
    await asyncio.to_thread(shutil.rmtree, entry.workspace, True)


def _safe(session_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)[:64]
