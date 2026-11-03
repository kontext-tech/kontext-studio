"""Process-level access to the active session-kernel manager.

Session kernels are owned by the supervisor process (the local worker). Job
definitions run inside that process and need the manager, but the manager is
created once at worker startup — not per job. This module provides the seam:
the worker calls :func:`install_session_kernel_manager` at startup and job code
calls :func:`get_session_kernel_manager`.

If no manager is installed (for example, a one-shot CLI run or a test that does
not exercise session kernels), :func:`get_session_kernel_manager` returns
``None`` so callers can fall back.
"""

from __future__ import annotations

from .sessions import SessionKernelManager

_manager: SessionKernelManager | None = None


def install_session_kernel_manager(manager: SessionKernelManager | None) -> None:
    """Install (or clear) the process-wide session-kernel manager."""
    global _manager
    _manager = manager


def get_session_kernel_manager() -> SessionKernelManager | None:
    """Return the installed session-kernel manager, if any."""
    return _manager
