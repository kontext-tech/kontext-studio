"""Job execution context for Python jobs in Kontext."""

import abc
import logging
import os
import typing
from typing import cast

from kontext.common.protocols import (
    CatalogManagementServiceProviderProtocol,
    ICatalogManagementServiceProtocol,
    IExecutionRunContextServiceProtocol,
    IFileServiceProtocol,
    IQuerySessionServiceProtocol,
    JobRuntimeProviderProtocol,
)
from kontext.common.utils.datetime_utils import utc_now
from kontext.schema import JobRunStatus, LogLevel


class IJobExecutionService(abc.ABC):
    """Interface for job execution services"""

    @abc.abstractmethod
    async def update_job_run_status_async(
        self,
        run_id: str,
        status: JobRunStatus,
        error_message: str | None = None,
        result_data: dict[str, typing.Any] | None = None,
    ) -> None:
        """Update job run status"""
        pass

    @abc.abstractmethod
    async def update_job_run_worker_async(self, run_id: str, worker: str) -> None:
        """Update job run worker identifier"""
        pass

    @abc.abstractmethod
    async def update_job_run_progress_async(self, run_id: str, progress: int) -> None:
        """Update job run progress"""
        pass

    @abc.abstractmethod
    async def add_job_run_log_async(
        self,
        run_id: str,
        level: LogLevel,
        message: str,
        data: dict[str, typing.Any] | None = None,
    ) -> None:
        """Add log entry for job run"""
        pass


class JobContext:
    """
    Context object for Python job implementations.
    Uses injected runtime providers for platform operations.
    """

    def __init__(
        self,
        job_run_id: str,
        project_id: str | None,
        job_name: str,
        job_execution_service: IJobExecutionService,
        parameters: dict[str, typing.Any],
        runtime_provider: JobRuntimeProviderProtocol,
        timeout_minutes: int = 60,
    ):
        self.job_run_id = job_run_id
        self.project_id = project_id
        self.job_name = job_name
        self.parameters = parameters
        self.timeout_minutes = timeout_minutes
        self.start_time = utc_now()

        # Set up logging
        self.logger = logging.getLogger(f"job.{job_run_id}")

        # Environment variables
        self.environment = os.getenv("ENVIRONMENT", "Development")

        # Initialize job execution service
        self.job_execution_service = job_execution_service

        if runtime_provider is None:
            raise ValueError("JobContext requires a runtime_provider")
        self.runtime_provider = runtime_provider

    def require_runtime_provider(self) -> JobRuntimeProviderProtocol:
        """Return the injected runtime provider or raise if missing."""
        if self.runtime_provider is None:
            raise RuntimeError("JobContext requires a runtime_provider")
        return self.runtime_provider

    def is_cancelled(self) -> bool:
        """Return True when this job run has been asked to cancel."""
        from .cancellation import get_cancellation_registry

        return get_cancellation_registry().is_cancelled(self.job_run_id)

    def raise_if_cancelled(self) -> None:
        """Raise :class:`JobCancelledError` if this run has been cancelled.

        Long-running jobs should call this at safe checkpoints (e.g. inside
        their main loop) to abort promptly instead of running to completion.
        """
        if self.is_cancelled():
            from .cancellation import JobCancelledError

            raise JobCancelledError(self.job_run_id)

    def get_runtime_provider(self) -> JobRuntimeProviderProtocol:
        """Return the injected runtime provider."""
        return self.runtime_provider

    def get_catalog_service(self) -> ICatalogManagementServiceProtocol:
        """Get the catalog management service from the provider."""
        provider = cast(
            CatalogManagementServiceProviderProtocol,
            self.require_runtime_provider(),
        )
        try:
            service = provider.get_catalog_service()
        except NotImplementedError as exc:
            raise RuntimeError("Catalog service is not supported") from exc
        if service is None:
            raise RuntimeError("Catalog service is not available")
        return service

    def get_file_service(self) -> IFileServiceProtocol:
        """Get the file service from the provider."""
        provider = self.require_runtime_provider()
        try:
            service = provider.get_file_service()
        except NotImplementedError as exc:
            raise RuntimeError("File service is not supported") from exc
        if service is None:
            raise RuntimeError("File service is not available")
        return service

    def get_query_session_service(self) -> IQuerySessionServiceProtocol:
        """Get the query session service from the provider."""
        provider = self.require_runtime_provider()
        try:
            service = provider.get_query_session_service()
        except NotImplementedError as exc:
            raise RuntimeError("Query session service is not supported") from exc
        if service is None:
            raise RuntimeError("Query session service is not available")
        return service

    def get_execution_run_context_service(self) -> IExecutionRunContextServiceProtocol:
        """Get the durable execution-run provenance service from the provider."""
        provider = self.require_runtime_provider()
        try:
            service = provider.get_execution_run_context_service()
        except NotImplementedError as exc:
            raise RuntimeError("Execution run context service is not supported") from exc
        if service is None:
            raise RuntimeError("Execution run context service is not available")
        return service

    async def log_info(self, message: str, data: dict[str, typing.Any] | None = None) -> None:
        """Log an info message for this job run"""
        self.logger.info(f"[{self.job_run_id}] {message}")
        await self.job_execution_service.add_job_run_log_async(
            self.job_run_id, LogLevel.INFORMATION, message, data
        )

    async def log_warning(self, message: str, data: dict[str, typing.Any] | None = None) -> None:
        """Log a warning message for this job run"""
        self.logger.warning(f"[{self.job_run_id}] {message}")
        await self.job_execution_service.add_job_run_log_async(
            self.job_run_id, LogLevel.WARNING, message, data
        )

    async def log_error(self, message: str, data: dict[str, typing.Any] | None = None) -> None:
        """Log an error message for this job run"""
        self.logger.error(f"[{self.job_run_id}] {message}")
        await self.job_execution_service.add_job_run_log_async(
            self.job_run_id, LogLevel.ERROR, message, data
        )

    async def log_debug(self, message: str, data: dict[str, typing.Any] | None = None) -> None:
        """Log a debug message for this job run"""
        self.logger.debug(f"[{self.job_run_id}] {message}")
        await self.job_execution_service.add_job_run_log_async(
            self.job_run_id, LogLevel.DEBUG, message, data
        )

    async def update_progress(self, progress: int, message: str = "") -> None:
        """Update job run progress percentage"""
        if message:
            await self.log_info(message)
        await self.job_execution_service.update_job_run_progress_async(self.job_run_id, progress)

    async def update_worker(self, worker_id: str) -> None:
        """Update job run worker identifier"""
        await self.job_execution_service.update_job_run_worker_async(self.job_run_id, worker_id)

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds since job start"""
        return (utc_now() - self.start_time).total_seconds()

    @property
    def elapsed_minutes(self) -> float:
        """Get elapsed time in minutes since job start"""
        return self.elapsed_time / 60.0

    @property
    def is_timeout_exceeded(self) -> bool:
        """Check if job has exceeded its timeout"""
        return self.elapsed_minutes > self.timeout_minutes

    @property
    def remaining_time_minutes(self) -> float:
        """Get remaining time in minutes before timeout"""
        return max(0, self.timeout_minutes - self.elapsed_minutes)

    async def check_timeout(self) -> None:
        """Check for timeout and raise exception if exceeded"""
        if self.is_timeout_exceeded:
            error_msg = f"Job execution exceeded timeout of {self.timeout_minutes} minutes"
            await self.log_error(error_msg)
            raise TimeoutError(error_msg)
