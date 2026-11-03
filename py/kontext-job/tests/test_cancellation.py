import asyncio

import pytest

from kontext.jobs.cancellation import (
    JobCancellationRegistry,
    JobCancelledError,
    get_cancellation_registry,
)


def test_registry_signals_registered_run() -> None:
    registry = JobCancellationRegistry()
    registry.register("run-1")

    assert registry.is_cancelled("run-1") is False
    assert registry.request_cancel("run-1") is True
    assert registry.is_cancelled("run-1") is True


def test_registry_request_cancel_unknown_run_is_noop() -> None:
    registry = JobCancellationRegistry()
    assert registry.request_cancel("missing") is False
    assert registry.is_cancelled("missing") is False


def test_registry_unregister_clears_signal() -> None:
    registry = JobCancellationRegistry()
    registry.register("run-1")
    registry.request_cancel("run-1")
    registry.unregister("run-1")

    assert registry.is_cancelled("run-1") is False
    assert registry.request_cancel("run-1") is False


async def _wait(registry: JobCancellationRegistry, run_id: str) -> None:
    await registry.wait_for_cancellation(run_id)


@pytest.mark.asyncio
async def test_wait_for_cancellation_returns_when_signalled() -> None:
    registry = JobCancellationRegistry()
    registry.register("run-1")

    waiter = asyncio.ensure_future(_wait(registry, "run-1"))
    await asyncio.sleep(0)
    assert waiter.done() is False

    registry.request_cancel("run-1")
    await asyncio.wait_for(waiter, timeout=1)


@pytest.mark.asyncio
async def test_wait_for_cancellation_returns_immediately_when_unregistered() -> None:
    registry = JobCancellationRegistry()
    await asyncio.wait_for(_wait(registry, "missing"), timeout=1)


def test_module_singleton_is_shared() -> None:
    assert get_cancellation_registry() is get_cancellation_registry()


def test_job_cancelled_error_carries_run_id() -> None:
    error = JobCancelledError("run-1")
    assert error.run_id == "run-1"
    assert "run-1" in str(error)


def test_job_context_raise_if_cancelled_matches_registry_state() -> None:
    from kontext.jobs.job_context import JobContext

    context = JobContext(
        job_run_id="run-ctx",
        project_id=None,
        job_name="test",
        job_execution_service=object(),  # type: ignore[arg-type]
        parameters={},
        runtime_provider=object(),  # type: ignore[arg-type]
    )

    # Not cancelled: no raise.
    context.raise_if_cancelled()
    assert context.is_cancelled() is False

    get_cancellation_registry().register("run-ctx")
    get_cancellation_registry().request_cancel("run-ctx")
    try:
        assert context.is_cancelled() is True
        with pytest.raises(JobCancelledError):
            context.raise_if_cancelled()
    finally:
        get_cancellation_registry().unregister("run-ctx")
