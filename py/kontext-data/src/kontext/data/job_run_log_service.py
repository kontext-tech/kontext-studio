"""Job run log data service for CRUD operations on job run logs.

Aligned with .NET JobDataService pattern - returns view models from kontext-schema.
Uses sync SQLAlchemy sessions with asyncio.to_thread() wrappers for async interface.
"""

import asyncio
import json
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from kontext.common.protocols import JobRunLogEntry
from kontext.schema import JobRunLogModel, LogLevel

from .base_service import ProjectDataService, ensure_uuid
from .converters import JobRunLogConverter
from .models import Job, JobRun, JobRunLog


class JobRunLogDataService(ProjectDataService):
    """Service for managing JobRunLog entities in project databases.

    Returns view models from kontext-schema for API compatibility.
    Uses sync SQLAlchemy sessions with asyncio.to_thread() for async methods.
    """

    async def add_log_async(
        self,
        *,
        job_run_id: UUID,
        level: LogLevel = LogLevel.INFORMATION,
        message: str,
        data: str | None = None,
    ) -> JobRunLogModel:
        """Add a log entry for a job run (async wrapper)."""
        return await asyncio.to_thread(
            self._add_log_sync,
            job_run_id=job_run_id,
            level=level,
            message=message,
            data=data,
        )

    async def add_logs_async(
        self,
        *,
        job_run_id: UUID,
        entries: Sequence[JobRunLogEntry],
    ) -> None:
        """Add multiple log entries in a single transaction (async wrapper).

        All-or-nothing: either every entry lands or none does, so an
        at-least-once caller replaying the batch can never produce duplicates.
        """
        await asyncio.to_thread(
            self._add_logs_sync, job_run_id=ensure_uuid(job_run_id), entries=entries
        )

    def _add_logs_sync(
        self,
        *,
        job_run_id: UUID,
        entries: Sequence[JobRunLogEntry],
    ) -> None:
        """Add multiple log entries for a job run (single transaction)."""
        if not entries:
            return
        with self._session_scope() as session:
            run_stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == job_run_id, Job.project_id == self.project_uuid)
            )
            run = session.execute(run_stmt).scalar_one_or_none()
            if run is None:
                raise ValueError("Job run not found for this project")

            session.add_all(
                JobRunLog(
                    job_run_id=job_run_id,
                    level=entry.level.value,
                    message=entry.message,
                    data=(json.dumps(entry.data) if entry.data is not None else None),
                )
                for entry in entries
            )
            session.flush()

    def _add_log_sync(
        self,
        *,
        job_run_id: UUID,
        level: LogLevel = LogLevel.INFORMATION,
        message: str,
        data: str | None = None,
    ) -> JobRunLogModel:
        """Add a log entry for a job run.

        Args:
            job_run_id: The parent job run ID.
            level: Log level enum value.
            message: The log message.
            data: Optional JSON additional data.

        Returns:
            The created JobRunLogModel.
        """
        with self._session_scope() as session:
            run_stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == job_run_id, Job.project_id == self.project_uuid)
            )
            run = session.execute(run_stmt).scalar_one_or_none()
            if run is None:
                raise ValueError("Job run not found for this project")

            log = JobRunLog(job_run_id=job_run_id, level=level.value, message=message, data=data)
            session.add(log)
            session.flush()

            return JobRunLogConverter.to_view_model(log, job_id=str(run.job_id))

    async def get_logs_for_run_async(
        self, job_run_id: UUID, limit: int | None = None, level: LogLevel | None = None
    ) -> list[JobRunLogModel]:
        """Get log entries for a job run (async wrapper)."""
        return await asyncio.to_thread(
            self._get_logs_for_run_sync, ensure_uuid(job_run_id), limit, level
        )

    def _get_logs_for_run_sync(
        self, job_run_id: UUID, limit: int | None = None, level: LogLevel | None = None
    ) -> list[JobRunLogModel]:
        """Get log entries for a job run.

        Args:
            job_run_id: The job run ID.
            limit: Optional maximum number of logs to return.
            level: Optional filter by log level.

        Returns:
            List of JobRunLogModels ordered by timestamp descending.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRunLog)
                .join(JobRun)
                .join(Job)
                .options(selectinload(JobRunLog.job_run))
                .where(
                    JobRunLog.job_run_id == job_run_id,
                    Job.project_id == self.project_uuid,
                )
                .order_by(JobRunLog.timestamp.desc())
            )

            if level is not None:
                stmt = stmt.where(JobRunLog.level == level.value)

            if limit is not None:
                stmt = stmt.limit(limit)

            result = session.execute(stmt)
            logs = result.scalars().all()

            return [JobRunLogConverter.to_view_model(log) for log in logs]

    async def get_logs_for_run_ids_async(
        self,
        job_run_ids: Sequence[UUID | str],
        *,
        limit: int | None = None,
        level: LogLevel | None = None,
    ) -> list[JobRunLogModel]:
        normalized_run_ids = [ensure_uuid(job_run_id) for job_run_id in job_run_ids]
        return await asyncio.to_thread(
            self._get_logs_for_run_ids_sync,
            normalized_run_ids,
            limit,
            level,
        )

    def _get_logs_for_run_ids_sync(
        self,
        job_run_ids: Sequence[UUID],
        limit: int | None = None,
        level: LogLevel | None = None,
    ) -> list[JobRunLogModel]:
        if not job_run_ids:
            return []

        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRunLog)
                .join(JobRun)
                .join(Job)
                .options(selectinload(JobRunLog.job_run))
                .where(
                    JobRunLog.job_run_id.in_(job_run_ids),
                    Job.project_id == self.project_uuid,
                )
                .order_by(JobRunLog.timestamp.desc())
            )

            if level is not None:
                stmt = stmt.where(JobRunLog.level == level.value)

            if limit is not None:
                stmt = stmt.limit(limit)

            result = session.execute(stmt)
            logs = result.scalars().all()

            return [JobRunLogConverter.to_view_model(log) for log in logs]

    async def get_recent_logs_for_run_async(
        self, job_run_id: UUID, limit: int = 100
    ) -> list[JobRunLogModel]:
        """Get the most recent log entries for a job run (async wrapper)."""
        return await asyncio.to_thread(
            self._get_recent_logs_for_run_sync, ensure_uuid(job_run_id), limit
        )

    def _get_recent_logs_for_run_sync(
        self, job_run_id: UUID, limit: int = 100
    ) -> list[JobRunLogModel]:
        """Get the most recent log entries for a job run.

        Args:
            job_run_id: The job run ID.
            limit: Maximum number of logs to return (default: 100).

        Returns:
            List of JobRunLogModels ordered by timestamp descending.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRunLog)
                .join(JobRun)
                .join(Job)
                .options(selectinload(JobRunLog.job_run))
                .where(
                    JobRunLog.job_run_id == job_run_id,
                    Job.project_id == self.project_uuid,
                )
                .order_by(JobRunLog.timestamp.desc())
                .limit(limit)
            )
            result = session.execute(stmt)
            logs = result.scalars().all()

            # Return in chronological order
            return [JobRunLogConverter.to_view_model(log) for log in reversed(logs)]

    async def get_error_logs_for_run_async(self, job_run_id: UUID) -> list[JobRunLogModel]:
        """Get error and critical log entries for a job run (async wrapper)."""
        return await asyncio.to_thread(self._get_error_logs_for_run_sync, ensure_uuid(job_run_id))

    def _get_error_logs_for_run_sync(self, job_run_id: UUID) -> list[JobRunLogModel]:
        """Get error and critical log entries for a job run.

        Args:
            job_run_id: The job run ID.

        Returns:
            List of error/critical JobRunLogModels.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRunLog)
                .join(JobRun)
                .join(Job)
                .options(selectinload(JobRunLog.job_run))
                .where(
                    JobRunLog.job_run_id == job_run_id,
                    Job.project_id == self.project_uuid,
                    JobRunLog.level.in_([LogLevel.ERROR.value, LogLevel.CRITICAL.value]),
                )
                .order_by(JobRunLog.timestamp.asc())
            )
            result = session.execute(stmt)
            logs = result.scalars().all()

            return [JobRunLogConverter.to_view_model(log) for log in logs]

    async def delete_logs_for_run_async(self, job_run_id: UUID) -> int:
        """Delete all log entries for a job run (async wrapper)."""
        return await asyncio.to_thread(self._delete_logs_for_run_sync, ensure_uuid(job_run_id))

    def _delete_logs_for_run_sync(self, job_run_id: UUID) -> int:
        """Delete all log entries for a job run.

        Args:
            job_run_id: The job run ID.

        Returns:
            Number of deleted log entries.
        """
        from sqlalchemy import delete

        with self._session_scope() as session:
            run_stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == job_run_id, Job.project_id == self.project_uuid)
            )
            run = session.execute(run_stmt).scalar_one_or_none()
            if run is None:
                return 0

            # Use bulk delete for efficiency instead of loading all logs into memory
            stmt = delete(JobRunLog).where(JobRunLog.job_run_id == job_run_id)
            result = session.execute(stmt)
            session.flush()
            rowcount = getattr(result, "rowcount", 0)
            return int(rowcount or 0)

    # =========================================================================
    # Internal Methods (for use by other services)
    # =========================================================================

    async def _get_logs_entities_async(self, job_run_id: UUID) -> Sequence[JobRunLog]:
        """Get raw JobRunLog entities (async wrapper for internal use)."""
        return await asyncio.to_thread(self._get_logs_entities_sync, job_run_id)

    def _get_logs_entities_sync(self, job_run_id: UUID) -> Sequence[JobRunLog]:
        """Get raw JobRunLog entities (for internal use).

        Args:
            job_run_id: The job run ID.

        Returns:
            Sequence of JobRunLog entities.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRunLog)
                .join(JobRun)
                .join(Job)
                .where(
                    JobRunLog.job_run_id == job_run_id,
                    Job.project_id == self.project_uuid,
                )
                .order_by(JobRunLog.timestamp.asc())
            )
            result = session.execute(stmt)
            return result.scalars().all()
