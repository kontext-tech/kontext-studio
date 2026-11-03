"""One-shot kernel-backed Python runner.

Implements the ``PythonRunnerBackend`` surface: executes code in a fresh kernel
process over the socket protocol. A one-shot kernel runs a single request and is
torn down afterwards; see :mod:`kontext.kernel.session_runner` for the
long-lived session variant.
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import sys
import tempfile
from pathlib import Path

from kontext.kernel.contracts import (
    PythonRunnerRequest,
    PythonRunnerResult,
)

from .execution import (
    ExecutionCollector,
    execute_and_collect,
    make_host_call_handler,
    timeout_result,
    validation_failure,
)
from .limits import ProcessLimits
from .manager import KernelManager

_DEFAULT_EXECUTE_TIMEOUT_SECONDS = 300


class KernelPythonRunnerBackend:
    """Run a single block of Python code in a fresh, one-shot kernel process."""

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._python_executable = python_executable or sys.executable
        self._env = env

    async def run(self, request: PythonRunnerRequest) -> PythonRunnerResult:
        invalid = validation_failure(request.code)
        if invalid is not None:
            return invalid

        timeout_seconds = request.timeout_seconds or _DEFAULT_EXECUTE_TIMEOUT_SECONDS
        workspace = Path(tempfile.mkdtemp(prefix="kontext-kernel-"))
        try:
            manager = KernelManager(python_executable=self._python_executable)
            kernel = await manager.start(
                workspace=workspace,
                env=self._env,
                run_id=request.run_id,
                limits=ProcessLimits(
                    memory_limit_mb=request.memory_limit_mb,
                    cpu_seconds=timeout_seconds,
                    file_size_limit_bytes=request.workspace_limit_bytes,
                ),
            )
            kernel.set_host_call_handler(
                make_host_call_handler(request.host_bridge, request.data_payloads)
            )
        except BaseException:
            # ``start`` may fail before a ManagedKernel exists to clean up.
            await asyncio.to_thread(shutil.rmtree, workspace, ignore_errors=True)
            raise

        try:
            return await execute_and_collect(
                kernel.execute(request.code),
                ExecutionCollector(
                    stdout_limit_bytes=request.stdout_limit_bytes,
                    stderr_limit_bytes=request.stderr_limit_bytes,
                ),
                timeout_seconds=timeout_seconds,
            )
        except TimeoutError:
            await kernel.shutdown(timeout=2.0)
            return timeout_result(timeout_seconds)
        except Exception:
            if not kernel.is_alive():
                kernel.log_exit_diagnostics(context="one-shot run")
            raise
        finally:
            if request.run_id:
                from .run_registry import get_running_kernel_registry

                get_running_kernel_registry().unregister(request.run_id)
            with contextlib.suppress(Exception):
                await kernel.shutdown(timeout=5.0)
            # A one-shot kernel has no session manager to reap it: drop the
            # workspace (connection file, child temp state) right away.
            await asyncio.to_thread(shutil.rmtree, workspace, ignore_errors=True)
