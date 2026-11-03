"""Job trigger data service for CRUD operations on job triggers.

Aligned with .NET JobDataService pattern - returns view models from kontext-schema.
Uses sync SQLAlchemy sessions with asyncio.to_thread() for async compatibility.
"""

import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from kontext.common.utils.datetime_utils import utc_now
from kontext.schema import JobTriggerModel, JobTriggerType, TriggerActorModel

from .base_service import ProjectDataService
from .converters import JobTriggerConverter
from .models import Job, JobTrigger

logger = logging.getLogger(__name__)


def _trigger_actor_type(actor: TriggerActorModel | None) -> str | None:
    return actor.type.value if actor else None


def _trigger_actor_id(actor: TriggerActorModel | None) -> str | None:
    return actor.id if actor else None


class JobTriggerDataService(ProjectDataService):
    """Service for managing JobTrigger entities in project databases.

    Uses sync SQLAlchemy sessions with asyncio.to_thread() wrappers
    for async compatibility.
    Returns view models from kontext-schema for API compatibility.
    """

    async def create_trigger_async(
        self,
        *,
        job_id: UUID,
        trigger_type: JobTriggerType,
        configuration: str,
        triggered_by: TriggerActorModel | None = None,
    ) -> JobTriggerModel:
        """Create a new job trigger (async wrapper)."""
        return await asyncio.to_thread(
            self._create_trigger_sync,
            job_id=job_id,
            trigger_type=trigger_type,
            configuration=configuration,
            triggered_by=triggered_by,
        )

    def _create_trigger_sync(
        self,
        *,
        job_id: UUID,
        trigger_type: JobTriggerType,
        configuration: str,
        triggered_by: TriggerActorModel | None = None,
    ) -> JobTriggerModel:
        """Create a new job trigger.

        Args:
            job_id: The parent job ID.
            trigger_type: The trigger type (Scheduled, Event, Manual, etc.).
            configuration: JSON configuration for the trigger.
            triggered_by: Structured actor/artifact that created the trigger.

        Returns:
            The created JobTriggerModel.
        """
        with self._session_scope() as session:
            # Ensure parent job belongs to this project
            from .models import Job

            job_stmt = select(Job).where(Job.id == job_id, Job.project_id == self.project_uuid)
            logger.debug(
                "Looking up job by id=%s project_uuid=%s types: %s %s",
                job_id,
                self.project_uuid,
                type(job_id),
                type(self.project_uuid),
            )
            job = session.execute(job_stmt).scalar_one_or_none()
            if job is None:
                raise ValueError("Job not found for this project")

            trigger = JobTrigger(
                job_id=job_id,
                trigger_type=trigger_type.value,
                configuration=configuration,
                triggered_by_type=_trigger_actor_type(triggered_by),
                triggered_by_id=_trigger_actor_id(triggered_by),
            )
            session.add(trigger)
            session.flush()

            return JobTriggerConverter.to_view_model(
                trigger, project_id=self._project_id, project_name=self._project_name
            )

    async def get_or_create_trigger_async(
        self,
        *,
        job_id: UUID,
        trigger_type: JobTriggerType,
        configuration: str = "{}",
        triggered_by: TriggerActorModel | None = None,
    ) -> JobTriggerModel:
        """Get or create a trigger by job, type, and actor (async wrapper)."""
        return await asyncio.to_thread(
            self._get_or_create_trigger_sync,
            job_id=job_id,
            trigger_type=trigger_type,
            configuration=configuration,
            triggered_by=triggered_by,
        )

    def _get_or_create_trigger_sync(
        self,
        *,
        job_id: UUID,
        trigger_type: JobTriggerType,
        configuration: str = "{}",
        triggered_by: TriggerActorModel | None = None,
    ) -> JobTriggerModel:
        """Get or create a trigger by job, type, and actor.

        Args:
            job_id: The parent job ID.
            trigger_type: The trigger type.
            configuration: JSON configuration for the trigger.
            triggered_by: Structured actor/artifact that created the trigger.

        Returns:
            The created or existing JobTriggerModel.
        """
        with self._session_scope() as session:
            # Check if a trigger already exists for this job, type, and actor
            stmt = select(JobTrigger).where(
                JobTrigger.job_id == job_id,
                JobTrigger.trigger_type == trigger_type.value,
                JobTrigger.triggered_by_type == _trigger_actor_type(triggered_by),
                JobTrigger.triggered_by_id == _trigger_actor_id(triggered_by),
                JobTrigger.is_deleted == False,  # noqa: E712
            )
            trigger = session.execute(stmt).scalar_one_or_none()

            if trigger is None:
                # Ensure parent job belongs to this project
                from .models import Job

                job_stmt = select(Job).where(Job.id == job_id, Job.project_id == self.project_uuid)
                job = session.execute(job_stmt).scalar_one_or_none()
                if job is None:
                    raise ValueError("Job not found for this project")

                trigger = JobTrigger(
                    job_id=job_id,
                    trigger_type=trigger_type.value,
                    configuration=configuration,
                    triggered_by_type=_trigger_actor_type(triggered_by),
                    triggered_by_id=_trigger_actor_id(triggered_by),
                )
                session.add(trigger)
                session.flush()

            return JobTriggerConverter.to_view_model(
                trigger, project_id=self._project_id, project_name=self._project_name
            )

    async def get_trigger_by_id_async(
        self, trigger_id: UUID, include_deleted: bool = False, include_job: bool = False
    ) -> JobTriggerModel | None:
        """Get a job trigger by ID (async wrapper)."""
        return await asyncio.to_thread(
            self._get_trigger_by_id_sync,
            trigger_id,
            include_deleted=include_deleted,
            include_job=include_job,
        )

    def _get_trigger_by_id_sync(
        self, trigger_id: UUID, include_deleted: bool = False, include_job: bool = False
    ) -> JobTriggerModel | None:
        """Get a job trigger by ID.

        Args:
            trigger_id: The trigger ID.
            include_deleted: Whether to include soft-deleted triggers.
            include_job: Whether to include the parent job.

        Returns:
            The JobTriggerModel if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobTrigger)
                .join(Job)
                .where(JobTrigger.id == trigger_id, Job.project_id == self.project_uuid)
            )
            if not include_deleted:
                stmt = stmt.where(JobTrigger.is_deleted == False)  # noqa: E712
            if include_job:
                stmt = stmt.options(selectinload(JobTrigger.job))
            result = session.execute(stmt)
            trigger = result.scalar_one_or_none()

            if trigger is None:
                return None

            return JobTriggerConverter.to_view_model(
                trigger,
                include_job=include_job,
                project_id=self._project_id,
                project_name=self._project_name,
            )

    async def get_triggers_for_job_async(
        self, job_id: UUID, include_deleted: bool = False
    ) -> list[JobTriggerModel]:
        """Get all triggers for a job (async wrapper)."""
        return await asyncio.to_thread(
            self._get_triggers_for_job_sync, job_id, include_deleted=include_deleted
        )

    def _get_triggers_for_job_sync(
        self, job_id: UUID, include_deleted: bool = False
    ) -> list[JobTriggerModel]:
        """Get all triggers for a job.

        Args:
            job_id: The job ID.
            include_deleted: Whether to include soft-deleted triggers.

        Returns:
            List of JobTriggerModels.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobTrigger)
                .join(Job)
                .where(JobTrigger.job_id == job_id, Job.project_id == self.project_uuid)
            )
            if not include_deleted:
                stmt = stmt.where(JobTrigger.is_deleted == False)  # noqa: E712
            stmt = stmt.order_by(JobTrigger.created_at.desc())
            result = session.execute(stmt)
            triggers = result.scalars().all()

            return [
                JobTriggerConverter.to_view_model(
                    trigger,
                    project_id=self._project_id,
                    project_name=self._project_name,
                )
                for trigger in triggers
            ]

    async def get_scheduled_triggers_async(
        self, include_paused: bool = False
    ) -> list[JobTriggerModel]:
        """Get all scheduled (CRON) triggers that are active (async wrapper)."""
        return await asyncio.to_thread(
            self._get_scheduled_triggers_sync, include_paused=include_paused
        )

    def _get_scheduled_triggers_sync(self, include_paused: bool = False) -> list[JobTriggerModel]:
        """Get all scheduled (CRON) triggers that are active.

        Args:
            include_paused: Whether to include paused triggers.

        Returns:
            List of scheduled JobTriggerModels with their jobs loaded.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobTrigger)
                .join(Job)
                .where(
                    JobTrigger.trigger_type == JobTriggerType.SCHEDULED.value,
                    JobTrigger.is_deleted == False,  # noqa: E712
                    Job.project_id == self.project_uuid,
                )
                .options(selectinload(JobTrigger.job))
            )
            if not include_paused:
                stmt = stmt.where(JobTrigger.is_paused == False)  # noqa: E712
            result = session.execute(stmt)
            triggers = result.scalars().all()

            return [
                JobTriggerConverter.to_view_model(
                    trigger,
                    include_job=True,
                    project_id=self._project_id,
                    project_name=self._project_name,
                )
                for trigger in triggers
            ]

    async def get_due_triggers_async(
        self, before_time: datetime | None = None
    ) -> list[JobTriggerModel]:
        """Get scheduled triggers that are due for execution (async wrapper)."""
        return await asyncio.to_thread(self._get_due_triggers_sync, before_time=before_time)

    def _get_due_triggers_sync(self, before_time: datetime | None = None) -> list[JobTriggerModel]:
        """Get scheduled triggers that are due for execution.

        This returns triggers where:
        - trigger_type is "Scheduled"
        - is_paused is False
        - is_deleted is False
        - last_scheduled_run_at is None OR before the specified time

        The actual CRON evaluation should be done in the scheduling module.

        Args:
            before_time: Optional time threshold for last_scheduled_run_at.

        Returns:
            List of potentially due JobTriggerModels with jobs loaded.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobTrigger)
                .join(Job)
                .where(
                    JobTrigger.trigger_type == JobTriggerType.SCHEDULED.value,
                    JobTrigger.is_paused == False,  # noqa: E712
                    JobTrigger.is_deleted == False,  # noqa: E712
                    Job.project_id == self.project_uuid,
                )
                .options(selectinload(JobTrigger.job))
            )

            if before_time is not None:
                # Include triggers never run or last run before threshold
                # Note: Using == None is intentional for SQLAlchemy column comparison
                stmt = stmt.where(
                    (JobTrigger.last_scheduled_run_at == None)  # noqa: E711
                    | (JobTrigger.last_scheduled_run_at < before_time)
                )

            result = session.execute(stmt)
            triggers = result.scalars().all()

            return [
                JobTriggerConverter.to_view_model(
                    trigger,
                    include_job=True,
                    project_id=self._project_id,
                    project_name=self._project_name,
                )
                for trigger in triggers
            ]

    async def update_last_scheduled_run_async(
        self, trigger_id: UUID, run_time: datetime | None = None
    ) -> JobTriggerModel | None:
        """Update a trigger's last scheduled run time (async wrapper)."""
        return await asyncio.to_thread(
            self._update_last_scheduled_run_sync, trigger_id, run_time=run_time
        )

    def _update_last_scheduled_run_sync(
        self, trigger_id: UUID, run_time: datetime | None = None
    ) -> JobTriggerModel | None:
        """Update a trigger's last scheduled run time.

        Args:
            trigger_id: The trigger ID.
            run_time: The run time to set (defaults to now).

        Returns:
            The updated JobTriggerModel or None if not found.
        """
        with self._session_scope() as session:
            stmt = select(JobTrigger).where(
                JobTrigger.id == trigger_id,
                JobTrigger.is_deleted == False,  # noqa: E712
            )
            result = session.execute(stmt)
            trigger = result.scalar_one_or_none()

            if trigger is None:
                return None

            trigger.last_scheduled_run_at = run_time or utc_now()
            session.flush()

            return JobTriggerConverter.to_view_model(
                trigger, project_id=self._project_id, project_name=self._project_name
            )

    async def pause_trigger_async(self, trigger_id: UUID) -> JobTriggerModel | None:
        """Pause a trigger (async wrapper)."""
        return await asyncio.to_thread(self._pause_trigger_sync, trigger_id)

    def _pause_trigger_sync(self, trigger_id: UUID) -> JobTriggerModel | None:
        """Pause a trigger.

        Args:
            trigger_id: The trigger ID.

        Returns:
            The updated JobTriggerModel, or None if not found.
        """
        with self._session_scope() as session:
            stmt = select(JobTrigger).where(
                JobTrigger.id == trigger_id,
                JobTrigger.is_deleted == False,  # noqa: E712
            )
            result = session.execute(stmt)
            trigger = result.scalar_one_or_none()

            if trigger is None:
                return None

            trigger.is_paused = True
            trigger.paused_at = utc_now()
            session.flush()

            return JobTriggerConverter.to_view_model(
                trigger, project_id=self._project_id, project_name=self._project_name
            )

    async def resume_trigger_async(self, trigger_id: UUID) -> JobTriggerModel | None:
        """Resume a paused trigger (async wrapper)."""
        return await asyncio.to_thread(self._resume_trigger_sync, trigger_id)

    def _resume_trigger_sync(self, trigger_id: UUID) -> JobTriggerModel | None:
        """Resume a paused trigger.

        Args:
            trigger_id: The trigger ID.

        Returns:
            The updated JobTriggerModel, or None if not found.
        """
        with self._session_scope() as session:
            stmt = select(JobTrigger).where(
                JobTrigger.id == trigger_id,
                JobTrigger.is_deleted == False,  # noqa: E712
            )
            result = session.execute(stmt)
            trigger = result.scalar_one_or_none()

            if trigger is None:
                return None

            trigger.is_paused = False
            trigger.paused_at = None
            session.flush()

            return JobTriggerConverter.to_view_model(
                trigger, project_id=self._project_id, project_name=self._project_name
            )

    async def soft_delete_trigger_async(self, trigger_id: UUID) -> bool:
        """Soft delete a trigger (async wrapper)."""
        return await asyncio.to_thread(self._soft_delete_trigger_sync, trigger_id)

    def _soft_delete_trigger_sync(self, trigger_id: UUID) -> bool:
        """Soft delete a trigger.

        Args:
            trigger_id: The trigger ID.

        Returns:
            True if deleted, False if not found.
        """
        with self._session_scope() as session:
            stmt = select(JobTrigger).where(
                JobTrigger.id == trigger_id,
                JobTrigger.is_deleted == False,  # noqa: E712
            )
            result = session.execute(stmt)
            trigger = result.scalar_one_or_none()

            if trigger is None:
                return False

            trigger.is_deleted = True
            trigger.deleted_at = utc_now()
            session.flush()
            return True

    async def update_trigger_configuration_async(
        self, trigger_id: UUID, *, configuration: str
    ) -> JobTriggerModel | None:
        """Update a trigger's configuration (async wrapper)."""
        return await asyncio.to_thread(
            self._update_trigger_configuration_sync,
            trigger_id,
            configuration=configuration,
        )

    def _update_trigger_configuration_sync(
        self, trigger_id: UUID, *, configuration: str
    ) -> JobTriggerModel | None:
        """Update a trigger's configuration.

        Args:
            trigger_id: The trigger ID.
            configuration: The new JSON configuration.

        Returns:
            The updated JobTriggerModel, or None if not found.
        """
        with self._session_scope() as session:
            stmt = select(JobTrigger).where(
                JobTrigger.id == trigger_id,
                JobTrigger.is_deleted == False,  # noqa: E712
            )
            result = session.execute(stmt)
            trigger = result.scalar_one_or_none()

            if trigger is None:
                return None

            trigger.configuration = configuration
            session.flush()

            return JobTriggerConverter.to_view_model(
                trigger, project_id=self._project_id, project_name=self._project_name
            )

    # =========================================================================
    # Internal Methods (for use by other services)
    # =========================================================================

    async def _get_trigger_entity_async(
        self, trigger_id: UUID, include_deleted: bool = False
    ) -> JobTrigger | None:
        """Get the raw JobTrigger entity (async wrapper for internal use)."""
        return await asyncio.to_thread(
            self._get_trigger_entity_sync, trigger_id, include_deleted=include_deleted
        )

    def _get_trigger_entity_sync(
        self, trigger_id: UUID, include_deleted: bool = False
    ) -> JobTrigger | None:
        """Get the raw JobTrigger entity (for internal use).

        Args:
            trigger_id: The trigger ID.
            include_deleted: Whether to include soft-deleted triggers.

        Returns:
            The JobTrigger entity if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(JobTrigger)
                .join(Job)
                .where(JobTrigger.id == trigger_id, Job.project_id == self.project_uuid)
            )
            if not include_deleted:
                stmt = stmt.where(JobTrigger.is_deleted == False)  # noqa: E712
            result = session.execute(stmt)
            trigger = result.scalar_one_or_none()
            if trigger:
                return self._make_detached(session, trigger)
            return None

    async def _get_scheduled_trigger_entities_async(
        self, include_paused: bool = False
    ) -> Sequence[JobTrigger]:
        """Get all scheduled trigger entities (async wrapper for internal use)."""
        return await asyncio.to_thread(
            self._get_scheduled_trigger_entities_sync, include_paused=include_paused
        )

    def _get_scheduled_trigger_entities_sync(
        self, include_paused: bool = False
    ) -> Sequence[JobTrigger]:
        """Get all scheduled trigger entities (for internal use).

        Args:
            include_paused: Whether to include paused triggers.

        Returns:
            Sequence of JobTrigger entities.
        """
        with self._session_scope(commit=False) as session:
            # Only load scheduled triggers that belong to this project
            stmt = (
                select(JobTrigger)
                .join(Job)
                .where(
                    JobTrigger.trigger_type == JobTriggerType.SCHEDULED.value,
                    JobTrigger.is_deleted == False,  # noqa: E712
                    Job.project_id == self.project_uuid,
                )
                .options(selectinload(JobTrigger.job))
            )
            if not include_paused:
                stmt = stmt.where(JobTrigger.is_paused == False)  # noqa: E712
            result = session.execute(stmt)
            triggers = result.scalars().all()
            # Detach all entities
            for trigger in triggers:
                self._make_detached(session, trigger)
            return triggers

    async def _get_or_create_trigger_entity_async(
        self,
        *,
        job_id: UUID,
        trigger_type: JobTriggerType,
        configuration: str = "{}",
        triggered_by: TriggerActorModel | None = None,
    ) -> JobTrigger:
        """Get or create a trigger entity (async wrapper for internal use)."""
        return await asyncio.to_thread(
            self._get_or_create_trigger_entity_sync,
            job_id=job_id,
            trigger_type=trigger_type,
            configuration=configuration,
            triggered_by=triggered_by,
        )

    def _get_or_create_trigger_entity_sync(
        self,
        *,
        job_id: UUID,
        trigger_type: JobTriggerType,
        configuration: str = "{}",
        triggered_by: TriggerActorModel | None = None,
    ) -> JobTrigger:
        """Get or create a trigger entity (for internal use)."""
        with self._session_scope() as session:
            # Check if a trigger already exists for this job, type, and actor
            stmt = select(JobTrigger).where(
                JobTrigger.job_id == job_id,
                JobTrigger.trigger_type == trigger_type.value,
                JobTrigger.triggered_by_type == _trigger_actor_type(triggered_by),
                JobTrigger.triggered_by_id == _trigger_actor_id(triggered_by),
                JobTrigger.is_deleted == False,  # noqa: E712
            )
            trigger = session.execute(stmt).scalar_one_or_none()

            if trigger is None:
                # Ensure the parent job belongs to this project
                from .models import Job

                job_stmt = select(Job).where(Job.id == job_id, Job.project_id == self.project_uuid)
                job = session.execute(job_stmt).scalar_one_or_none()
                if job is None:
                    raise ValueError("Job not found for this project")

                trigger = JobTrigger(
                    job_id=job_id,
                    trigger_type=trigger_type.value,
                    configuration=configuration,
                    triggered_by_type=_trigger_actor_type(triggered_by),
                    triggered_by_id=_trigger_actor_id(triggered_by),
                )
                session.add(trigger)
                session.flush()

            return self._make_detached(session, trigger)

    async def _create_trigger_entity_async(
        self,
        *,
        job_id: UUID,
        trigger_type: JobTriggerType,
        configuration: str,
        triggered_by: TriggerActorModel | None = None,
    ) -> JobTrigger:
        """Create a new job trigger entity (async wrapper for internal use)."""
        return await asyncio.to_thread(
            self._create_trigger_entity_sync,
            job_id=job_id,
            trigger_type=trigger_type,
            configuration=configuration,
            triggered_by=triggered_by,
        )

    def _create_trigger_entity_sync(
        self,
        *,
        job_id: UUID,
        trigger_type: JobTriggerType,
        configuration: str,
        triggered_by: TriggerActorModel | None = None,
    ) -> JobTrigger:
        """Create a new job trigger and return the entity (for internal use).

        Args:
            job_id: The parent job ID.
            trigger_type: The trigger type (Scheduled, Event, Manual, etc.).
            configuration: JSON configuration for the trigger.
            triggered_by: Structured actor/artifact that created the trigger.

        Returns:
            The created JobTrigger entity.
        """
        with self._session_scope() as session:
            # Ensure the parent job belongs to this project
            job_stmt = select(Job).where(Job.id == job_id, Job.project_id == self.project_uuid)
            job = session.execute(job_stmt).scalar_one_or_none()
            if job is None:
                raise ValueError("Job not found for this project")

            trigger = JobTrigger(
                job_id=job_id,
                trigger_type=trigger_type.value,
                configuration=configuration,
                triggered_by_type=_trigger_actor_type(triggered_by),
                triggered_by_id=_trigger_actor_id(triggered_by),
            )
            session.add(trigger)
            session.flush()

            return self._make_detached(session, trigger)
