"""Tests for kernel child resource limits.

The important regression here is RLIMIT_NPROC: it is enforced per real UID, so
an absolute cap can sit below the number of tasks a shared user (for example a
CI account) already owns, causing the kernel to die during startup with
``can't start new thread``. The cap must be relative to current usage.
"""

from __future__ import annotations

from unittest import mock

from kontext.kernel import limits as limits_module
from kontext.kernel.limits import (
    _NPROC_HEADROOM,
    ProcessLimits,
    _count_user_tasks,
    _posix_preexec,
)


def _build_preexec_recording_nproc():
    """Build the pre-exec hook with a fake ``resource`` and record NPROC sets."""
    applied: list[int] = []
    fake_resource = mock.Mock()
    fake_resource.RLIMIT_NPROC = object()

    def record(which, value):
        if which is fake_resource.RLIMIT_NPROC:
            applied.append(value[0])

    fake_resource.setrlimit.side_effect = record
    with mock.patch.dict("sys.modules", {"resource": fake_resource}):
        pre_exec = _posix_preexec(ProcessLimits())
    return pre_exec, applied, fake_resource


def test_count_user_tasks_returns_none_without_proc() -> None:
    """Platforms without /proc (macOS) must skip the NPROC cap."""
    with mock.patch.object(limits_module, "Path") as path_cls:
        path_cls.return_value.is_dir.return_value = False
        assert _count_user_tasks() is None


def test_count_user_tasks_counts_current_uid_pids() -> None:
    if not limits_module.Path("/proc").is_dir():  # pragma: no cover - non-Linux
        return

    count = _count_user_tasks()
    assert count is not None
    assert count >= 1


def test_posix_preexec_skips_nproc_when_count_unavailable() -> None:
    """When the task count is unknown, the NPROC limit must not be applied."""
    with mock.patch.object(limits_module, "_count_user_tasks", return_value=None):
        pre_exec, applied, _fake = _build_preexec_recording_nproc()

    with mock.patch.object(limits_module.os, "setsid"):
        pre_exec()

    assert applied == []


def test_posix_preexec_sets_nproc_above_current_usage() -> None:
    """The cap must leave headroom above the caller's current task count."""
    with mock.patch.object(limits_module, "_count_user_tasks", return_value=1000):
        pre_exec, applied, _fake = _build_preexec_recording_nproc()

    with mock.patch.object(limits_module.os, "setsid"):
        pre_exec()

    assert applied == [1000 + _NPROC_HEADROOM]
