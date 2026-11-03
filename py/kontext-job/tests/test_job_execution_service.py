import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from kontext.jobs.cancellation import get_cancellation_registry
from kontext.jobs.job_execution_service import JobExecutionService
from kontext.schema import JobRunStatus


@pytest.mark.asyncio
async def test_execute_job_run_skips_when_cancelled_after_worker_assignment():
    service_backend = MagicMock()
    service_backend.get_job_run = AsyncMock(
        side_effect=[
            MagicMock(
                status=JobRunStatus.QUEUED,
                job_id="job-123",
                parameters="{}",
            ),
            MagicMock(status=JobRunStatus.CANCELED),
        ]
    )
    service_backend.update_worker = AsyncMock()
    service_backend.update_status = AsyncMock()
    service_backend.add_log = AsyncMock()

    service = JobExecutionService(
        project_id="project-123",
        runtime_provider=MagicMock(),
        service=service_backend,
    )

    result = await service.execute_job_run("run-123", "worker-1")

    assert result is None
    service_backend.update_worker.assert_awaited_once()
    service_backend.update_status.assert_not_awaited()


def _make_service_backend(*, job_type: str = "python.jobs.NoopJob") -> MagicMock:
    """Build a fully-mocked IJobRunServiceProtocol backend for a happy path."""
    backend = MagicMock()
    job_run = MagicMock(
        status=JobRunStatus.QUEUED,
        job_id="job-123",
        parameters="{}",
    )
    job = MagicMock(type=job_type, name="placeholder", timeout=1)
    # ``name`` is special-cased by MagicMock and must be reassigned explicitly.
    job.name = "noop-job"
    job.type = job_type
    backend.get_job_run = AsyncMock(return_value=job_run)
    backend.get_job = AsyncMock(return_value=job)
    backend.update_worker = AsyncMock()
    backend.update_status = AsyncMock()
    backend.add_log = AsyncMock()
    # Terminal writes go through the claim-ownership fence; a healthy claim
    # renews (and truthiness must not be incidental).
    backend.renew_lease = AsyncMock(return_value=True)
    return backend


@pytest.mark.asyncio
async def test_no_emitter_means_no_lineage_side_effects(monkeypatch):
    """Without an emitter, execute_job_run must behave exactly as before."""

    class _NoopJob:
        async def execute(self, context, parameters):
            from kontext.jobs.job_result import JobResult

            return JobResult.success_result("ok")

    fake_registry = MagicMock()
    fake_registry.create_job_instance = MagicMock(return_value=_NoopJob())
    monkeypatch.setattr(
        "kontext.jobs.job_registry.get_job_registry",
        lambda: fake_registry,
    )

    service = JobExecutionService(
        project_id="project-123",
        runtime_provider=MagicMock(),
        service=_make_service_backend(),
    )
    # Must not raise and must complete the run.
    from uuid import uuid4

    result = await service.execute_job_run(str(uuid4()), "worker-1")
    assert result is not None


@pytest.mark.asyncio
async def test_execute_job_run_aborts_a_running_job_on_cancel(monkeypatch):
    """A running job is cancelled and the run is marked Canceled."""
    job_started = asyncio.Event()

    class _HangingJob:
        async def execute(self, context, parameters):
            job_started.set()
            # Runs forever unless cancelled externally.
            await asyncio.sleep(3600)

    fake_registry = MagicMock()
    fake_registry.create_job_instance = MagicMock(return_value=_HangingJob())
    monkeypatch.setattr(
        "kontext.jobs.job_registry.get_job_registry",
        lambda: fake_registry,
    )

    backend = _make_service_backend()
    service = JobExecutionService(
        project_id="project-123",
        runtime_provider=MagicMock(),
        service=backend,
    )

    run_id = str(uuid4())
    execution = asyncio.ensure_future(service.execute_job_run(run_id, "worker-1"))
    # Wait until the job is actually executing before cancelling.
    await asyncio.wait_for(job_started.wait(), timeout=1)

    registry = get_cancellation_registry()
    registry.request_cancel(run_id)

    result = await asyncio.wait_for(execution, timeout=5)

    assert result is None
    assert registry.is_cancelled(run_id) is False  # unregistered in finally
    statuses = [call.args[2] for call in backend.update_status.await_args_list]
    assert JobRunStatus.CANCELED in statuses


@pytest.mark.asyncio
async def test_cooperative_cancellation_marks_run_canceled_not_failed(monkeypatch):
    """A job that signals cancellation is recorded as Canceled, not Failed.

    Exercises the real ``BasePythonJob.execute`` wrapper (not a stub), proving
    ``JobCancelledError`` propagates instead of being swallowed into a failure,
    and that the executor records the run as CANCELED.
    """
    from kontext.jobs.base import BaseJobParams, BasePythonJob
    from kontext.jobs.cancellation import JobCancelledError

    class _Params(BaseJobParams):
        pass

    class _CooperativeJob(BasePythonJob[_Params]):
        def get_params_model(self):
            return _Params

        async def execute_job(self, context, parameters):
            raise JobCancelledError(context.job_run_id)

    fake_registry = MagicMock()
    fake_registry.create_job_instance = MagicMock(return_value=_CooperativeJob())
    monkeypatch.setattr(
        "kontext.jobs.job_registry.get_job_registry",
        lambda: fake_registry,
    )

    backend = _make_service_backend()
    service = JobExecutionService(
        project_id="project-123",
        runtime_provider=MagicMock(),
        service=backend,
    )

    result = await asyncio.wait_for(service.execute_job_run(str(uuid4()), "worker-1"), timeout=5)

    assert result is None
    statuses = [call.args[2] for call in backend.update_status.await_args_list]
    assert JobRunStatus.CANCELED in statuses
    assert JobRunStatus.FAILED not in statuses


@pytest.mark.asyncio
async def test_execute_job_run_observes_cancel_from_db_status(monkeypatch):
    """A cancel persisted by another process stops the local execution.

    The API cancels by writing ``Canceled`` to the run row; this process only
    sees it via the status watcher, never via the in-process registry. This is
    the cross-process cancellation path.
    """
    job_started = asyncio.Event()

    class _HangingJob:
        async def execute(self, context, parameters):
            job_started.set()
            await asyncio.sleep(3600)

    fake_registry = MagicMock()
    fake_registry.create_job_instance = MagicMock(return_value=_HangingJob())
    monkeypatch.setattr(
        "kontext.jobs.job_registry.get_job_registry",
        lambda: fake_registry,
    )

    backend = _make_service_backend()
    # After the run is marked RUNNING, later reads report CANCELED as if another
    # process had cancelled it.
    queued = MagicMock(status=JobRunStatus.QUEUED, job_id="job-123", parameters="{}")
    canceled = MagicMock(status=JobRunStatus.CANCELED, job_id="job-123", parameters="{}")

    def _get_job_run(_run_id, _project_id):
        return canceled if job_started.is_set() else queued

    backend.get_job_run = AsyncMock(side_effect=_get_job_run)

    service = JobExecutionService(
        project_id="project-123",
        runtime_provider=MagicMock(),
        service=backend,
    )
    # Poll fast so the test does not wait a full second.
    monkeypatch.setattr(
        "kontext.jobs.job_execution_service._CANCEL_POLL_INTERVAL_SECONDS",
        0.05,
    )

    run_id = str(uuid4())
    execution = asyncio.ensure_future(service.execute_job_run(run_id, "worker-1"))
    await asyncio.wait_for(job_started.wait(), timeout=1)

    result = await asyncio.wait_for(execution, timeout=10)

    assert result is None
    statuses = [call.args[2] for call in backend.update_status.await_args_list]
    assert JobRunStatus.CANCELED in statuses


@pytest.mark.asyncio
async def test_execute_job_run_does_not_overwrite_after_losing_claim(monkeypatch):
    """A superseded execution (lease lost) must not write its outcome.

    When the claim is no longer owned (the reaper reclaimed a lapsed lease,
    another worker re-claimed the run, or the API canceled it), the terminal
    write is fenced off. At-least-once semantics make the skip safe: the
    requeued run will be executed again and record its own outcome.
    """

    class _NoopJob:
        async def execute(self, context, parameters):
            from kontext.jobs.job_result import JobResult

            return JobResult.success_result("ok")

    fake_registry = MagicMock()
    fake_registry.create_job_instance = MagicMock(return_value=_NoopJob())
    monkeypatch.setattr(
        "kontext.jobs.job_registry.get_job_registry",
        lambda: fake_registry,
    )

    backend = _make_service_backend()
    backend.renew_lease = AsyncMock(return_value=False)  # claim lost

    service = JobExecutionService(
        project_id="project-123",
        runtime_provider=MagicMock(),
        service=backend,
    )

    result = await service.execute_job_run(str(uuid4()), "worker-1")

    assert result is None
    statuses = [call.args[2] for call in backend.update_status.await_args_list]
    assert JobRunStatus.SUCCEEDED not in statuses
    assert JobRunStatus.FAILED not in statuses


@pytest.mark.asyncio
async def test_execute_job_run_cancels_job_when_executor_is_cancelled(monkeypatch):
    """Cancelling the executor (worker shutdown) must cancel the running job.

    Regression test: the job task previously leaked on outer cancellation
    because CancelledError skips the job-specific cleanup branches.
    """
    job_started = asyncio.Event()
    job_finished = asyncio.Event()

    class _HangingJob:
        async def execute(self, context, parameters):
            job_started.set()
            try:
                await asyncio.sleep(3600)
            finally:
                job_finished.set()

    fake_registry = MagicMock()
    fake_registry.create_job_instance = MagicMock(return_value=_HangingJob())
    monkeypatch.setattr(
        "kontext.jobs.job_registry.get_job_registry",
        lambda: fake_registry,
    )

    backend = _make_service_backend()
    service = JobExecutionService(
        project_id="project-123",
        runtime_provider=MagicMock(),
        service=backend,
    )

    execution = asyncio.ensure_future(service.execute_job_run(str(uuid4()), "worker-1"))
    await asyncio.wait_for(job_started.wait(), timeout=1)

    execution.cancel()
    with pytest.raises(asyncio.CancelledError):
        await execution

    # The job coroutine must have observed cancellation, not been left detached.
    await asyncio.wait_for(job_finished.wait(), timeout=1)
