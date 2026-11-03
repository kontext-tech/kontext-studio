"""Project-scoped event recording and job triggering."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from uuid import UUID

from pydantic import BaseModel

from kontext.common.jobs.trigger_actor import event_actor
from kontext.common.messaging import IQueueClient
from kontext.data.event_service import EventDataService
from kontext.data.models import Event
from kontext.jobs.service import JobService
from kontext.schema import (
    CatalogEntityCreatedEventData,
    CatalogEntityDeletedEventData,
    CatalogEntityUpdatedEventData,
    EventType,
    FileCreatedEventData,
    FileDeletedEventData,
    FileSchemaUpdatedEventData,
    JobTriggerType,
    SimpleFileEventData,
)

from .scheduling import create_queued_job_run_and_maybe_dispatch

logger = logging.getLogger(__name__)


# =============================================================================
# Event-to-Job Converters (following .NET EventJobParameterConverter pattern)
# =============================================================================


class EventJobConverter(ABC):
    """
    Abstract base class for converting project events to job parameters.
    Following the same pattern as .NET EventJobParameterConverter.
    """

    @property
    @abstractmethod
    def job_type(self) -> str:
        """The fully qualified job type this converter handles."""
        ...

    @abstractmethod
    def convert(self, event: Event) -> dict | None:
        """
        Convert event to job parameters.

        Args:
            event: The event to convert

        Returns:
            Job parameters dict, or None if conversion fails
        """
        ...


class LakehouseCleanupJobConverter(EventJobConverter):
    """Converts file deletion events to lakehouse cleanup job parameters."""

    @property
    def job_type(self) -> str:
        return "python.jobs.LakehouseCleanupJob"

    def convert(self, event: Event) -> dict | None:
        if not event.content:
            logger.warning(f"Event {event.id} has no content, cannot convert to job params")
            return None

        try:
            data = FileDeletedEventData.model_validate_json(event.content)
            res_type = data.file_type.value if data.file_type else None
            return {
                "project_id": str(data.project_id),
                "file_id": str(data.file_id),
                "file_type": res_type,
            }
        except Exception as e:
            logger.error(f"Failed to convert event {event.id}: {e}")
            return None


# =============================================================================
# Event-to-Job Mappings Configuration
# =============================================================================

# Maps event types to their job converters (same pattern as .NET EventToJobMappings)
EVENT_TO_JOB_MAPPINGS: dict[EventType, list[EventJobConverter]] = {
    EventType.DELETEFILE: [LakehouseCleanupJobConverter()],
}


# =============================================================================
# Event Service
# =============================================================================


class EventService:
    """
    Service for recording project events and scheduling triggered jobs.

    This service:
    1. Records events for audit trail in project SQLite
    2. Converts events to job parameters
    3. Schedules corresponding background jobs using local data services

    Uses queue_client to dispatch job execution messages to the Python job queue.
    """

    def __init__(self, *, project_id: UUID | str, queue_client: IQueueClient | None = None):
        """
        Initialize the event service.

        Args:
            project_id: Project ID for event recording and job scheduling.
            queue_client: Queue client for dispatching job execution messages.
                         If provided, jobs are scheduled locally via SQLite
                         and dispatched via the Python job queue.
        """
        self._project_id = str(project_id)
        self._queue_client = queue_client

    # =========================================================================
    # Resource Event Recording
    # =========================================================================

    async def record_file_created(
        self,
        file: SimpleFileEventData,
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> Event:
        """
        Record a single file creation event.

        Args:
            file: Created file data
            user_id: User who created the file
            ip_address: Client IP address of the request

        Returns:
            Created Event
        """
        return await self.record_files_created([file], user_id, ip_address)

    async def record_files_created(
        self,
        files: list[SimpleFileEventData],
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> Event:
        """
        Record a multiple files creation event.

        Args:
            files: List of created files data
            user_id: User who created the files
            ip_address: Client IP address of the request

        Returns:
            Created Event
        """
        event_type = EventType.CREATEFILE if len(files) == 1 else EventType.CREATEFILES

        event_data = FileCreatedEventData(project_id=self._project_id, files=files)

        file_names = ", ".join(f.name for f in files[:3])
        if len(files) > 3:
            file_names += f" (+{len(files) - 3} more)"

        return await self._record_event(
            event_type=event_type,
            title=f"Created {len(files)} file(s): {file_names}",
            data=event_data,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def record_resource_deleted(
        self,
        file_id: UUID,
        file_type: str | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> Event:
        """
        Record a file deletion event.

        Args:
            file_id: Deleted file ID
            file_type: Type of the deleted file
            user_id: User who deleted the file
            ip_address: Client IP address of the request

        Returns:
            Created Event
        """
        from kontext.schema import FileFormatType

        event_data = FileDeletedEventData(
            project_id=self._project_id,
            file_id=str(file_id),
            file_type=FileFormatType(file_type) if file_type else None,
        )

        return await self._record_event(
            event_type=EventType.DELETEFILE,
            title=f"Deleted file {file_id}",
            data=event_data,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def record_file_schema_updated(
        self,
        file_id: UUID,
        file_type: str | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> Event:
        """
        Record a file schema update event.

        Args:
            file_id: Updated file ID
            file_type: Type of the updated file
            user_id: User who triggered the update (or system)
            ip_address: Client IP address of the request

        Returns:
            Created Event
        """
        from kontext.schema import FileFormatType

        event_data = FileSchemaUpdatedEventData(
            project_id=self._project_id,
            file_id=str(file_id),
            file_type=FileFormatType(file_type) if file_type else None,
        )

        return await self._record_event(
            event_type=EventType.UPDATEFILESCHEMA,
            title=f"Updated schema for file {file_id}",
            data=event_data,
            user_id=user_id,
            ip_address=ip_address,
        )

    # =========================================================================
    # Catalog Entity Event Recording
    # =========================================================================

    async def record_catalog_entity_created(
        self,
        entity_id: UUID,
        entity_name: str,
        connection_id: UUID | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> Event:
        """Record a catalog entity creation event."""
        event_data = CatalogEntityCreatedEventData(
            project_id=self._project_id,
            entity_id=str(entity_id),
            entity_name=entity_name,
            connection_id=str(connection_id) if connection_id else None,
        )

        return await self._record_event(
            event_type=EventType.CREATECATALOGENTITY,
            title=f"Created catalog entity: {entity_name}",
            data=event_data,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def record_catalog_entity_updated(
        self,
        entity_id: UUID,
        entity_name: str,
        connection_id: UUID | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> Event:
        """Record a catalog entity update event."""
        event_data = CatalogEntityUpdatedEventData(
            project_id=self._project_id,
            entity_id=str(entity_id),
            entity_name=entity_name,
            connection_id=str(connection_id) if connection_id else None,
        )

        return await self._record_event(
            event_type=EventType.UPDATECATALOGENTITY,
            title=f"Updated catalog entity: {entity_name}",
            data=event_data,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def record_catalog_entity_deleted(
        self,
        entity_id: UUID,
        entity_name: str,
        connection_id: UUID | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> Event:
        """Record a catalog entity deletion event."""
        event_data = CatalogEntityDeletedEventData(
            project_id=self._project_id,
            entity_id=str(entity_id),
            entity_name=entity_name,
            connection_id=str(connection_id) if connection_id else None,
        )

        return await self._record_event(
            event_type=EventType.DELETECATALOGENTITY,
            title=f"Deleted catalog entity: {entity_name}",
            data=event_data,
            user_id=user_id,
            ip_address=ip_address,
        )

    # =========================================================================
    # Event Processing (Job Scheduling)
    # =========================================================================

    async def _schedule_jobs_for_event(self, event: Event) -> list[UUID]:
        """
        Internal method to schedule jobs triggered by an event.

        Creates queued job runs for all mapped jobs and optionally dispatches
        them when an external queue transport is configured.

        Args:
            event: The event to process

        Returns:
            List of scheduled job run IDs
        """
        return await self._schedule_jobs_locally(event)

    async def _schedule_jobs_locally(self, event: Event) -> list[UUID]:
        """
        Schedule jobs using project-scoped job persistence.

        This creates job definitions and queued job runs directly in the
        project's database, then dispatches them only when a queue client exists.

        Args:
            event: The event to process

        Returns:
            List of scheduled job run IDs
        """
        from kontext.data import JobTriggerDataService
        from kontext.jobs.job_registry import get_job_registry

        scheduled_job_run_ids: list[UUID] = []
        event_type = EventType(event.type)
        converters = EVENT_TO_JOB_MAPPINGS.get(event_type, [])

        if not converters:
            logger.debug(f"No job converters configured for event type {event_type}")
            return scheduled_job_run_ids

        trigger_service = JobTriggerDataService(project_id=self._project_id)
        job_registry = get_job_registry()

        for converter in converters:
            try:
                # Convert event to job parameters
                parameters = converter.convert(event)
                if parameters is None:
                    logger.warning(
                        f"Converter {converter.__class__.__name__} returned None "
                        f"for event {event.id}, skipping job {converter.job_type}"
                    )
                    continue

                # Ensure job definition exists locally
                job_metadata = job_registry.get_job_metadata(converter.job_type)
                if not job_metadata:
                    logger.warning(f"Job type {converter.job_type} not found in registry")
                    continue

                job_service = JobService(project_id=self._project_id)
                job_entity = await job_service.ensure_job_exists_async(
                    job_type=converter.job_type,
                    name=job_metadata.name or converter.job_type,
                    description=job_metadata.description,
                    timeout=300,
                )

                if not job_entity or not job_entity.id:
                    logger.warning(
                        f"Could not find or create job definition for {converter.job_type}"
                    )
                    continue

                job_id = job_entity.id

                # Create an Event trigger record for this job run
                trigger_config = {
                    "event_id": str(event.id),
                    "event_type": event_type.value,
                }
                trigger = await trigger_service.create_trigger_async(
                    job_id=job_id,
                    trigger_type=JobTriggerType.EVENT,
                    configuration=json.dumps(trigger_config),
                    triggered_by=event_actor(str(event.id)),
                )

                job_run, dispatched = await create_queued_job_run_and_maybe_dispatch(
                    project_id=self._project_id,
                    queue_client=self._queue_client,
                    job_id=job_id,
                    parameters=parameters,
                    job_type=converter.job_type,
                    job_name=job_entity.name or converter.job_type,
                    timeout_seconds=job_entity.timeout,
                    triggered_by=event_actor(str(event.id)),
                    trigger_id=trigger.id,
                    priority=5,
                )

                if not job_run.id:
                    logger.warning(
                        "Created job run for %s without an ID; skipping event %s",
                        converter.job_type,
                        event.id,
                    )
                    continue

                scheduled_job_run_ids.append(UUID(str(job_run.id)))

                logger.info(
                    "Created queued job run %s for %s from event %s (%s)%s",
                    job_run.id,
                    converter.job_type,
                    event.id,
                    event_type.value,
                    "" if dispatched else " - awaiting embedded local worker",
                )

            except Exception as e:
                logger.error(
                    f"Failed to schedule job {converter.job_type} for event {event.id}: {e}"
                )
                # Continue with other converters

        return scheduled_job_run_ids

    async def process_event(self, event: Event) -> list[UUID]:
        """
        Process an event and schedule triggered jobs.

        Note: This is typically called internally by record_* methods.
        Use this for manual/batch event processing scenarios.

        Args:
            event: The event to process

        Returns:
            List of scheduled job run IDs
        """
        return await self._schedule_jobs_for_event(event)

    async def mark_event_processed(self, event_id: UUID, error: str | None = None) -> None:
        """
        Mark an event as processed.

        Args:
            event_id: Event ID to mark
            error: Optional error message if processing failed
        """
        data_service = EventDataService(self._project_id)
        await data_service.mark_event_processed_async(event_id, error)

    async def get_unprocessed_events(self, limit: int = 100) -> list[Event]:
        """
        Get unprocessed events for batch processing.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of unprocessed events ordered by creation date
        """
        data_service = EventDataService(self._project_id)
        events = await data_service.get_unprocessed_events_async(limit)
        return list(events)

    # =========================================================================
    # Private Methods
    # =========================================================================

    async def _record_event(
        self,
        event_type: EventType,
        title: str,
        data: BaseModel,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        auto_schedule_jobs: bool = True,
    ) -> Event:
        """
        Internal method to record an event and optionally schedule triggered jobs.

        Args:
            event_type: Type of the event
            title: Human-readable title
            data: Event data payload (Pydantic model)
            user_id: User who triggered the event
            ip_address: Client IP address of the request
            auto_schedule_jobs: Whether to automatically schedule jobs for this event

        Returns:
            Created Event
        """
        data_service = EventDataService(self._project_id)
        event = await data_service.create_event_async(
            event_type=event_type,
            title=title,
            content=data.model_dump_json(),
            user_id=user_id,
            project_id=UUID(self._project_id),
            ip_address=ip_address,
        )

        logger.info(f"Recorded event {event.id} ({event_type.value}): {title}")

        if auto_schedule_jobs:
            try:
                scheduled_jobs = await self._schedule_jobs_for_event(event)
                if scheduled_jobs:
                    logger.info(
                        "Created %s queued job(s) for event %s (%s)",
                        len(scheduled_jobs),
                        event.id,
                        event_type.value,
                    )
            except Exception as e:
                # Log but don't fail event recording if job scheduling fails
                logger.error(f"Failed to schedule jobs for event {event.id}: {e}")

        return event
