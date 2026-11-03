"""Session-kernel execution for notebook/chat Python jobs.

Turns a :class:`~kontext.kernel.sessions.SessionKernelManager` plus a
platform bridge into the same :class:`~kontext.kernel.contracts.PythonRunnerResult`
shape callers already consume, keyed by a session id so that consecutive cells
share a namespace.

The supervisor (worker) owns the manager; the API never holds a kernel.
"""

from __future__ import annotations

import asyncio
import contextlib

from kontext.kernel.contracts import (
    PythonRunnerHostBridge,
    PythonRunnerResult,
)

from .execution import (
    ExecutionCollector,
    execute_and_collect,
    make_host_call_handler,
    timeout_result,
    validation_failure,
)
from .registry import get_session_kernel_manager
from .sessions import SessionKernelManager

_DEFAULT_TIMEOUT_SECONDS = 300


def get_session_runner() -> SessionRunner | None:
    """Return a SessionRunner backed by this process's manager, if installed.

    ``None`` means no supervisor owns session kernels here (for example a
    one-shot CLI run), so callers should fall back to the single-use runner
    backend.
    """
    manager = get_session_kernel_manager()
    return SessionRunner(manager) if manager is not None else None


class SessionRunner:
    """Execute code in a named session kernel and collect a runner result."""

    def __init__(self, manager: SessionKernelManager) -> None:
        self._manager = manager

    def _session_is_shared(self, session_id: str) -> bool:
        """Whether *session_id* already has a live kernel (may reuse aliases)."""
        return session_id in self._manager.active_session_ids()

    async def run(
        self,
        *,
        session_id: str,
        code: str,
        host_bridge: PythonRunnerHostBridge | None = None,
        data_payloads: dict[str, str] | None = None,
        timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
        stdout_limit_bytes: int | None = None,
        stderr_limit_bytes: int | None = None,
        ephemeral: bool = False,
    ) -> PythonRunnerResult:
        # A session kernel that already exists may have aliases (and any other
        # bindings) from earlier cells, so the "alias used but not defined"
        # guidance must not misfire on follow-up cells. A genuinely missing
        # import still fails at execution time with a normal NameError.
        invalid = validation_failure(code, shared_namespace=self._session_is_shared(session_id))
        if invalid is not None:
            return invalid

        handler = make_host_call_handler(host_bridge, data_payloads)
        stream = self._manager.execute(session_id, code, host_call_handler=handler)
        try:
            return await execute_and_collect(
                stream,
                ExecutionCollector(
                    stdout_limit_bytes=stdout_limit_bytes,
                    stderr_limit_bytes=stderr_limit_bytes,
                ),
                timeout_seconds=timeout_seconds,
            )
        except TimeoutError:
            # Best-effort SIGINT for the first offense; a second consecutive
            # timeout recreates the kernel (it ignored SIGINT).
            with contextlib.suppress(Exception):
                await self._manager.escalate_timeout(session_id)
            return timeout_result(timeout_seconds)
        except asyncio.CancelledError:
            # The run was cancelled: interrupt the kernel so the cell stops, then
            # let the cancellation propagate to the executor.
            with contextlib.suppress(Exception):
                await self._manager.interrupt(session_id)
            raise
        finally:
            # Run-scoped (non-session) executions must not leave a kernel or
            # workspace behind, since nothing will ever reuse or reconcile them.
            if ephemeral:
                with contextlib.suppress(Exception):
                    await self._manager.close_session(session_id)
