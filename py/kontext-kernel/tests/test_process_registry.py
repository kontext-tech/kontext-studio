"""Tests for the kernel run registry (run_id -> live kernel)."""

from __future__ import annotations

from unittest.mock import MagicMock

from kontext.kernel.run_registry import (
    KernelRunRegistry,
    get_running_kernel_registry,
    terminate_running_kernel,
)


def test_registry_register_and_kill() -> None:
    registry = KernelRunRegistry()
    kernel = MagicMock()
    kernel.is_alive.return_value = True

    registry.register("run-1", kernel)
    assert registry.is_registered("run-1") is True
    assert registry.kill("run-1") is True
    kernel.terminate_now.assert_called_once()

    # Popped on kill: not registered afterwards.
    assert registry.is_registered("run-1") is False


def test_registry_kill_unknown_run_returns_false() -> None:
    registry = KernelRunRegistry()
    assert registry.kill("missing") is False


def test_registry_kill_skips_dead_kernel() -> None:
    registry = KernelRunRegistry()
    kernel = MagicMock()
    kernel.is_alive.return_value = False

    registry.register("run-1", kernel)
    assert registry.kill("run-1") is False
    kernel.terminate_now.assert_not_called()


def test_registry_unregister() -> None:
    registry = KernelRunRegistry()
    kernel = MagicMock()
    kernel.is_alive.return_value = True

    registry.register("run-1", kernel)
    registry.unregister("run-1")
    assert registry.is_registered("run-1") is False
    assert registry.kill("run-1") is False


def test_module_singleton_is_shared() -> None:
    assert get_running_kernel_registry() is get_running_kernel_registry()


def test_terminate_running_kernel_unknown_run_is_noop() -> None:
    assert terminate_running_kernel("does-not-exist") is False
