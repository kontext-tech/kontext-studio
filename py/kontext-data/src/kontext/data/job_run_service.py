"""Job run data service for CRUD operations on job runs.

Aligned with .NET JobDataService pattern - returns view models from kontext-schema.
Uses sync SQLAlchemy sessions with asyncio.to_thread() wrappers for async interface.
"""

import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from kontext.common.constants import job_run_lease_seconds
from kontext.common.utils.datetime_utils import utc_now
from kontext.schema import (
    JobRunModel,
    JobTriggerType,
    PaginatedListOfJobRunModel,
    TriggerActorModel,
)

from .base_service import ProjectDataService, ensure_uuid
from .converters import JobRunConverter
from .models import Job, JobRun, JobTrigger

logger = logging.getLogger(__name__)

# Statuses a run never leaves by an ordinary status write. Resetting a run
# back to Queued for retry is a separate, deliberate flow that goes through
# the reset endpoint, not through update_status.
_TERMINAL_JOB_RUN_STATUS_VALUES = frozenset(
    {"Succeeded", "Failed", "Canceled", "TimedOut", "DeadLettered"}
)


class JobRunDataService(ProjectDataService):
    """Service for managing JobRun entities in project databases.

    Returns view models from kontext-schema for API compatibility.
    Uses sync SQLAlchemy sessions with asyncio.to_thread() for async interface.
    """

    async def create_run_async(
        self,
        *,
        job_id: UUID | str,
        parameters: str | None = None,
        trigger_id: UUID | str | None = None,
        status: str = "Queued",
        triggered_by: TriggerActorModel | None = None,
        trigger_type: JobTriggerType = JobTriggerType.MANUAL,
        trigger_configuration: str | None = None,
        attempt_count: int = 0,
        execution_id: str | None = None,
        run_id: UUID | str | None = None,
    ) -> JobRunModel:
        """Create a new job run (async wrapper).

        Args:
            job_id: The parent job ID.
            parameters: Optional JSON string of runtime parameters.
            trigger_id: Optional trigger ID that initiated this run.
            status: Initial status (default: "Queued").
            triggered_by: Structured actor/artifact that triggered the run.
            trigger_type: The trigger type (default: JobTriggerType.MANUAL).
            trigger_configuration: Optional JSON string of trigger configuration.
            attempt_count: The attempt number for this run (default: 0).
            execution_id: Optional queue message/execution ID.
            run_id: Optional client-supplied run ID (idempotency key). When the
                caller needs to cancel a run while it is still executing, it must
                know the ID up front; supplying it here makes that deterministic.

        Returns:
            The created JobRunModel.
        """
        return await asyncio.to_thread(
            self._create_run_sync,
            job_id=ensure_uuid(job_id),
            parameters=parameters,
            trigger_id=ensure_uuid(trigger_id) if trigger_id else None,
            status=status,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            trigger_configuration=trigger_configuration,
            attempt_count=attempt_count,
            execution_id=execution_id,
            run_id=ensure_uuid(run_id) if run_id else None,
        )

    def _create_run_sync(
        self,
        *,
        job_id: UUID,
        parameters: str | None = None,
        trigger_id: UUID | None = None,
        status: str = "Queued",
        triggered_by: TriggerActorModel | None = None,
        trigger_type: JobTriggerType = JobTriggerType.MANUAL,
        trigger_configuration: str | None = None,
        attempt_count: int = 0,
        execution_id: str | None = None,
        run_id: UUID | None = None,
    ) -> JobRunModel:
        """Create a new job run.

        Args:
            job_id: The parent job ID.
            parameters: Optional JSON string of runtime parameters.
            trigger_id: Optional trigger ID that initiated this run.
            status: Initial status (default: "Queued").
            triggered_by: Structured actor/artifact that triggered the run.
            trigger_type: The trigger type (default: JobTriggerType.MANUAL).
            trigger_configuration: Optional JSON string of trigger configuration.
            attempt_count: The attempt number for this run (default: 0).
            execution_id: Optional queue message/execution ID.

        Returns:
            The created JobRunModel.
        """
        # Set execution_id if null (use timestamp format) to match .NET behavior
        if not execution_id:
            execution_id = utc_now().strftime("%Y%m%d%H%M%S%f")[:-3]

        with self._session_scope() as session:
            # Ensure the parent job exists and belongs to this project
            job_stmt = select(Job).where(
                Job.id == job_id,
                Job.project_id == self.project_uuid,
                Job.is_deleted == False,  # noqa: E712
            )
            job_result = session.execute(job_stmt)
            job = job_result.scalar_one_or_none()

            if job is None:
                raise ValueError("Job not found for this project")

            # If no trigger_id is provided, find or create a trigger for this run
            # matching .NET JobDataService.CreateJobRunAsync behavior
            if trigger_id is None:
                # Check if a trigger already exists for this job, type, and actor
                # This avoids creating duplicate triggers for manual/interactive runs
                triggered_by_type = triggered_by.type.value if triggered_by else None
                triggered_by_id = triggered_by.id if triggered_by else None
                trigger_stmt = select(JobTrigger).where(
                    JobTrigger.job_id == job_id,
                    JobTrigger.trigger_type == trigger_type.value,
                    JobTrigger.triggered_by_type == triggered_by_type,
                    JobTrigger.triggered_by_id == triggered_by_id,
                )
                trigger = session.execute(trigger_stmt).scalar_one_or_none()

                if trigger is None:
                    trigger = JobTrigger(
                        job_id=job_id,
                        trigger_type=trigger_type.value,
                        triggered_by_type=triggered_by_type,
                        triggered_by_id=triggered_by_id,
                        configuration=trigger_configuration or "{}",
                    )
                    session.add(trigger)
                    session.flush()

                trigger_id = trigger.id

            job_run = JobRun(
                job_id=job_id,
                parameters=parameters,
                trigger_id=trigger_id,
                status=status,
                attempt_count=attempt_count,
                execution_id=execution_id,
            )
            if run_id is not None:
                job_run.id = run_id
            session.add(job_run)
            session.flush()
            session.expunge(job_run)

            return JobRunConverter.to_view_model(
                job_run, project_id=self._project_id, project_name=self._project_name
            )

    async def get_run_by_id_async(
        self, run_id: UUID | str, include_job: bool = True, include_trigger: bool = True
    ) -> JobRunModel | None:
        """Get a job run by ID (async wrapper).

        Args:
            run_id: The job run ID.
            include_job: Whether to eagerly load the parent job.
            include_trigger: Whether to eagerly load the trigger.

        Returns:
            The JobRunModel if found, None otherwise.
        """
        return await asyncio.to_thread(
            self._get_run_by_id_sync,
            ensure_uuid(run_id),
            include_job=include_job,
            include_trigger=include_trigger,
        )

    def _get_run_by_id_sync(
        self, run_id: UUID, include_job: bool = True, include_trigger: bool = True
    ) -> JobRunModel | None:
        """Get a job run by ID.

        Args:
            run_id: The job run ID.
            include_job: Whether to eagerly load the parent job.
            include_trigger: Whether to eagerly load the trigger.

        Returns:
            The JobRunModel if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == run_id, Job.project_id == self.project_uuid)
            )
            if include_job:
                stmt = stmt.options(selectinload(JobRun.job))
            if include_trigger:
                stmt = stmt.options(selectinload(JobRun.trigger))
            result = session.execute(stmt)
            job_run = result.scalar_one_or_none()

            if job_run is None:
                return None

            session.expunge(job_run)
            return JobRunConverter.to_view_model(
                job_run,
                project_id=self._project_id,
                project_name=self._project_name,
                include_job=include_job,
                include_trigger=include_trigger,
            )

    def claim_next_queued_run_sync(
        self, *, worker_identifier: str, lease_seconds: int | None = None
    ) -> JobRunModel | None:
        """Atomically claim the oldest queued run, if any.

        A single conditional ``UPDATE`` both selects and reserves the run, so
        two worker processes can never claim the same one: only the process
        whose ``UPDATE`` matched still sees ``rowcount == 1``. The transition is
        ``Queued -> Dispatched`` with the claiming worker recorded, which is the
        state the executor then moves to ``Running``.

        The claim stamps a lease (``lease_expires_at``) — the DB-poll analogue
        of a queue visibility timeout. The owning worker renews it while alive
        (fenced on its worker identifier); a lapsed lease marks the run
        reclaimable after a worker crash.

        Args:
            worker_identifier: Identifies this worker process on the run row.
            lease_seconds: Lease duration; defaults to the shared job-lease
                configuration.

        Returns:
            The claimed run as a view model, or ``None`` if nothing was queued.
        """
        effective_lease_seconds = (
            lease_seconds if lease_seconds is not None else job_run_lease_seconds()
        )
        with self._session_scope() as session:
            candidate_id = session.execute(
                select(JobRun.id)
                .join(Job)
                .where(
                    JobRun.status == "Queued",
                    Job.project_id == self.project_uuid,
                    Job.is_deleted == False,  # noqa: E712
                )
                .order_by(JobRun.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()

            if candidate_id is None:
                return None

            result = session.execute(
                update(JobRun)
                .where(JobRun.id == candidate_id, JobRun.status == "Queued")
                .values(
                    status="Dispatched",
                    worker=worker_identifier,
                    started_at=utc_now(),
                    updated_at=utc_now(),
                    lease_expires_at=utc_now() + timedelta(seconds=effective_lease_seconds),
                )
            )
            if result.rowcount != 1:  # type: ignore[attr-defined]
                # Another worker claimed it between the SELECT and UPDATE.
                return None

            session.flush()
            job_run = session.get(JobRun, candidate_id)
            session.refresh(job_run)
            session.expunge(job_run)
            # The claiming worker only needs the run's identity and scope to
            # start it; nested job/trigger are not eager-loaded here, so do not
            # request them (``session.get`` would return ``None`` for them).
            return JobRunConverter.to_view_model(
                job_run,
                project_id=self._project_id,
                project_name=self._project_name,
            )

    async def renew_run_lease_async(
        self, run_id: UUID, *, worker: str, lease_seconds: int | None = None
    ) -> bool:
        """Renew a claimed run's lease (async wrapper).

        Returns:
            True if the lease was extended for this worker; False when the run
            is no longer claimed by *worker* (or no longer claimable state) —
            the caller must treat that as lease loss and stop executing.
        """
        return await asyncio.to_thread(
            self._renew_run_lease_sync,
            run_id,
            worker=worker,
            lease_seconds=lease_seconds,
        )

    def _renew_run_lease_sync(
        self, run_id: UUID, *, worker: str, lease_seconds: int | None = None
    ) -> bool:
        """Renew a claimed run's lease, fenced on the worker identity.

        The conditional ``UPDATE`` doubles as the ownership check: it only
        matches while this worker's claim is intact, so a run reclaimed by the
        reaper (or claimed by someone else) makes renewal return False.
        """
        effective_lease_seconds = (
            lease_seconds if lease_seconds is not None else job_run_lease_seconds()
        )
        with self._session_scope() as session:
            candidate_id = session.execute(
                select(JobRun.id)
                .join(Job)
                .where(
                    JobRun.id == run_id,
                    Job.project_id == self.project_uuid,
                    JobRun.worker == worker,
                    JobRun.status.in_(("Dispatched", "Running")),
                )
                .limit(1)
            ).scalar_one_or_none()
            if candidate_id is None:
                return False

            result = session.execute(
                update(JobRun)
                .where(
                    JobRun.id == candidate_id,
                    JobRun.worker == worker,
                    JobRun.status.in_(("Dispatched", "Running")),
                )
                .values(
                    lease_expires_at=utc_now() + timedelta(seconds=effective_lease_seconds),
                    updated_at=utc_now(),
                )
            )
            if result.rowcount != 1:  # type: ignore[attr-defined]
                return False

            session.flush()
            return True

    async def reclaim_expired_run_leases_async(
        self, *, reason: str, max_attempts: int
    ) -> list[UUID]:
        """Reclaim runs whose claim lease lapsed (async wrapper).

        Worker crashed mid-run: requeue the same run for another claim, or
        dead-letter it once it has exhausted its reclaim budget.

        Args:
            reason: Recorded on the run (error message / audit trail).
            max_attempts: Reclaim budget; a run reclaimed more than
                ``max_attempts`` times is dead-lettered instead of requeued.

        Returns:
            The IDs of the runs that were requeued or dead-lettered.
        """
        return await asyncio.to_thread(
            self._reclaim_expired_run_leases_sync, reason=reason, max_attempts=max_attempts
        )

    def _reclaim_expired_run_leases_sync(self, *, reason: str, max_attempts: int) -> list[UUID]:
        """Reclaim runs whose claim lease lapsed, in a single transaction."""
        with self._session_scope() as session:
            rows = session.execute(
                select(JobRun.id, JobRun.attempt_count)
                .join(Job)
                .where(
                    Job.project_id == self.project_uuid,
                    JobRun.status.in_(("Dispatched", "Running")),
                    JobRun.worker.isnot(None),
                    JobRun.lease_expires_at.isnot(None),
                    JobRun.lease_expires_at < utc_now(),
                )
            ).all()

            reclaimed: list[UUID] = []
            now = utc_now()
            for run_id, attempt_count in rows:
                if (attempt_count or 0) + 1 > max_attempts:
                    # Crash-looping (wedged job or a worker that stays dead):
                    # stop retrying and surface the run as dead-lettered.
                    result = session.execute(
                        update(JobRun)
                        .where(
                            JobRun.id == run_id,
                            JobRun.status.in_(("Dispatched", "Running")),
                        )
                        .values(
                            status="DeadLettered",
                            error_message=reason,
                            completed_at=now,
                            lease_expires_at=None,
                            updated_at=now,
                        )
                    )
                else:
                    # Same-run requeue (visibility-timeout semantics): the run
                    # keeps its identity and history; attempt count ticks up.
                    result = session.execute(
                        update(JobRun)
                        .where(
                            JobRun.id == run_id,
                            JobRun.status.in_(("Dispatched", "Running")),
                        )
                        .values(
                            status="Queued",
                            started_at=None,
                            completed_at=None,
                            progress=None,
                            worker=None,
                            execution_id=None,
                            error_message=reason,
                            error_stack=None,
                            result_type=None,
                            result_data=None,
                            attempt_count=(attempt_count or 0) + 1,
                            lease_expires_at=None,
                            updated_at=now,
                        )
                    )
                # Another process may have reclaimed or completed the run
                # between the SELECT and this conditional UPDATE; only count
                # the rows we actually transitioned.
                if result.rowcount == 1:  # type: ignore[attr-defined]
                    reclaimed.append(run_id)

            if reclaimed:
                session.flush()
            return reclaimed

    async def get_runs_paginated_async(
        self,
        page_index: int = 1,
        page_size: int = 20,
        job_id: UUID | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        owner_id: UUID | None = None,
    ) -> PaginatedListOfJobRunModel:
        """Get paginated job runs (async wrapper).

        Args:
            page_index: The page number (1-indexed).
            page_size: The number of items per page.
            job_id: Optional filter by job ID.
            status: Optional filter by status.
            start_date: Optional filter for runs after this date.
            end_date: Optional filter for runs before this date.
            owner_id: Optional filter by owner ID.

        Returns:
            PaginatedListOfJobRunModel with items and pagination info.
        """
        return await asyncio.to_thread(
            self._get_runs_paginated_sync,
            page_index=page_index,
            page_size=page_size,
            job_id=job_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            owner_id=owner_id,
        )

    def _get_runs_paginated_sync(
        self,
        page_index: int = 1,
        page_size: int = 20,
        job_id: UUID | None = None,
        status: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        owner_id: UUID | None = None,
    ) -> PaginatedListOfJobRunModel:
        """Get paginated job runs.

        Args:
            page_index: The page number (1-indexed).
            page_size: The number of items per page.
            job_id: Optional filter by job ID.
            status: Optional filter by status.
            start_date: Optional filter for runs after this date.
            end_date: Optional filter for runs before this date.
            owner_id: Optional filter by owner ID.

        Returns:
            PaginatedListOfJobRunModel with items and pagination info.
        """
        with self._session_scope(commit=False) as session:
            # Base query (always scoped to project via join to Job)
            stmt = select(JobRun).join(Job).where(Job.project_id == self.project_uuid)
            count_stmt = (
                select(func.count(JobRun.id))
                .select_from(JobRun)
                .join(Job)
                .where(Job.project_id == self.project_uuid)
            )

            # Apply filters
            if owner_id is not None:
                stmt = stmt.where(Job.owner_id == owner_id)
                count_stmt = count_stmt.where(Job.owner_id == owner_id)

            if job_id is not None:
                stmt = stmt.where(JobRun.job_id == job_id)
                count_stmt = count_stmt.where(JobRun.job_id == job_id)

            if status is not None:
                stmt = stmt.where(JobRun.status == status)
                count_stmt = count_stmt.where(JobRun.status == status)

            if start_date is not None:
                stmt = stmt.where(JobRun.created_at >= start_date)
                count_stmt = count_stmt.where(JobRun.created_at >= start_date)

            if end_date is not None:
                stmt = stmt.where(JobRun.created_at <= end_date)
                count_stmt = count_stmt.where(JobRun.created_at <= end_date)

            # Get total count
            total_result = session.execute(count_stmt)
            total_count = total_result.scalar() or 0

            # Get paginated items with job and trigger relationships
            offset = (page_index - 1) * page_size
            stmt = (
                stmt.options(selectinload(JobRun.job), selectinload(JobRun.trigger))
                .order_by(JobRun.created_at.desc())
                .offset(offset)
                .limit(page_size)
            )
            result = session.execute(stmt)
            job_runs = result.scalars().all()
            for job_run in job_runs:
                session.expunge(job_run)

            items = [
                JobRunConverter.to_view_model(
                    job_run,
                    project_id=self._project_id,
                    project_name=self._project_name,
                    include_job=True,
                    include_trigger=True,
                )
                for job_run in job_runs
            ]

            # Calculate total pages
            total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

            return PaginatedListOfJobRunModel(
                items=items,
                total_count=total_count,
                page_index=page_index,
                page_size=page_size,
                total_pages=total_pages,
            )

    async def get_runs_for_job_async(self, job_id: UUID, limit: int = 100) -> list[JobRunModel]:
        """Get recent runs for a specific job (async wrapper).

        Args:
            job_id: The job ID.
            limit: Maximum number of runs to return.

        Returns:
            List of JobRunModels.
        """
        return await asyncio.to_thread(self._get_runs_for_job_sync, job_id, limit=limit)

    def _get_runs_for_job_sync(self, job_id: UUID, limit: int = 100) -> list[JobRunModel]:
        """Get recent runs for a specific job.

        Args:
            job_id: The job ID.
            limit: Maximum number of runs to return.

        Returns:
            List of JobRunModels.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.job_id == job_id, Job.project_id == self.project_uuid)
                .options(selectinload(JobRun.job), selectinload(JobRun.trigger))
                .order_by(JobRun.created_at.desc())
                .limit(limit)
            )
            result = session.execute(stmt)
            job_runs = result.scalars().all()
            for job_run in job_runs:
                session.expunge(job_run)

            return [
                JobRunConverter.to_view_model(
                    job_run,
                    project_id=self._project_id,
                    project_name=self._project_name,
                    include_job=True,
                    include_trigger=True,
                )
                for job_run in job_runs
            ]

    async def get_runs_by_ids_async(
        self,
        run_ids: Sequence[UUID | str],
        *,
        include_job: bool = True,
        include_trigger: bool = True,
    ) -> list[JobRunModel]:
        normalized_run_ids = [ensure_uuid(run_id) for run_id in run_ids if run_id]
        return await asyncio.to_thread(
            self._get_runs_by_ids_sync,
            normalized_run_ids,
            include_job=include_job,
            include_trigger=include_trigger,
        )

    def _get_runs_by_ids_sync(
        self,
        run_ids: Sequence[UUID],
        *,
        include_job: bool = True,
        include_trigger: bool = True,
    ) -> list[JobRunModel]:
        if not run_ids:
            return []

        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id.in_(run_ids), Job.project_id == self.project_uuid)
            )
            if include_job:
                stmt = stmt.options(selectinload(JobRun.job))
            if include_trigger:
                stmt = stmt.options(selectinload(JobRun.trigger))

            result = session.execute(stmt)
            job_runs = result.scalars().all()
            for job_run in job_runs:
                session.expunge(job_run)

            return [
                JobRunConverter.to_view_model(
                    job_run,
                    project_id=self._project_id,
                    project_name=self._project_name,
                    include_job=include_job,
                    include_trigger=include_trigger,
                )
                for job_run in job_runs
            ]

    async def get_total_completed_duration_ms_async(self) -> int:
        """Get total duration (ms) of non-running job runs for the project.

        Includes runs that have both start and completion timestamps and are
        not currently in the "Running" state (e.g., Succeeded, Failed,
        Canceled, TimedOut, DeadLettered).
        """
        return await asyncio.to_thread(self._get_total_completed_duration_ms_sync)

    def _get_total_completed_duration_ms_sync(self) -> int:
        """Calculate total duration (ms) of completed job runs.

        Constructs dialect-specific SQL for PostgreSQL or SQLite.
        Raises ValueError for unsupported dialects.
        """
        with self._session_scope(commit=False) as session:
            dialect_name = (
                getattr(session.bind.dialect, "name", "").lower()
                if session.bind is not None
                else ""
            )

            if dialect_name.startswith("postgres") or dialect_name == "postgresql":
                # Postgres: extract('epoch', interval) * 1000
                stmt = (
                    select(
                        func.coalesce(
                            func.sum(
                                func.extract("epoch", JobRun.completed_at - JobRun.started_at)
                                * 1000
                            ),
                            0,
                        ).label("total_duration_ms")
                    )
                    .select_from(JobRun)
                    .join(Job)
                    .where(
                        JobRun.started_at.isnot(None),
                        JobRun.completed_at.isnot(None),
                        JobRun.completed_at > JobRun.started_at,
                        Job.project_id == self.project_uuid,
                    )
                )
            elif dialect_name == "sqlite":
                # SQLite: (strftime('%s', completed) - strftime('%s', started)) * 1000
                stmt = (
                    select(
                        func.coalesce(
                            func.sum(
                                (
                                    func.strftime("%s", JobRun.completed_at)
                                    - func.strftime("%s", JobRun.started_at)
                                )
                                * 1000
                            ),
                            0,
                        ).label("total_duration_ms")
                    )
                    .select_from(JobRun)
                    .join(Job)
                    .where(
                        JobRun.started_at.isnot(None),
                        JobRun.completed_at.isnot(None),
                        JobRun.completed_at > JobRun.started_at,
                        Job.project_id == self.project_uuid,
                    )
                )
            else:
                raise ValueError(
                    f"Unsupported database dialect '{dialect_name}'. "
                    f"Only PostgreSQL and SQLite are supported."
                )

            result = session.execute(stmt)
            return int(result.scalar() or 0)

    async def update_status_async(
        self,
        run_id: UUID,
        *,
        status: str,
        error_message: str | None = None,
        error_stack: str | None = None,
        result_type: str | None = None,
        result_data: str | None = None,
    ) -> JobRunModel | None:
        """Update a job run's status (async wrapper).

        Terminal outcomes are sticky: once a run holds a terminal status, a
        late or racing write with a *different* terminal status is ignored
        (first terminal outcome wins) so a run completing just after a cancel
        can never rewrite the cancel; a replay of the identical terminal write
        is a stable no-op. Non-terminal transitions (including resetting a run
        back to Queued via the dedicated reset flow) are unaffected.

        Args:
            run_id: The job run ID.
            status: The new status.
            error_message: Optional error message (for failed status).
            error_stack: Optional error stack trace.
            result_type: Optional result type identifier.
            result_data: Optional JSON result data.

        Returns:
            The updated JobRunModel, or None if not found.
        """
        return await asyncio.to_thread(
            self._update_status_sync,
            run_id,
            status=status,
            error_message=error_message,
            error_stack=error_stack,
            result_type=result_type,
            result_data=result_data,
        )

    def _update_status_sync(
        self,
        run_id: UUID,
        *,
        status: str,
        error_message: str | None = None,
        error_stack: str | None = None,
        result_type: str | None = None,
        result_data: str | None = None,
    ) -> JobRunModel | None:
        """Update a job run's status.

        Enforces the first-terminal-wins rule documented on
        :meth:`update_status_async`.

        Args:
            run_id: The job run ID.
            status: The new status.
            error_message: Optional error message (for failed status).
            error_stack: Optional error stack trace.
            result_type: Optional result type identifier.
            result_data: Optional JSON result data.

        Returns:
            The updated JobRunModel — unchanged (current state) when the write
            was ignored as a conflicting terminal write — or None if not found.
        """
        with self._session_scope() as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == run_id, Job.project_id == self.project_uuid)
            )
            result = session.execute(stmt)
            job_run = result.scalar_one_or_none()

            if job_run is None:
                return None

            # First terminal outcome wins: a late or racing write must never
            # rewrite a recorded outcome (e.g. a run completing just after the
            # API canceled it). Identical terminal replays and non-terminal
            # transitions proceed unchanged.
            if job_run.status in _TERMINAL_JOB_RUN_STATUS_VALUES and status != job_run.status:
                session.expunge(job_run)
                return JobRunConverter.to_view_model(
                    job_run, project_id=self._project_id, project_name=self._project_name
                )

            job_run.status = status
            job_run.updated_at = utc_now()

            if error_message is not None:
                job_run.error_message = error_message
            if error_stack is not None:
                job_run.error_stack = error_stack
            if result_type is not None:
                job_run.result_type = result_type
            if result_data is not None:
                job_run.result_data = result_data

            # Set completion timestamp for terminal states. Only set it on the
            # first terminal write so an identical replayed update (at-least-once
            # delivery from workers) leaves the run's observable state stable.
            if status in (
                "Succeeded",
                "Failed",
                "Canceled",
                "TimedOut",
                "DeadLettered",
            ):
                if job_run.completed_at is None:
                    job_run.completed_at = utc_now()
                # A terminal run holds no live claim; drop the worker lease so
                # the run can never look reclaimable.
                job_run.lease_expires_at = None
            else:
                job_run.completed_at = None
                if status == "Running" and job_run.started_at is None:
                    job_run.started_at = utc_now()

            session.flush()
            session.expunge(job_run)

            return JobRunConverter.to_view_model(
                job_run, project_id=self._project_id, project_name=self._project_name
            )

    async def update_progress_async(self, run_id: UUID, *, progress: int) -> JobRunModel | None:
        """Update a job run's progress (async wrapper).

        Args:
            run_id: The job run ID.
            progress: Progress percentage (0-100).

        Returns:
            The updated JobRunModel, or None if not found.
        """
        return await asyncio.to_thread(self._update_progress_sync, run_id, progress=progress)

    def _update_progress_sync(self, run_id: UUID, *, progress: int) -> JobRunModel | None:
        """Update a job run's progress.

        Args:
            run_id: The job run ID.
            progress: Progress percentage (0-100).

        Returns:
            The updated JobRunModel, or None if not found.
        """
        with self._session_scope() as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == run_id, Job.project_id == self.project_uuid)
            )
            result = session.execute(stmt)
            job_run = result.scalar_one_or_none()

            if job_run is None:
                return None

            job_run.progress = max(0, min(100, progress))
            job_run.updated_at = utc_now()
            session.flush()
            session.expunge(job_run)

            return JobRunConverter.to_view_model(
                job_run, project_id=self._project_id, project_name=self._project_name
            )

    async def update_worker_async(
        self, run_id: UUID, *, worker: str, execution_id: str | None = None
    ) -> JobRunModel | None:
        """Update a job run's worker assignment (async wrapper).

        Args:
            run_id: The job run ID.
            worker: The worker process identifier.
            execution_id: Optional queue message/execution ID.

        Returns:
            The updated JobRunModel, or None if not found.
        """
        return await asyncio.to_thread(
            self._update_worker_sync, run_id, worker=worker, execution_id=execution_id
        )

    def _update_worker_sync(
        self, run_id: UUID, *, worker: str, execution_id: str | None = None
    ) -> JobRunModel | None:
        """Update a job run's worker assignment.

        Args:
            run_id: The job run ID.
            worker: The worker process identifier.
            execution_id: Optional queue message/execution ID.

        Returns:
            The updated JobRunModel, or None if not found.
        """
        with self._session_scope() as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == run_id, Job.project_id == self.project_uuid)
            )
            result = session.execute(stmt)
            job_run = result.scalar_one_or_none()

            if job_run is None:
                return None

            job_run.worker = worker
            if execution_id is not None:
                job_run.execution_id = execution_id
            job_run.updated_at = utc_now()
            session.flush()
            session.expunge(job_run)

            return JobRunConverter.to_view_model(
                job_run, project_id=self._project_id, project_name=self._project_name
            )

    async def increment_attempt_count_async(self, run_id: UUID) -> JobRunModel | None:
        """Increment a job run's attempt count (async wrapper).

        Args:
            run_id: The job run ID.

        Returns:
            The updated JobRunModel, or None if not found.
        """
        return await asyncio.to_thread(self._increment_attempt_count_sync, run_id)

    def _increment_attempt_count_sync(self, run_id: UUID) -> JobRunModel | None:
        """Increment a job run's attempt count.

        Args:
            run_id: The job run ID.

        Returns:
            The updated JobRunModel, or None if not found.
        """
        with self._session_scope() as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == run_id, Job.project_id == self.project_uuid)
            )
            result = session.execute(stmt)
            job_run = result.scalar_one_or_none()

            if job_run is None:
                return None

            job_run.attempt_count += 1
            job_run.updated_at = utc_now()
            session.flush()
            session.expunge(job_run)

            return JobRunConverter.to_view_model(
                job_run, project_id=self._project_id, project_name=self._project_name
            )

    async def get_running_runs_async(self) -> list[JobRunModel]:
        """Get all currently running job runs (async wrapper).

        Returns:
            List of running JobRunModels.
        """
        return await asyncio.to_thread(self._get_running_runs_sync)

    def _get_running_runs_sync(self) -> list[JobRunModel]:
        """Get all currently running job runs.

        Returns:
            List of running JobRunModels.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(
                    JobRun.status.in_(["Queued", "Dispatched", "Running"]),
                    Job.project_id == self.project_uuid,
                )
                .options(selectinload(JobRun.job))
                .order_by(JobRun.created_at.desc())
            )
            result = session.execute(stmt)
            job_runs = result.scalars().all()
            for job_run in job_runs:
                session.expunge(job_run)

            return [
                JobRunConverter.to_view_model(
                    job_run,
                    project_id=self._project_id,
                    project_name=self._project_name,
                    include_job=True,
                )
                for job_run in job_runs
            ]

    async def get_failed_runs_async(
        self, since: datetime | None = None, limit: int = 100
    ) -> list[JobRunModel]:
        """Get failed job runs (async wrapper).

        Args:
            since: Optional filter for runs failed after this date.
            limit: Maximum number of runs to return.

        Returns:
            List of failed JobRunModels.
        """
        return await asyncio.to_thread(self._get_failed_runs_sync, since=since, limit=limit)

    def _get_failed_runs_sync(
        self, since: datetime | None = None, limit: int = 100
    ) -> list[JobRunModel]:
        """Get failed job runs.

        Args:
            since: Optional filter for runs failed after this date.
            limit: Maximum number of runs to return.

        Returns:
            List of failed JobRunModels.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.status == "Failed", Job.project_id == self.project_uuid)
                .options(selectinload(JobRun.job))
                .order_by(JobRun.created_at.desc())
                .limit(limit)
            )
            if since is not None:
                stmt = stmt.where(JobRun.completed_at >= since)
            result = session.execute(stmt)
            job_runs = result.scalars().all()
            for job_run in job_runs:
                session.expunge(job_run)

            return [
                JobRunConverter.to_view_model(
                    job_run,
                    project_id=self._project_id,
                    project_name=self._project_name,
                    include_job=True,
                )
                for job_run in job_runs
            ]

    async def get_job_run_stats_async(self, job_id: UUID) -> dict[str, int]:
        """Get run statistics for a job (async wrapper).

        Uses conditional aggregation for a single query instead of
        multiple COUNT queries.

        Args:
            job_id: The job ID.

        Returns:
            Dictionary with total_runs, successful_runs, failed_runs counts.
        """
        return await asyncio.to_thread(self._get_job_run_stats_sync, job_id)

    def _get_job_run_stats_sync(self, job_id: UUID) -> dict[str, int]:
        """Get run statistics for a job.

        Uses conditional aggregation for a single query instead of
        multiple COUNT queries.

        Args:
            job_id: The job ID.

        Returns:
            Dictionary with total_runs, successful_runs, failed_runs counts.
        """
        with self._session_scope(commit=False) as session:
            from sqlalchemy import case

            # Use conditional aggregation to get all stats in a single query
            # Scope the stats to this project's jobs only
            stmt = (
                select(
                    func.count(JobRun.id).label("total_runs"),
                    func.count(case((JobRun.status == "Succeeded", 1))).label("successful_runs"),
                    func.count(case((JobRun.status == "Failed", 1))).label("failed_runs"),
                    func.count(
                        case((JobRun.status.in_(["Queued", "Dispatched", "Running"]), 1))
                    ).label("in_progress_runs"),
                )
                .select_from(JobRun)
                .join(Job)
                .where(JobRun.job_id == job_id, Job.project_id == self.project_uuid)
            )

            result = session.execute(stmt)
            row = result.one()

            return {
                "total_runs": row.total_runs or 0,
                "successful_runs": row.successful_runs or 0,
                "failed_runs": row.failed_runs or 0,
                "in_progress_runs": row.in_progress_runs or 0,
            }

    async def get_job_run_stats_batch_async(
        self, job_ids: list[UUID]
    ) -> dict[UUID, dict[str, int]]:
        """Get run statistics for multiple jobs in a single query (async wrapper).

        Uses conditional aggregation with GROUP BY for efficient batch loading.

        Args:
            job_ids: List of job IDs to get stats for.

        Returns:
            Dictionary mapping job_id to stats dict with keys:
            total_runs, successful_runs, failed_runs, in_progress_runs.
        """
        return await asyncio.to_thread(self._get_job_run_stats_batch_sync, job_ids)

    def _get_job_run_stats_batch_sync(self, job_ids: list[UUID]) -> dict[UUID, dict[str, int]]:
        """Get run statistics for multiple jobs in a single query.

        Uses conditional aggregation with GROUP BY for efficient batch loading.

        Args:
            job_ids: List of job IDs to get stats for.

        Returns:
            Dictionary mapping job_id to stats dict with keys:
            total_runs, successful_runs, failed_runs, in_progress_runs.
        """
        if not job_ids:
            return {}

        with self._session_scope(commit=False) as session:
            from sqlalchemy import case

            # First, restrict to job_ids that belong to this project
            allowed_stmt = select(Job.id).where(
                Job.id.in_(job_ids), Job.project_id == self.project_uuid
            )
            allowed_ids = session.execute(allowed_stmt).scalars().all()
            if not allowed_ids:
                return {
                    job_id: {
                        "total_runs": 0,
                        "successful_runs": 0,
                        "failed_runs": 0,
                        "in_progress_runs": 0,
                    }
                    for job_id in job_ids
                }

            # Use conditional aggregation with GROUP BY for batch loading
            stmt = (
                select(
                    JobRun.job_id,
                    func.count(JobRun.id).label("total_runs"),
                    func.count(case((JobRun.status == "Succeeded", 1))).label("successful_runs"),
                    func.count(case((JobRun.status == "Failed", 1))).label("failed_runs"),
                    func.count(
                        case((JobRun.status.in_(["Queued", "Dispatched", "Running"]), 1))
                    ).label("in_progress_runs"),
                )
                .where(JobRun.job_id.in_(allowed_ids))
                .group_by(JobRun.job_id)
            )

            result = session.execute(stmt)
            rows = result.all()

            # Build result dictionary
            stats_map: dict[UUID, dict[str, int]] = {}
            for row in rows:
                stats_map[row.job_id] = {
                    "total_runs": row.total_runs or 0,
                    "successful_runs": row.successful_runs or 0,
                    "failed_runs": row.failed_runs or 0,
                    "in_progress_runs": row.in_progress_runs or 0,
                }

            # Fill in zeros for jobs with no runs
            empty_stats = {
                "total_runs": 0,
                "successful_runs": 0,
                "failed_runs": 0,
                "in_progress_runs": 0,
            }
            for job_id in job_ids:
                if job_id not in stats_map:
                    stats_map[job_id] = empty_stats.copy()

            return stats_map

    async def get_last_run_for_job_async(self, job_id: UUID) -> JobRunModel | None:
        """Get the most recent run for a job (async wrapper).

        Args:
            job_id: The job ID.

        Returns:
            The most recent JobRunModel or None.
        """
        return await asyncio.to_thread(self._get_last_run_for_job_sync, job_id)

    def _get_last_run_for_job_sync(self, job_id: UUID) -> JobRunModel | None:
        """Get the most recent run for a job.

        Args:
            job_id: The job ID.

        Returns:
            The most recent JobRunModel or None.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.job_id == job_id, Job.project_id == self.project_uuid)
                .order_by(JobRun.created_at.desc())
                .limit(1)
            )
            result = session.execute(stmt)
            job_run = result.scalar_one_or_none()

            if job_run is None:
                return None

            session.expunge(job_run)
            return JobRunConverter.to_view_model(
                job_run, project_id=self._project_id, project_name=self._project_name
            )

    async def get_last_runs_batch_async(self, job_ids: list[UUID]) -> dict[UUID, JobRunModel]:
        """Get the most recent run for multiple jobs in a single query (async wrapper).

        Uses a window function to efficiently get the latest run per job.

        Args:
            job_ids: List of job IDs to get last runs for.

        Returns:
            Dictionary mapping job_id to the most recent JobRunModel.
            Jobs with no runs will not have an entry.
        """
        return await asyncio.to_thread(self._get_last_runs_batch_sync, job_ids)

    def _get_last_runs_batch_sync(self, job_ids: list[UUID]) -> dict[UUID, JobRunModel]:
        """Get the most recent run for multiple jobs in a single query.

        Uses a window function to efficiently get the latest run per job.

        Args:
            job_ids: List of job IDs to get last runs for.

        Returns:
            Dictionary mapping job_id to the most recent JobRunModel.
            Jobs with no runs will not have an entry.
        """
        if not job_ids:
            return {}

        with self._session_scope(commit=False) as session:
            # Restrict to job ids belonging to this project first
            allowed_stmt = select(Job.id).where(
                Job.id.in_(job_ids), Job.project_id == self.project_uuid
            )
            allowed_ids = session.execute(allowed_stmt).scalars().all()
            if not allowed_ids:
                return {}

            from sqlalchemy import and_

            # Subquery to get max created_at per job
            subquery = (
                select(JobRun.job_id, func.max(JobRun.created_at).label("max_created_at"))
                .where(JobRun.job_id.in_(allowed_ids))
                .group_by(JobRun.job_id)
                .subquery()
            )

            # Join to get the actual JobRun records
            stmt = select(JobRun).join(
                subquery,
                and_(
                    JobRun.job_id == subquery.c.job_id,
                    JobRun.created_at == subquery.c.max_created_at,
                ),
            )

            result = session.execute(stmt)
            job_runs = result.scalars().all()
            for job_run in job_runs:
                session.expunge(job_run)

            return {
                job_run.job_id: JobRunConverter.to_view_model(
                    job_run,
                    project_id=self._project_id,
                    project_name=self._project_name,
                )
                for job_run in job_runs
            }

    # =========================================================================
    # Internal Methods (for use by other services)
    # =========================================================================

    async def _get_run_entity_async(self, run_id: UUID, include_job: bool = False) -> JobRun | None:
        """Get the raw JobRun entity (async wrapper for internal use).

        Args:
            run_id: The job run ID.
            include_job: Whether to eagerly load the parent job.

        Returns:
            The JobRun entity if found, None otherwise.
        """
        return await asyncio.to_thread(self._get_run_entity_sync, run_id, include_job=include_job)

    def _get_run_entity_sync(self, run_id: UUID, include_job: bool = False) -> JobRun | None:
        """Get the raw JobRun entity (for internal use).

        Args:
            run_id: The job run ID.
            include_job: Whether to eagerly load the parent job.

        Returns:
            The JobRun entity if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobRun)
                .join(Job)
                .where(JobRun.id == run_id, Job.project_id == self.project_uuid)
            )
            if include_job:
                stmt = stmt.options(selectinload(JobRun.job))
            result = session.execute(stmt)
            job_run = result.scalar_one_or_none()
            if job_run:
                return self._make_detached(session, job_run)
            return None

    async def _create_run_entity_async(
        self,
        *,
        job_id: UUID,
        parameters: str | None = None,
        trigger_id: UUID | None = None,
        status: str = "Queued",
        execution_id: str | None = None,
    ) -> JobRun:
        """Create a new job run and return the entity (async wrapper for internal use).

        Args:
            job_id: The parent job ID.
            parameters: Optional JSON string of runtime parameters.
            trigger_id: Optional trigger ID that initiated this run.
            status: Initial status (default: "Queued").
            execution_id: Optional queue message/execution ID.

        Returns:
            The created JobRun entity.
        """
        return await asyncio.to_thread(
            self._create_run_entity_sync,
            job_id=job_id,
            parameters=parameters,
            trigger_id=trigger_id,
            status=status,
            execution_id=execution_id,
        )

    def _create_run_entity_sync(
        self,
        *,
        job_id: UUID,
        parameters: str | None = None,
        trigger_id: UUID | None = None,
        status: str = "Queued",
        execution_id: str | None = None,
    ) -> JobRun:
        """Create a new job run and return the entity (for internal use).

        Args:
            job_id: The parent job ID.
            parameters: Optional JSON string of runtime parameters.
            trigger_id: Optional trigger ID that initiated this run.
            status: Initial status (default: "Queued").
            execution_id: Optional queue message/execution ID.

        Returns:
            The created JobRun entity.
        """
        # Set execution_id if null (use timestamp format) to match .NET behavior
        if not execution_id:
            execution_id = utc_now().strftime("%Y%m%d%H%M%S%f")[:-3]

        with self._session_scope() as session:
            # Ensure parent job belongs to this project
            job_stmt = select(Job).where(Job.id == job_id, Job.project_id == self.project_uuid)
            job_result = session.execute(job_stmt)
            job = job_result.scalar_one_or_none()

            if job is None:
                raise ValueError("Job not found for this project")

            job_run = JobRun(
                job_id=job_id,
                parameters=parameters,
                trigger_id=trigger_id,
                status=status,
                execution_id=execution_id,
            )
            session.add(job_run)
            session.flush()
            return self._make_detached(session, job_run)
