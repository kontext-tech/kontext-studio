"""Entity to Model converters for job-related models.

Provides conversion utilities similar to .NET Mapster mappings
to align Python data services with .NET backend patterns.
"""

import contextlib
from datetime import datetime
from uuid import UUID

from sqlalchemy import inspect as sa_inspect

from kontext.common.utils.datetime_utils import normalize_datetime_utc
from kontext.schema import (
    JobModel,
    JobRetryStrategy,
    JobRunLogModel,
    JobRunModel,
    JobRunStatus,
    JobTriggerModel,
    JobTriggerType,
    LogLevel,
    TriggerActorModel,
    TriggerActorType,
)

from .models import Job, JobRun, JobRunLog, JobTrigger


def _normalize_required_datetime(dt: datetime | None) -> datetime:
    """Normalize a required datetime and fail loudly if it is missing."""
    normalized = normalize_datetime_utc(dt)
    if normalized is None:
        raise ValueError("Expected datetime value to be present")
    return normalized


def _trigger_actor_from_entity(trigger: JobTrigger | None) -> TriggerActorModel | None:
    """Build a structured trigger actor from a stored job trigger."""
    if trigger is None or not trigger.triggered_by_type:
        return None

    try:
        actor_type = TriggerActorType(trigger.triggered_by_type)
    except ValueError:
        return None

    return TriggerActorModel(type=actor_type, id=trigger.triggered_by_id)


def _trigger_actor_user_id(actor: TriggerActorModel | None) -> str | None:
    """Return the user id from a trigger actor when it represents a user."""
    if actor is not None and actor.type == TriggerActorType.USER:
        return actor.id
    return None


def _get_loaded_relationship(instance: object, relationship_name: str):
    """Return a loaded relationship without triggering lazy loading."""
    insp = sa_inspect(instance)
    if insp is None:
        return None
    if relationship_name in insp.unloaded:
        return None
    return getattr(instance, relationship_name, None)


class JobConverter:
    """Converter for Job entity to JobModel."""

    @staticmethod
    def to_view_model(
        job: Job,
        *,
        project_id: UUID | str | None = None,
        project_name: str | None = None,
        stats: dict[str, int] | None = None,
        last_run_status: str | None = None,
        last_run_date: datetime | None = None,
        next_run_date: datetime | None = None,
    ) -> JobModel:
        """Convert a Job entity to JobModel.

        Args:
            job: The Job SQLAlchemy entity.
            project_id: The project ID (passed from context).
            project_name: Optional project name.
            stats: Optional run statistics dictionary with keys:
                - total_runs, successful_runs, failed_runs, in_progress_runs
            last_run_status: Status of the last job run.
            last_run_date: Date of the last job run.
            next_run_date: Date of the next scheduled run.

        Returns:
            JobModel with all fields populated.
        """
        # Parse retry strategy
        retry_strategy = JobRetryStrategy.NONE
        if job.retry_strategy:
            try:
                retry_strategy = JobRetryStrategy(job.retry_strategy)
            except ValueError:
                # Fall back to NONE for unrecognized retry strategy values
                retry_strategy = JobRetryStrategy.NONE

        # Parse last run status
        parsed_last_run_status = None
        if last_run_status:
            with contextlib.suppress(ValueError):
                # Leave as None for unrecognized status values
                parsed_last_run_status = JobRunStatus(last_run_status)

        return JobModel(
            id=str(job.id),
            name=job.name,
            description=job.description,
            type=job.type,
            schedule=job.schedule,
            parameters=job.parameters,
            timeout=job.timeout,
            is_enabled=job.is_enabled,
            retry_strategy=retry_strategy,
            retry_limit=job.retry_limit,
            project_id=str(project_id) if project_id else None,
            project_name=project_name,
            owner_id=str(job.owner_id) if job.owner_id else None,
            date_created=_normalize_required_datetime(job.created_at),
            date_modified=normalize_datetime_utc(job.updated_at),
            last_run_status=parsed_last_run_status,
            last_run_date=normalize_datetime_utc(last_run_date),
            next_run_date=normalize_datetime_utc(next_run_date),
            total_runs=stats.get("total_runs", 0) if stats else 0,
            successful_runs=stats.get("successful_runs", 0) if stats else 0,
            failed_runs=stats.get("failed_runs", 0) if stats else 0,
            in_progress_runs=stats.get("in_progress_runs", 0) if stats else 0,
            total_run_duration_seconds=0.0,  # Add missing field
        )


class JobRunConverter:
    """Converter for JobRun entity to JobRunModel."""

    @staticmethod
    def to_view_model(
        job_run: JobRun,
        *,
        project_id: UUID | str | None = None,
        project_name: str | None = None,
        include_job: bool = False,
        include_trigger: bool = False,
    ) -> JobRunModel:
        """Convert a JobRun entity to JobRunModel.

        Args:
            job_run: The JobRun SQLAlchemy entity.
            project_id: The project ID (passed from context).
            project_name: Optional project name.
            include_job: Whether to include the nested Job view model.
            include_trigger: Whether to include the nested JobTrigger view model.

        Returns:
            JobRunModel with all fields populated.
        """
        # Parse status - default to Queued if not set or unrecognized
        status = JobRunStatus.QUEUED
        if job_run.status:
            with contextlib.suppress(ValueError):
                # Default to Queued for unrecognized status values
                status = JobRunStatus(job_run.status)

        loaded_job = _get_loaded_relationship(job_run, "job")
        loaded_trigger = _get_loaded_relationship(job_run, "trigger")

        # Build nested job view model if requested and available
        job_vm = None
        if include_job and loaded_job:
            job_vm = JobConverter.to_view_model(
                loaded_job, project_id=project_id, project_name=project_name
            )

        # Build nested trigger view model if requested and available
        trigger_vm = None
        if include_trigger and loaded_trigger:
            trigger_vm = JobTriggerConverter.to_view_model(loaded_trigger)

        owner_id = (
            str(loaded_job.owner_id)
            if loaded_job and loaded_job.owner_id
            else _trigger_actor_user_id(_trigger_actor_from_entity(loaded_trigger))
        )

        return JobRunModel(
            id=str(job_run.id),
            job_id=str(job_run.job_id),
            job_trigger_id=str(job_run.trigger_id) if job_run.trigger_id else None,
            project_id=str(project_id) if project_id else None,
            project_name=project_name,
            owner_id=owner_id,
            status=status,
            progress=job_run.progress,
            started_at=normalize_datetime_utc(job_run.started_at),
            completed_at=normalize_datetime_utc(job_run.completed_at),
            parameters=job_run.parameters,
            execution_id=job_run.execution_id,
            worker=job_run.worker,
            attempt_count=job_run.attempt_count,
            result_type=job_run.result_type,
            result_data=job_run.result_data,
            error_message=job_run.error_message,
            error_stack=job_run.error_stack,
            created_at=_normalize_required_datetime(job_run.created_at),
            job=job_vm,
            job_trigger=trigger_vm,
        )


class JobTriggerConverter:
    """Converter for JobTrigger entity to JobTriggerModel."""

    @staticmethod
    def to_view_model(
        trigger: JobTrigger,
        *,
        include_job: bool = False,
        project_id: UUID | str | None = None,
        project_name: str | None = None,
    ) -> JobTriggerModel:
        """Convert a JobTrigger entity to JobTriggerModel.

        Args:
            trigger: The JobTrigger SQLAlchemy entity.
            include_job: Whether to include the nested Job view model.
            project_id: The project ID (for nested job).
            project_name: Optional project name (for nested job).

        Returns:
            JobTriggerModel with all fields populated.
        """
        # Parse trigger type
        trigger_type = JobTriggerType.MANUAL
        if trigger.trigger_type:
            try:
                trigger_type = JobTriggerType(trigger.trigger_type)
            except ValueError:
                # Default to MANUAL for unrecognized trigger type values
                trigger_type = JobTriggerType.MANUAL

        loaded_job = _get_loaded_relationship(trigger, "job")

        # Build nested job view model if requested and available
        job_vm = None
        if include_job and loaded_job:
            job_vm = JobConverter.to_view_model(
                loaded_job, project_id=project_id, project_name=project_name
            )

        return JobTriggerModel(
            id=str(trigger.id),
            job_id=str(trigger.job_id),
            trigger_type=trigger_type,
            configuration=trigger.configuration,
            triggered_by=_trigger_actor_from_entity(trigger),
            created_at=_normalize_required_datetime(trigger.created_at),
            is_paused=trigger.is_paused,
            paused_at=normalize_datetime_utc(trigger.paused_at),
            is_deleted=trigger.is_deleted,
            deleted_at=normalize_datetime_utc(trigger.deleted_at),
            last_scheduled_run_at=normalize_datetime_utc(trigger.last_scheduled_run_at),
            job=job_vm,
        )


class JobRunLogConverter:
    """Converter for JobRunLog entity to JobRunLogModel."""

    @staticmethod
    def to_view_model(log: JobRunLog, job_id: str | None = None) -> JobRunLogModel:
        """Convert a JobRunLog entity to JobRunLogModel.

        Args:
            log: The JobRunLog SQLAlchemy entity.
            job_id: Optional job ID to include in the model.
                    If not provided, attempts to get from relationship.

        Returns:
            JobRunLogModel with all fields populated.
        """
        # Parse log level
        level = None
        if log.level:
            try:
                level = LogLevel(log.level)
            except ValueError:
                level = LogLevel.INFORMATION

        # Resolve job_id: use provided value, or get from loaded relationship
        # Use SQLAlchemy inspect to check if job_run is already loaded to avoid
        # triggering lazy loading in async contexts
        resolved_job_id = job_id
        if resolved_job_id is None:
            insp = sa_inspect(log)
            # Check if job_run relationship is loaded (not pending lazy load)
            if insp is not None and "job_run" not in insp.unloaded and log.job_run is not None:
                resolved_job_id = str(log.job_run.job_id)

        return JobRunLogModel(
            id=str(log.id),
            job_run_id=str(log.job_run_id),
            job_id=resolved_job_id if resolved_job_id else "",
            timestamp=_normalize_required_datetime(log.timestamp),
            level=level if level else LogLevel.INFORMATION,
            message=log.message,
            data=log.data,
        )
