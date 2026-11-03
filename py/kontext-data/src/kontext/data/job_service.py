"""Job data service for CRUD operations on jobs.

Aligned with .NET JobDataService pattern - returns view models from kontext-schema.
Uses sync SQLAlchemy sessions with asyncio.to_thread() wrappers.
"""

import asyncio
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select

from kontext.common.jobs.scheduling import CronParser
from kontext.common.utils.datetime_utils import utc_now
from kontext.schema import (
    CreateJobRequest,
    JobModel,
    PaginatedListOfJobModel,
    UpdateJobRequest,
)

from .base_service import ProjectDataService, ensure_uuid, parse_uuid
from .converters import JobConverter
from .job_run_service import JobRunDataService
from .models import Job


class JobDataService(ProjectDataService):
    """Service for managing Job entities in project databases.

    Returns view models from kontext-schema for API compatibility.
    Uses sync SQLAlchemy operations with asyncio.to_thread() wrappers.
    """

    # =========================================================================
    # Async Interface (for FastAPI compatibility)
    # =========================================================================

    async def create_job_async(
        self,
        request: CreateJobRequest,
        *,
        owner_id: UUID | str | None = None,
        created_by: str | None = None,
    ) -> JobModel:
        """Create a new job (async wrapper)."""
        return await asyncio.to_thread(
            self._create_job_sync,
            request,
            owner_id=ensure_uuid(owner_id) if owner_id else None,
            created_by=created_by,
        )

    async def get_job_by_id_async(
        self, job_id: UUID | str, include_deleted: bool = False
    ) -> JobModel | None:
        """Get a job by ID (async wrapper)."""
        return await asyncio.to_thread(
            self._get_job_by_id_sync, ensure_uuid(job_id), include_deleted
        )

    async def get_job_by_type_async(
        self, job_type: str, include_deleted: bool = False
    ) -> JobModel | None:
        """Get a job by its type (async wrapper)."""
        return await asyncio.to_thread(self._get_job_by_type_sync, job_type, include_deleted)

    async def get_or_create_job_for_owner_async(
        self,
        job_type: str,
        owner_id: UUID | str | None,
        request: CreateJobRequest,
        *,
        created_by: str | None = None,
    ) -> JobModel:
        """Get or create a job by type and owner (async wrapper).

        Each user gets their own job instance for a given job type.
        This prevents different users from sharing the same job record.

        Args:
            job_type: The job type to look for or create.
            owner_id: The owner user ID.
            request: The CreateJobRequest for creating a new job if needed.
            created_by: Optional creator identifier for new jobs.

        Returns:
            The existing or newly created JobModel.
        """
        return await asyncio.to_thread(
            self._get_or_create_job_for_owner_sync,
            job_type,
            ensure_uuid(owner_id) if owner_id else None,
            request,
            created_by=created_by,
        )

    async def get_jobs_paginated_async(
        self,
        page_index: int = 1,
        page_size: int = 20,
        include_deleted: bool = False,
        filter_string: str | None = None,
        is_enabled: bool | None = None,
        owner_id: UUID | None = None,
    ) -> PaginatedListOfJobModel:
        """Get paginated jobs (async wrapper)."""
        return await asyncio.to_thread(
            self._get_jobs_paginated_sync,
            page_index,
            page_size,
            include_deleted,
            filter_string,
            is_enabled,
            owner_id=owner_id,
        )

    async def get_enabled_jobs_async(self) -> list[JobModel]:
        """Get all enabled, non-deleted jobs (async wrapper)."""
        return await asyncio.to_thread(self._get_enabled_jobs_sync)

    async def update_job_async(
        self, job_id: UUID, request: UpdateJobRequest, *, updated_by: str | None = None
    ) -> JobModel | None:
        """Update a job's fields (async wrapper)."""
        return await asyncio.to_thread(
            self._update_job_sync, job_id, request, updated_by=updated_by
        )

    async def soft_delete_job_async(self, job_id: UUID) -> bool:
        """Soft delete a job (async wrapper)."""
        return await asyncio.to_thread(self._soft_delete_job_sync, job_id)

    async def job_exists_by_name_async(self, name: str, exclude_id: UUID | None = None) -> bool:
        """Check if a job with the given name exists (async wrapper)."""
        return await asyncio.to_thread(self._job_exists_by_name_sync, name, exclude_id)

    async def enrich_job_with_stats_async(
        self,
        job_vm: JobModel,
        run_service: JobRunDataService,
        *,
        calculate_next_run: bool = True,
    ) -> JobModel:
        """Enrich a job view model with run statistics (async wrapper)."""
        return await asyncio.to_thread(
            self._enrich_job_with_stats_sync,
            job_vm,
            run_service,
            calculate_next_run=calculate_next_run,
        )

    async def enrich_jobs_with_stats_batch_async(
        self,
        job_vms: list[JobModel],
        run_service: JobRunDataService,
        *,
        calculate_next_run: bool = True,
    ) -> list[JobModel]:
        """
        Enrich multiple job view models with run statistics in batch (async wrapper).
        """
        return await asyncio.to_thread(
            self._enrich_jobs_with_stats_batch_sync,
            job_vms,
            run_service,
            calculate_next_run=calculate_next_run,
        )

    async def _get_job_entity_async(
        self, job_id: UUID, include_deleted: bool = False
    ) -> Job | None:
        """Get the raw Job entity (for internal use) (async wrapper)."""
        return await asyncio.to_thread(self._get_job_entity_sync, job_id, include_deleted)

    async def _get_all_jobs_entities_async(self, include_deleted: bool = False) -> Sequence[Job]:
        """Get all Job entities (for internal use) (async wrapper)."""
        return await asyncio.to_thread(self._get_all_jobs_entities_sync, include_deleted)

    # =========================================================================
    # Sync Implementation
    # =========================================================================

    def _create_job_sync(
        self,
        request: CreateJobRequest,
        *,
        owner_id: UUID | None = None,
        created_by: str | None = None,
    ) -> JobModel:
        """Create a new job.

        Args:
            request: The CreateJobRequest with job details.
            owner_id: Optional owner user ID.
            created_by: Optional creator identifier.

        Returns:
            The created job as a JobModel.
        """
        with self._session_scope() as session:
            retry_strategy = request.retry_strategy.value if request.retry_strategy else "None"
            job = Job(
                name=request.name,
                type=request.type,
                description=request.description,
                schedule=request.schedule,
                parameters=request.parameters,
                project_id=parse_uuid(self._project_id),
                timeout=request.timeout or 3600,
                is_enabled=(request.is_enabled if request.is_enabled is not None else True),
                retry_strategy=retry_strategy,
                retry_limit=request.retry_limit or 3,
                owner_id=owner_id,
                created_by=created_by,
            )
            session.add(job)
            session.flush()

            return JobConverter.to_view_model(
                job, project_id=self._project_id, project_name=self._project_name
            )

    def _get_job_by_id_sync(self, job_id: UUID, include_deleted: bool = False) -> JobModel | None:
        """Get a job by ID.

        Args:
            job_id: The job ID.
            include_deleted: Whether to include soft-deleted jobs.

        Returns:
            The JobModel if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = select(Job).where(Job.id == job_id, Job.project_id == self.project_uuid)
            if not include_deleted:
                stmt = stmt.where(Job.is_deleted == False)  # noqa: E712
            result = session.execute(stmt)
            job = result.scalar_one_or_none()

            if job is None:
                return None

            return JobConverter.to_view_model(
                job, project_id=self._project_id, project_name=self._project_name
            )

    def _get_job_by_type_sync(
        self, job_type: str, include_deleted: bool = False
    ) -> JobModel | None:
        """Get a job by its type.

        Args:
            job_type: The job type string.
            include_deleted: Whether to include soft-deleted jobs.

        Returns:
            The JobModel if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = select(Job).where(
                Job.type == job_type, Job.project_id == parse_uuid(self._project_id)
            )
            if not include_deleted:
                stmt = stmt.where(Job.is_deleted == False)  # noqa: E712
            result = session.execute(stmt)
            job = result.scalar_one_or_none()

            if job is None:
                return None

            return JobConverter.to_view_model(
                job, project_id=self._project_id, project_name=self._project_name
            )

    def _get_or_create_job_for_owner_sync(
        self,
        job_type: str,
        owner_id: UUID | None,
        request: CreateJobRequest,
        *,
        created_by: str | None = None,
    ) -> JobModel:
        """Get or create a job by type and owner.

        Each user gets their own job instance for a given job type.
        This prevents different users from sharing the same job record.

        Args:
            job_type: The job type to look for or create.
            owner_id: The owner user ID.
            request: The CreateJobRequest for creating a new job if needed.
            created_by: Optional creator identifier for new jobs.

        Returns:
            The existing or newly created JobModel.
        """
        with self._session_scope() as session:
            # Look for existing job by type AND owner
            stmt = select(Job).where(
                Job.type == job_type,
                Job.project_id == self.project_uuid,
                Job.is_deleted == False,  # noqa: E712
            )
            if owner_id is not None:
                stmt = stmt.where(Job.owner_id == owner_id)
            else:
                stmt = stmt.where(Job.owner_id.is_(None))

            result = session.execute(stmt)
            job = result.scalar_one_or_none()

            if job is not None:
                return JobConverter.to_view_model(
                    job, project_id=self._project_id, project_name=self._project_name
                )

            # Create new job for this owner
            retry_strategy = str(request.retry_strategy) if request.retry_strategy else "None"
            job = Job(
                name=request.name,
                type=request.type,
                description=request.description,
                schedule=request.schedule,
                parameters=request.parameters,
                project_id=parse_uuid(self._project_id),
                timeout=request.timeout or 3600,
                is_enabled=(request.is_enabled if request.is_enabled is not None else True),
                retry_strategy=retry_strategy,
                retry_limit=request.retry_limit or 3,
                owner_id=owner_id,
                created_by=created_by,
            )
            session.add(job)
            session.flush()

            return JobConverter.to_view_model(
                job, project_id=self._project_id, project_name=self._project_name
            )

    def _get_jobs_paginated_sync(
        self,
        page_index: int = 1,
        page_size: int = 20,
        include_deleted: bool = False,
        filter_string: str | None = None,
        is_enabled: bool | None = None,
        owner_id: UUID | None = None,
    ) -> PaginatedListOfJobModel:
        """Get paginated jobs.

        Args:
            page_index: The page number (1-indexed).
            page_size: The number of items per page.
            include_deleted: Whether to include soft-deleted jobs.
            filter_string: Optional filter to search by name.
            is_enabled: Optional filter by enabled status.
            owner_id: Optional filter by owner ID.

        Returns:
            PaginatedListOfJobModel with items and pagination info.
        """
        with self._session_scope(commit=False) as session:
            # Base query (always scoped to project)
            stmt = select(Job).where(Job.project_id == parse_uuid(self._project_id))
            count_stmt = select(func.count(Job.id)).where(
                Job.project_id == parse_uuid(self._project_id)
            )

            if not include_deleted:
                stmt = stmt.where(Job.is_deleted == False)  # noqa: E712
                count_stmt = count_stmt.where(Job.is_deleted == False)  # noqa: E712

            # Apply owner filter
            if owner_id:
                stmt = stmt.where(Job.owner_id == owner_id)
                count_stmt = count_stmt.where(Job.owner_id == owner_id)

            # Apply name filter
            if filter_string:
                stmt = stmt.where(Job.name.ilike(f"%{filter_string}%"))
                count_stmt = count_stmt.where(Job.name.ilike(f"%{filter_string}%"))

            # Apply enabled filter
            if is_enabled is not None:
                stmt = stmt.where(Job.is_enabled == is_enabled)
                count_stmt = count_stmt.where(Job.is_enabled == is_enabled)

            # Get total count
            total_result = session.execute(count_stmt)
            total_count = total_result.scalar() or 0

            # Get paginated items
            offset = (page_index - 1) * page_size
            stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(page_size)
            result = session.execute(stmt)
            jobs = result.scalars().all()

            items = [
                JobConverter.to_view_model(
                    job, project_id=self._project_id, project_name=self._project_name
                )
                for job in jobs
            ]

            return PaginatedListOfJobModel(
                items=items,
                total_count=total_count,
                page_index=page_index,
                page_size=page_size,
            )

    def _get_enabled_jobs_sync(self) -> list[JobModel]:
        """Get all enabled, non-deleted jobs.

        Returns:
            List of enabled JobModels.
        """
        with self._session_scope(commit=False) as session:
            stmt = select(Job).where(
                Job.project_id == parse_uuid(self._project_id),
                Job.is_enabled == True,  # noqa: E712
                Job.is_deleted == False,  # noqa: E712
            )
            result = session.execute(stmt)
            jobs = result.scalars().all()

            return [
                JobConverter.to_view_model(
                    job, project_id=self._project_id, project_name=self._project_name
                )
                for job in jobs
            ]

    def _update_job_sync(
        self, job_id: UUID, request: UpdateJobRequest, *, updated_by: str | None = None
    ) -> JobModel | None:
        """Update a job's fields.

        Args:
            job_id: The ID of the job to update.
            request: The UpdateJobRequest with updated fields.
            updated_by: Optional updater identifier.

        Returns:
            The updated JobModel, or None if not found.
        """
        with self._session_scope() as session:
            stmt = select(Job).where(
                Job.id == job_id,
                Job.project_id == self.project_uuid,
                Job.is_deleted == False,  # noqa: E712
            )
            result = session.execute(stmt)
            job = result.scalar_one_or_none()

            if job is None:
                return None

            # Update fields from request
            if request.name is not None:
                job.name = request.name
            if request.type is not None:
                job.type = request.type
            if request.description is not None:
                job.description = request.description
            if request.schedule is not None:
                job.schedule = request.schedule
            if request.parameters is not None:
                job.parameters = request.parameters
            if request.timeout is not None:
                job.timeout = request.timeout
            if request.is_enabled is not None:
                job.is_enabled = request.is_enabled
            if request.retry_strategy is not None:
                job.retry_strategy = request.retry_strategy.value
            if request.retry_limit is not None:
                job.retry_limit = request.retry_limit
            if updated_by is not None:
                job.updated_by = updated_by

            job.updated_at = utc_now()
            session.flush()

            return JobConverter.to_view_model(
                job, project_id=self._project_id, project_name=self._project_name
            )

    def _soft_delete_job_sync(self, job_id: UUID) -> bool:
        """Soft delete a job.

        Args:
            job_id: The ID of the job to soft delete.

        Returns:
            True if deleted, False if not found.
        """
        with self._session_scope() as session:
            stmt = select(Job).where(
                Job.id == job_id,
                Job.project_id == self.project_uuid,
                Job.is_deleted == False,  # noqa: E712
            )
            result = session.execute(stmt)
            job = result.scalar_one_or_none()

            if job is None:
                return False

            job.is_deleted = True
            job.deleted_at = utc_now()
            session.flush()
            return True

    def _job_exists_by_name_sync(self, name: str, exclude_id: UUID | None = None) -> bool:
        """Check if a job with the given name exists.

        Args:
            name: The job name to check.
            exclude_id: Optional ID to exclude from the check (for updates).

        Returns:
            True if a job with the name exists, False otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = select(Job.id).where(
                Job.name == name,
                Job.project_id == parse_uuid(self._project_id),
                Job.is_deleted == False,  # noqa: E712
            )
            if exclude_id is not None:
                stmt = stmt.where(Job.id != exclude_id)
            result = session.execute(stmt)
            return result.scalar_one_or_none() is not None

    def _enrich_job_with_stats_sync(
        self,
        job_vm: JobModel,
        run_service: JobRunDataService,
        *,
        calculate_next_run: bool = True,
    ) -> JobModel:
        """Enrich a job view model with run statistics.

        Args:
            job_vm: The job view model to enrich.
            run_service: JobRunDataService for stats queries.
            calculate_next_run: Whether to calculate next run date from schedule.

        Returns:
            A new JobModel with stats populated.
        """
        # Get run statistics
        job_id = UUID(job_vm.id) if job_vm.id else None
        stats: dict[str, int] = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "in_progress_runs": 0,
        }
        last_run_status = None
        last_run_date = None
        next_run_date = None

        if job_id:
            stats = run_service._get_job_run_stats_sync(job_id)
            last_run = run_service._get_last_run_for_job_sync(job_id)

            if last_run:
                last_run_status = last_run.status
                last_run_date = last_run.completed_at or last_run.started_at

        # Calculate next run date if scheduled
        if calculate_next_run and job_vm.schedule and CronParser.is_valid(job_vm.schedule):
            next_run = CronParser.get_next_run(job_vm.schedule)
            if next_run:
                next_run_date = next_run

        return JobModel(
            id=job_vm.id,
            name=job_vm.name,
            description=job_vm.description,
            type=job_vm.type,
            schedule=job_vm.schedule,
            parameters=job_vm.parameters,
            timeout=job_vm.timeout,
            is_enabled=job_vm.is_enabled,
            retry_strategy=job_vm.retry_strategy,
            retry_limit=job_vm.retry_limit,
            project_id=job_vm.project_id,
            project_name=job_vm.project_name,
            owner_id=job_vm.owner_id,
            date_created=job_vm.date_created,
            date_modified=job_vm.date_modified,
            last_run_status=last_run_status,
            last_run_date=last_run_date,
            next_run_date=next_run_date,
            total_runs=stats.get("total_runs", 0),
            successful_runs=stats.get("successful_runs", 0),
            failed_runs=stats.get("failed_runs", 0),
            in_progress_runs=stats.get("in_progress_runs", 0),
        )

    def _enrich_jobs_with_stats_batch_sync(
        self,
        job_vms: list[JobModel],
        run_service: JobRunDataService,
        *,
        calculate_next_run: bool = True,
    ) -> list[JobModel]:
        """Enrich multiple job view models with run statistics in batch.

        Uses batch queries to avoid N+1 query issues.

        Args:
            job_vms: The job view models to enrich.
            run_service: JobRunDataService for stats queries.
            calculate_next_run: Whether to calculate next run date from schedule.

        Returns:
            List of JobModels with stats populated.
        """
        if not job_vms:
            return []

        # Collect job IDs
        job_ids = [UUID(vm.id) for vm in job_vms if vm.id]

        # Batch load stats and last runs
        stats_map = run_service._get_job_run_stats_batch_sync(job_ids)
        last_runs_map = run_service._get_last_runs_batch_sync(job_ids)

        # Enrich each job
        enriched_jobs = []
        for job_vm in job_vms:
            job_id = UUID(job_vm.id) if job_vm.id else None

            # Get stats from batch results
            stats = (
                stats_map.get(
                    job_id,
                    {
                        "total_runs": 0,
                        "successful_runs": 0,
                        "failed_runs": 0,
                        "in_progress_runs": 0,
                    },
                )
                if job_id
                else {
                    "total_runs": 0,
                    "successful_runs": 0,
                    "failed_runs": 0,
                    "in_progress_runs": 0,
                }
            )

            # Get last run from batch results
            last_run = last_runs_map.get(job_id) if job_id else None
            last_run_status = last_run.status if last_run else None
            last_run_date = (last_run.completed_at or last_run.started_at) if last_run else None

            # Calculate next run date if scheduled
            next_run_date = None
            if calculate_next_run and job_vm.schedule and CronParser.is_valid(job_vm.schedule):
                next_run = CronParser.get_next_run(job_vm.schedule)
                if next_run:
                    next_run_date = next_run

            enriched_jobs.append(
                JobModel(
                    id=job_vm.id,
                    name=job_vm.name,
                    description=job_vm.description,
                    type=job_vm.type,
                    schedule=job_vm.schedule,
                    parameters=job_vm.parameters,
                    timeout=job_vm.timeout,
                    is_enabled=job_vm.is_enabled,
                    retry_strategy=job_vm.retry_strategy,
                    retry_limit=job_vm.retry_limit,
                    project_id=job_vm.project_id,
                    project_name=job_vm.project_name,
                    owner_id=job_vm.owner_id,
                    date_created=job_vm.date_created,
                    date_modified=job_vm.date_modified,
                    last_run_status=last_run_status,
                    last_run_date=last_run_date,
                    next_run_date=next_run_date,
                    total_runs=stats.get("total_runs", 0),
                    successful_runs=stats.get("successful_runs", 0),
                    failed_runs=stats.get("failed_runs", 0),
                    in_progress_runs=stats.get("in_progress_runs", 0),
                )
            )

        return enriched_jobs

    # =========================================================================
    # Internal Methods (for use by other services)
    # =========================================================================

    def _get_job_entity_sync(self, job_id: UUID, include_deleted: bool = False) -> Job | None:
        """Get the raw Job entity (for internal use by other services).

        Args:
            job_id: The job ID.
            include_deleted: Whether to include soft-deleted jobs.

        Returns:
            The Job entity if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = select(Job).where(Job.id == job_id, Job.project_id == self.project_uuid)
            if not include_deleted:
                stmt = stmt.where(Job.is_deleted == False)  # noqa: E712
            result = session.execute(stmt)
            job = result.scalar_one_or_none()
            if job:
                return self._make_detached(session, job)
            return None

    def _get_all_jobs_entities_sync(self, include_deleted: bool = False) -> Sequence[Job]:
        """Get all Job entities (for internal use).

        Args:
            include_deleted: Whether to include soft-deleted jobs.

        Returns:
            Sequence of Job entities.
        """
        with self._session_scope(commit=False) as session:
            stmt = select(Job).where(Job.project_id == self.project_uuid)
            if not include_deleted:
                stmt = stmt.where(Job.is_deleted == False)  # noqa: E712
            result = session.execute(stmt)
            jobs = result.scalars().all()
            # Detach all entities
            for job in jobs:
                self._make_detached(session, job)
            return jobs
