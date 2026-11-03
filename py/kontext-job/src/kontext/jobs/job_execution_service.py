"""
Job execution service for project-scoped Python jobs.

This service handles job execution with pluggable backends for
database operations. The service contains business logic while
the operations backend handles the actual data access.
"""

import asyncio
import contextlib
import json
import logging
import re
import time
from typing import Any

from kontext.common.protocols import IJobRunServiceProtocol, JobRuntimeProviderProtocol
from kontext.schema import JobModel, JobRunModel, JobRunStatus, LogLevel

from .cancellation import JobCancelledError, get_cancellation_registry
from .job_context import IJobExecutionService, JobContext
from .job_result import JobResult

logger = logging.getLogger(__name__)

# How often the executor re-reads a running run's status to notice a cancel
# issued by another process (the API). Cancellation is persisted as a status
# change, so this polling is how a worker learns about it.
_CANCEL_POLL_INTERVAL_SECONDS = 1.0


class JobExecutionService(IJobExecutionService):
    """
    Job execution service for project-scoped Python jobs.

    Handles all job execution operations including status updates,
    logging, and job result processing. Uses provider-backed
    job run services for API-based communication with the platform.
    """

    def __init__(
        self,
        project_id: str,
        runtime_provider: JobRuntimeProviderProtocol,
        service: IJobRunServiceProtocol,
    ) -> None:
        """
        Initialize the service.

        Args:
            project_id: The project ID to scope operations to.
            runtime_provider: The runtime provider for job dependencies.
            service: The job run service implementation.
        """
        self._project_id = project_id
        self._runtime_provider = runtime_provider
        self._service = service
        self.logger = logging.getLogger(__name__)

    @property
    def runtime_provider(self) -> JobRuntimeProviderProtocol:
        return self._runtime_provider

    async def update_job_run_progress_async(self, run_id: str, progress: int) -> None:
        """Updates job run progress with business logic and logging"""
        try:
            # Validate progress range (business logic)
            if not 0 <= progress <= 100:
                raise ValueError(f"Progress must be between 0 and 100, got {progress}")

            # Use service backend for data access
            await self._service.update_progress(run_id, self._project_id, progress)

            # Add audit log for progress update (business logic)
            await self.add_job_run_log_async(
                run_id,
                LogLevel.INFORMATION,
                f"Job progress updated to {progress}%",
                {"Progress": progress},
            )

        except Exception as e:
            self.logger.error(f"Failed to update job run progress for {run_id}: {e}")
            raise

    async def add_job_run_log_async(
        self,
        run_id: str,
        level: LogLevel,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Adds a log entry with business validation"""
        try:
            # Business validation
            if not message or not message.strip():
                raise ValueError("Log message cannot be empty")

            # Use service backend for data access
            await self._service.add_log(run_id, self._project_id, level, message, data)

        except Exception as e:
            # Don't let logging failures break job execution (business logic)
            self.logger.warning(f"Failed to add job run log: {e}")

    async def update_job_run_status_async(
        self,
        run_id: str,
        status: JobRunStatus,
        error_message: str | None = None,
        result_data: dict[str, Any] | None = None,
    ) -> None:
        """Updates job run status with business logic"""
        try:
            # Use service backend for data access
            await self._service.update_status(
                run_id, self._project_id, status, error_message, result_data
            )

            # Add audit log for status change (business logic)
            status_message = f"Job status changed to {status.value}"
            if error_message:
                status_message += f": {error_message}"

            log_data: dict[str, Any] = {
                "Status": status.value,
                "ErrorMessage": error_message,
            }
            if result_data:
                log_data["HasResultData"] = True

            await self.add_job_run_log_async(run_id, LogLevel.INFORMATION, status_message, log_data)

        except Exception as e:
            self.logger.error(f"Failed to update job run status for {run_id}: {e}")
            raise

    async def update_job_run_worker_async(self, run_id: str, worker: str) -> None:
        """Updates job run worker with audit logging"""
        try:
            # Use service backend for data access
            await self._service.update_worker(run_id, self._project_id, worker)

            # Add audit log for worker assignment (business logic)
            await self.add_job_run_log_async(
                run_id,
                LogLevel.INFORMATION,
                f"Job assigned to worker: {worker}",
                {"Worker": worker},
            )

        except Exception as e:
            self.logger.error(f"Failed to update job run worker for {run_id}: {e}")
            raise

    async def _write_terminal_status_if_owned(
        self,
        run_id: str,
        worker: str,
        status: JobRunStatus,
        *,
        error_message: str | None = None,
        result_data: dict[str, Any] | None = None,
    ) -> bool:
        """Write a terminal status only while this worker still owns the claim.

        Renewal doubles as the fence and the final heartbeat. Losing the lease
        means the run's state now belongs to someone else: a reclaimed
        (requeued) run will be executed again by its next claim, and a run
        canceled by the API is already recorded as Canceled — either way the
        outcome of a superseded execution must not overwrite the run's current
        state. At-least-once semantics make the skip safe: the reclaimed run
        re-executes and records its own outcome.
        """
        try:
            owned = await self._service.renew_lease(run_id, self._project_id, worker)
        except Exception as e:
            self.logger.error(f"Lease renewal failed for job run {run_id}: {e}")
            owned = False
        if not owned:
            self.logger.warning(
                "Skipping terminal status write for job run %s: claim no longer owned "
                "(run was reclaimed for retry, re-claimed elsewhere, or canceled)",
                run_id,
            )
            return False
        await self.update_job_run_status_async(run_id, status, error_message, result_data)
        return True

    async def _mark_run_canceled(
        self, run_id: str, *, worker: str, execution_time_ms: int | None
    ) -> None:
        """Record a cancelled run and its audit log in one place.

        The audit log always lands (inert evidence); the terminal status write
        is fenced on claim ownership via
        :meth:`_write_terminal_status_if_owned` so a superseded execution can
        never label a reclaimed run as cancelled.
        """
        message = "Job execution cancelled"
        data: dict[str, Any] = {"IsCancelled": True}
        if execution_time_ms is not None:
            data["ExecutionTimeMs"] = execution_time_ms
        await self.add_job_run_log_async(run_id, LogLevel.INFORMATION, message, data)
        await self._write_terminal_status_if_owned(run_id, worker, JobRunStatus.CANCELED)

    async def get_job_run_details(self, job_run_id: str) -> JobRunModel | None:
        """Get job run details via service backend"""
        try:
            return await self._service.get_job_run(job_run_id, self._project_id)
        except Exception as e:
            self.logger.error(f"Failed to get job run details for {job_run_id}: {e}")
            raise

    async def get_job_details(self, job_id: str) -> JobModel | None:
        """Get job details via service backend"""
        try:
            return await self._service.get_job(job_id, self._project_id)
        except Exception as e:
            self.logger.error(f"Failed to get job details for {job_id}: {e}")
            raise

    async def _watch_for_cancellation(
        self,
        job_run_id: str,
        cancel_event: asyncio.Event,
        worker: str,
        *,
        poll_interval_seconds: float | None = None,
    ) -> None:
        """Poll the run's persisted status and signal local cancellation on match.

        Cancellation is requested by another process (the API) writing
        ``Canceled`` to the run row, so this process cannot be notified directly.
        Watch the row for the duration of the execution and set the process-local
        cancellation event so the executor can stop. Returns when cancelled; the
        caller cancels this task otherwise.

        The same loop renews the claim lease on a budget so a healthy-but-quiet
        worker is never reclaimed, and treats a failed renewal (lease lost to
        the reaper or another claim) as cancellation of this execution.
        """
        from kontext.common.constants import job_run_lease_seconds

        interval = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else _CANCEL_POLL_INTERVAL_SECONDS
        )
        # Renew at a third of the lease so a couple of missed polls can never
        # race the reaper; a transient renewal error is retried on the next
        # poll rather than killing a healthy run.
        renewal_interval_seconds = max(job_run_lease_seconds() / 3.0, interval)
        last_renewal = time.monotonic()
        while not cancel_event.is_set():
            await asyncio.sleep(interval)

            latest = await self.get_job_run_details(job_run_id)
            if latest is not None and latest.status == JobRunStatus.CANCELED:
                cancel_event.set()
                return

            if time.monotonic() - last_renewal < renewal_interval_seconds:
                continue
            try:
                renewed = await self._service.renew_lease(job_run_id, self._project_id, worker)
            except Exception as exc:
                logger.warning(
                    "Lease renewal for job run %s failed; will retry (%s)", job_run_id, exc
                )
                continue
            last_renewal = time.monotonic()
            if not renewed:
                logger.warning(
                    "Job run %s lease lost (reclaimed or claimed elsewhere); "
                    "aborting this execution",
                    job_run_id,
                )
                cancel_event.set()
                return

    async def execute_job_run(
        self, job_run_id: str, worker_identifier: str, store_result_data: bool = True
    ) -> JobResult | None:
        """Execute a Python job run using the operations backend"""
        try:
            # Get job run details
            job_run = await self.get_job_run_details(job_run_id)
            if not job_run:
                raise ValueError(f"Job run {job_run_id} not found")

            if job_run.status not in [JobRunStatus.QUEUED, JobRunStatus.DISPATCHED]:
                logger.warning(
                    "Job run %s is not in queued/dispatched status: %s",
                    job_run_id,
                    job_run.status,
                )
                return None

            # Update worker identifier
            await self.update_job_run_worker_async(job_run_id, worker_identifier)

            # Respect cancellation before the worker transitions the run to RUNNING.
            refreshed_job_run = await self.get_job_run_details(job_run_id)
            if refreshed_job_run and refreshed_job_run.status == JobRunStatus.CANCELED:
                await self.add_job_run_log_async(
                    job_run_id,
                    LogLevel.INFORMATION,
                    "Job execution skipped because the run was canceled before start",
                )
                return None

            # Update status to running
            await self.update_job_run_status_async(job_run_id, JobRunStatus.RUNNING)

            # Get job details
            if job_run.job_id is None:
                raise ValueError("Job run has no job_id")

            job = await self.get_job_details(job_run.job_id)
            if not job:
                raise ValueError(f"Job {job_run.job_id} not found")

            if not job.type:
                raise ValueError(f"Job {job_run.job_id} has no type defined")
            if not job.name:
                raise ValueError(f"Job {job_run.job_id} has no name defined")

            # Create job instance from registry
            from .job_registry import get_job_registry

            job_registry = get_job_registry()
            job_instance = job_registry.create_job_instance(job.type or "")

            if not job_instance:
                raise ValueError(f"Job type {job.type} not found in Python registry")

            # Parse parameters and convert PascalCase keys to snake_case
            parameters = self._convert_pascal_to_snake_case(json.loads(job_run.parameters or "{}"))

            # Create job context with the job execution service
            context = JobContext(
                job_run_id=job_run_id,
                project_id=self._project_id,
                job_name=job.name,
                parameters=parameters,
                timeout_minutes=job.timeout or 60,
                job_execution_service=self,
                runtime_provider=self._runtime_provider,
            )

            # Calculate timeout in seconds
            timeout_seconds = (job.timeout or 60) * 60

            await self.add_job_run_log_async(
                job_run_id,
                LogLevel.INFORMATION,
                f"Starting job execution with timeout of {timeout_seconds} seconds",
                {"TimeoutSeconds": timeout_seconds},
            )

            # Execute job with timeout, racing against cooperative cancellation.
            start_time = time.time()

            registry = get_cancellation_registry()
            cancel_event = registry.register(job_run_id)
            try:
                # Close the race where a cancel arrived after the pre-start DB
                # check but before this registration.
                latest = await self.get_job_run_details(job_run_id)
                if cancel_event.is_set() or (
                    latest is not None and latest.status == JobRunStatus.CANCELED
                ):
                    await self._mark_run_canceled(
                        job_run_id, worker=worker_identifier, execution_time_ms=None
                    )
                    return None

                job_task = asyncio.ensure_future(job_instance.execute(context, parameters))
                cancel_task = asyncio.ensure_future(registry.wait_for_cancellation(job_run_id))
                # The cancellation signal is process-local, but the cancel itself
                # arrives as a persisted status change from another process (the
                # API). Watch the run's status so a cancel issued elsewhere stops
                # this execution too; the same loop keeps this worker's claim
                # lease renewed and aborts if the lease is lost.
                watch_task = asyncio.ensure_future(
                    self._watch_for_cancellation(job_run_id, cancel_event, worker_identifier)
                )
                try:
                    done, _pending = await asyncio.wait(
                        {job_task, cancel_task},
                        timeout=timeout_seconds,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                finally:
                    # Cancel the waiter tasks so they are not left pending. Also
                    # cancel job_task if it is still running: on outer
                    # cancellation (worker shutdown) CancelledError skips the
                    # job-specific cleanup below, which would otherwise leave the
                    # job detached until the loop closes.
                    cancel_task.cancel()
                    watch_task.cancel()
                    job_cancelled_here = not job_task.done()
                    if job_cancelled_here:
                        job_task.cancel()
                    for task in (cancel_task, watch_task):
                        with contextlib.suppress(asyncio.CancelledError):
                            await task
                    if job_cancelled_here:
                        with contextlib.suppress(asyncio.CancelledError):
                            await job_task

                execution_time_ms = int((time.time() - start_time) * 1000)

                if job_task in done:
                    result = job_task.result()
                    await self.add_job_run_log_async(
                        job_run_id,
                        LogLevel.INFORMATION,
                        f"Job execution completed in {execution_time_ms}ms",
                        {"ExecutionTimeMs": execution_time_ms},
                    )
                elif cancel_task in done:
                    job_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await job_task
                    await self._mark_run_canceled(
                        job_run_id, worker=worker_identifier, execution_time_ms=execution_time_ms
                    )
                    return None
                else:
                    # Neither the job nor cancellation finished: timed out.
                    job_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await job_task
                    timeout_message = f"Job execution timed out after {timeout_seconds} seconds"
                    await self.add_job_run_log_async(
                        job_run_id,
                        LogLevel.ERROR,
                        timeout_message,
                        {
                            "TimeoutSeconds": timeout_seconds,
                            "ExecutionTimeMs": execution_time_ms,
                            "IsTimeout": True,
                        },
                    )
                    result = JobResult.error_result(timeout_message)

            except JobCancelledError:
                execution_time_ms = int((time.time() - start_time) * 1000)
                await self._mark_run_canceled(
                    job_run_id, worker=worker_identifier, execution_time_ms=execution_time_ms
                )
                return None

            except Exception as job_error:
                execution_time_ms = int((time.time() - start_time) * 1000)
                error_message = f"Job execution failed: {job_error!s}"

                await self.add_job_run_log_async(
                    job_run_id,
                    LogLevel.ERROR,
                    error_message,
                    {
                        "ExecutionTimeMs": execution_time_ms,
                        "ErrorType": type(job_error).__name__,
                        "IsExecutionError": True,
                    },
                )

                raise job_error

            finally:
                registry.unregister(job_run_id)

            # Prepare result data for storage
            result_data = self._prepare_result_data(result, store_result_data)

            # Process result — fenced: a superseded execution (claim reclaimed
            # or re-claimed elsewhere, or the run canceled via the API) must not
            # overwrite the run's current state.
            if result.success:
                written = await self._write_terminal_status_if_owned(
                    job_run_id,
                    worker_identifier,
                    JobRunStatus.SUCCEEDED,
                    error_message=result.message,
                    result_data=result_data,
                )
            else:
                written = await self._write_terminal_status_if_owned(
                    job_run_id,
                    worker_identifier,
                    JobRunStatus.FAILED,
                    error_message=result.message,
                    result_data=result_data,
                )
            return result if written else None

        except Exception as e:
            logger.error(f"Error executing Python job run {job_run_id}: {e}")

            # Create error result data for exception cases
            error_result_data = {
                "success": False,
                "message": str(e),
                "result_type": "PythonJobResult",
                "error_type": type(e).__name__,
                "is_exception": True,
            }

            # Fence the failure against a lost claim too, but always surface
            # the error to the worker loop.
            with contextlib.suppress(Exception):
                await self._write_terminal_status_if_owned(
                    job_run_id,
                    worker_identifier,
                    JobRunStatus.FAILED,
                    error_message=str(e),
                    result_data=error_result_data,
                )
            raise

    def _convert_pascal_to_snake_case(self, data: Any) -> Any:
        """
        Recursively converts PascalCase keys in dictionaries to
        snake_case for Python compatibility.
        """
        if isinstance(data, dict):
            return {
                self._pascal_to_snake(key): self._convert_pascal_to_snake_case(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._convert_pascal_to_snake_case(item) for item in data]
        else:
            return data

    def _pascal_to_snake(self, name: str) -> str:
        """Convert PascalCase string to snake_case"""
        return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()

    def _prepare_result_data(
        self, result: JobResult, store_result_data: bool = True
    ) -> dict[str, Any] | None:
        """
        Prepares result data for storage in the database.
        """
        if not result:
            return None

        try:
            result_dict = result.to_dict(include_data=store_result_data)
            result_dict["result_type"] = "PythonJobResult"
            return result_dict

        except Exception as e:
            self.logger.warning(f"Failed to prepare result data: {e}")
            return {
                "success": getattr(result, "success", False),
                "message": getattr(result, "message", str(result)),
                "result_type": "PythonJobResult",
                "serialization_error": str(e),
            }
