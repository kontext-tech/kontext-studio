"""Execution-oriented polling helpers shared across API and runtimes."""

from __future__ import annotations

import logging
from uuid import UUID

from kontext.common.utils import poll_until
from kontext.data import JobRunDataService
from kontext.schema import JobRunStatus

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_POLL_TIMEOUT_SECONDS = 300


class JobRunPollingResult:
    """Result of polling a job run for completion."""

    def __init__(
        self,
        status: JobRunStatus,
        result_data: str | None = None,
        error_message: str | None = None,
    ):
        self.status = status
        self.result_data = result_data
        self.error_message = error_message

    @property
    def succeeded(self) -> bool:
        return self.status == JobRunStatus.SUCCEEDED

    @property
    def failed(self) -> bool:
        return self.status in {
            JobRunStatus.FAILED,
            JobRunStatus.CANCELED,
            JobRunStatus.DEADLETTERED,
        }


async def poll_job_run_completion(
    project_id: UUID,
    job_run_id: str,
    timeout_seconds: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
) -> JobRunPollingResult | None:
    """Poll job-run state until it reaches a terminal status."""
    terminal_statuses = {
        JobRunStatus.SUCCEEDED,
        JobRunStatus.FAILED,
        JobRunStatus.CANCELED,
        JobRunStatus.DEADLETTERED,
    }

    poll_count = 0
    last_status: JobRunStatus | None = None

    async def check_job_status() -> JobRunPollingResult | None:
        nonlocal poll_count, last_status
        poll_count += 1

        job_run_service = JobRunDataService(project_id=project_id)
        job_run = await job_run_service.get_run_by_id_async(
            UUID(job_run_id), include_job=False, include_trigger=False
        )
        if not job_run:
            logger.error("Job run %s not found during polling", job_run_id)
            return JobRunPollingResult(
                status=JobRunStatus.FAILED,
                error_message="Job run not found",
            )

        status = job_run.status
        last_status = status
        if poll_count % 10 == 0:
            logger.debug("Job run %s still in status %s", job_run_id, status)

        if status and status in terminal_statuses:
            logger.info("Job run %s completed with status %s", job_run_id, status)
            return JobRunPollingResult(
                status=status,
                result_data=job_run.result_data,
                error_message=job_run.error_message,
            )

        return None

    result = await poll_until(
        check_job_status,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )
    if result:
        return result

    logger.error(
        "Job run %s polling timed out. Last status: %s. "
        "This may indicate the worker is not processing messages.",
        job_run_id,
        last_status,
    )
    return None
