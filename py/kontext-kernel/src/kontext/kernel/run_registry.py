"""Process-local registry of live kernels by job-run id.

A run in flight needs to be cancellable. The supervisor owns the kernels, so
this maps a ``run_id`` to its kernel for the duration of the execution and lets
a cancel request terminate that specific kernel — the kernel-process analogue of
the old subprocess registry.

Scope is deliberately process-local: it coordinates the supervisor with the
kernels it spawned, which is the blast radius a single local install needs.
"""

from __future__ import annotations

import contextlib
import threading

from .manager import ManagedKernel


class KernelRunRegistry:
    """Map of ``run_id`` -> live :class:`ManagedKernel`."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._kernels: dict[str, ManagedKernel] = {}

    def register(self, run_id: str, kernel: ManagedKernel) -> None:
        with self._lock:
            self._kernels[run_id] = kernel

    def unregister(self, run_id: str) -> None:
        with self._lock:
            self._kernels.pop(run_id, None)

    def is_registered(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._kernels

    def kill(self, run_id: str) -> bool:
        """Terminate the kernel for *run_id* if it is running. Returns True if killed."""
        with self._lock:
            kernel = self._kernels.pop(run_id, None)
        if kernel is None or not kernel.is_alive():
            return False
        # Synchronous terminate: a cancel may arrive from a thread without a
        # running loop, and we cannot await here.
        with contextlib.suppress(Exception):
            kernel.terminate_now()
        return True


_registry = KernelRunRegistry()


def get_running_kernel_registry() -> KernelRunRegistry:
    """Return the process-local running-kernel registry singleton."""
    return _registry


def terminate_running_kernel(run_id: str) -> bool:
    """Terminate the kernel process for *run_id*, if any."""
    return _registry.kill(run_id)
