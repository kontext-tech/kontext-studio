"""Event data service for CRUD operations on project events.

This service manages Event entities in project-scoped SQLite databases.
The Event model is aligned with the .NET Kontext.Data.Models.Event<TKey>
structure for consistency with shared frontend components.

Uses sync SQLAlchemy sessions with asyncio.to_thread() wrappers to provide
async interface while avoiding issues with SQLite and async operations.
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from kontext.data.models import Event
from kontext.schema import ChannelType, EventType

from .base_service import ProjectDataService


class EventDataService(ProjectDataService):
    """Service for managing Event entities in project databases.

    This service provides CRUD operations for project-scoped events stored
    in SQLite databases. The Event model matches the .NET Event<TKey> structure,
    enabling shared frontend components between project events.

    Uses sync SQLAlchemy Session internally with asyncio.to_thread() wrappers
    to provide async interface while maintaining compatibility with SQLite.
    """

    def _create_event_sync(
        self,
        *,
        event_type: EventType,
        title: str | None = None,
        content: str | None = None,
        user_id: UUID | None = None,
        project_id: UUID | None = None,
        content_id: UUID | None = None,
        channel_type: ChannelType = ChannelType.API,
        ip_address: str | None = None,
        user_agent: str | None = None,
        path: str | None = None,
    ) -> Event:
        """Sync implementation: Create a new event."""
        with self._session_scope() as session:
            event = Event(
                id=uuid4(),
                type=event_type.value,
                title=title,
                content=content,
                user_id=user_id,
                project_id=project_id,
                content_id=content_id,
                channel_type=channel_type.value,
                ip_address=ip_address,
                user_agent=user_agent,
                path=path,
                is_processed=False,
            )

            session.add(event)
            session.flush()

            return self._make_detached(session, event)

    async def create_event_async(
        self,
        *,
        event_type: EventType,
        title: str | None = None,
        content: str | None = None,
        user_id: UUID | None = None,
        project_id: UUID | None = None,
        content_id: UUID | None = None,
        channel_type: ChannelType = ChannelType.API,
        ip_address: str | None = None,
        user_agent: str | None = None,
        path: str | None = None,
    ) -> Event:
        """Create a new event.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            event_type: The type of event (EventType enum).
            title: Optional human-readable title for the event.
            content: Optional content/description of the event.
            user_id: Optional user ID who triggered the event.
            project_id: Optional project ID the event is associated with.
            content_id: Optional content ID the event relates to.
            channel_type: The channel type (default: ChannelType.API).
            ip_address: Optional IP address of the request.
            user_agent: Optional user agent string.
            path: Optional request path.

        Returns:
            The created Event entity.
        """
        return await asyncio.to_thread(
            self._create_event_sync,
            event_type=event_type,
            title=title,
            content=content,
            user_id=user_id,
            project_id=project_id,
            content_id=content_id,
            channel_type=channel_type,
            ip_address=ip_address,
            user_agent=user_agent,
            path=path,
        )

    def _get_event_by_id_sync(self, event_id: UUID) -> Event | None:
        """Sync implementation: Get an event by ID."""
        with self._session_scope(commit=False) as session:
            stmt = select(Event).where(Event.id == event_id)
            result = session.execute(stmt)
            event = result.scalar_one_or_none()
            if event:
                return self._make_detached(session, event)
            return None

    async def get_event_by_id_async(self, event_id: UUID) -> Event | None:
        """Get an event by ID.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            event_id: The event ID.

        Returns:
            The Event if found, None otherwise.
        """
        return await asyncio.to_thread(self._get_event_by_id_sync, event_id)

    def _get_unprocessed_events_sync(self, limit: int = 100) -> Sequence[Event]:
        """Sync implementation: Get unprocessed events for batch processing."""
        with self._session_scope(commit=False) as session:
            stmt = (
                select(Event)
                .where(Event.is_processed == False)  # noqa: E712
                .order_by(Event.date_created)
                .limit(limit)
            )
            result = session.execute(stmt)
            return result.scalars().all()

    async def get_unprocessed_events_async(self, limit: int = 100) -> Sequence[Event]:
        """Get unprocessed events for batch processing.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            limit: Maximum number of events to return.

        Returns:
            List of unprocessed events ordered by creation date.
        """
        return await asyncio.to_thread(self._get_unprocessed_events_sync, limit)

    def _get_events_by_type_sync(
        self, event_type: str, limit: int = 100, include_processed: bool = False
    ) -> Sequence[Event]:
        """Sync implementation: Get events by type."""
        with self._session_scope(commit=False) as session:
            stmt = select(Event).where(
                Event.type == event_type, Event.project_id == self.project_uuid
            )

            if not include_processed:
                stmt = stmt.where(Event.is_processed == False)  # noqa: E712

            stmt = stmt.order_by(Event.date_created.desc()).limit(limit)

            result = session.execute(stmt)
            return result.scalars().all()

    async def get_events_by_type_async(
        self, event_type: str, limit: int = 100, include_processed: bool = False
    ) -> Sequence[Event]:
        """Get events by type.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            event_type: The event type to filter by.
            limit: Maximum number of events to return.
            include_processed: Whether to include already processed events.

        Returns:
            List of events matching the type.
        """
        return await asyncio.to_thread(
            self._get_events_by_type_sync, event_type, limit, include_processed
        )

    def _mark_event_processed_sync(self, event_id: UUID, error: str | None = None) -> None:
        """Sync implementation: Mark an event as processed."""
        with self._session_scope() as session:
            stmt = (
                update(Event)
                .where(Event.id == event_id, Event.project_id == self.project_uuid)
                .values(
                    is_processed=True,
                    date_processed=datetime.now(UTC),
                    processing_error=error,
                )
            )
            session.execute(stmt)

    async def mark_event_processed_async(self, event_id: UUID, error: str | None = None) -> None:
        """Mark an event as processed.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            event_id: The event ID to mark as processed.
            error: Optional error message if processing failed.
        """
        await asyncio.to_thread(self._mark_event_processed_sync, event_id, error)

    def _mark_events_processed_sync(self, event_ids: list[UUID], error: str | None = None) -> int:
        """Sync implementation: Mark multiple events as processed."""
        if not event_ids:
            return 0

        with self._session_scope() as session:
            stmt = (
                update(Event)
                .where(Event.id.in_(event_ids), Event.project_id == self.project_uuid)
                .values(
                    is_processed=True,
                    date_processed=datetime.now(UTC),
                    processing_error=error,
                )
            )
            result = session.execute(stmt)
            rowcount = getattr(result, "rowcount", 0)
            return int(rowcount or 0)

    async def mark_events_processed_async(
        self, event_ids: list[UUID], error: str | None = None
    ) -> int:
        """Mark multiple events as processed.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            event_ids: List of event IDs to mark as processed.
            error: Optional error message if processing failed.

        Returns:
            Number of events updated.
        """
        return await asyncio.to_thread(self._mark_events_processed_sync, event_ids, error)

    def _count_unprocessed_events_sync(self) -> int:
        """Sync implementation: Count the number of unprocessed events."""
        with self._session_scope(commit=False) as session:
            stmt = (
                select(func.count())
                .select_from(Event)
                .where(
                    Event.is_processed == False,  # noqa: E712
                    Event.project_id == self.project_uuid,
                )
            )
            result = session.execute(stmt)
            return result.scalar_one()

    async def count_unprocessed_events_async(self) -> int:
        """Count the number of unprocessed events.

        Uses asyncio.to_thread() to run sync database operations.

        Returns:
            The count of unprocessed events.
        """
        return await asyncio.to_thread(self._count_unprocessed_events_sync)

    def _get_recent_events_sync(
        self, limit: int = 50, event_types: list[str] | None = None
    ) -> Sequence[Event]:
        """Sync implementation: Get recent events, optionally filtered by type."""
        with self._session_scope(commit=False) as session:
            stmt = select(Event).where(Event.project_id == self.project_uuid)

            if event_types:
                stmt = stmt.where(Event.type.in_(event_types))

            stmt = stmt.order_by(Event.date_created.desc()).limit(limit)

            result = session.execute(stmt)
            return result.scalars().all()

    async def get_recent_events_async(
        self, limit: int = 50, event_types: list[str] | None = None
    ) -> Sequence[Event]:
        """Get recent events, optionally filtered by type.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            limit: Maximum number of events to return.
            event_types: Optional list of event types to filter by.

        Returns:
            List of recent events ordered by creation date (newest first).
        """
        return await asyncio.to_thread(self._get_recent_events_sync, limit, event_types)

    def _get_paginated_events_sync(
        self,
        page_index: int = 1,
        page_size: int = 20,
        event_types: list[str] | None = None,
        days_limit: int = 30,
    ) -> tuple[Sequence[Event], int]:
        """Sync implementation: Get paginated events within a date range."""
        with self._session_scope(commit=False) as session:
            cutoff_date = datetime.now(UTC) - timedelta(days=days_limit)

            # Build base query with date and project filter
            base_stmt = select(Event).where(
                Event.date_created >= cutoff_date, Event.project_id == self.project_uuid
            )

            if event_types:
                base_stmt = base_stmt.where(Event.type.in_(event_types))

            # Count total matching events
            count_stmt = (
                select(func.count())
                .select_from(Event)
                .where(
                    Event.date_created >= cutoff_date,
                    Event.project_id == self.project_uuid,
                )
            )
            if event_types:
                count_stmt = count_stmt.where(Event.type.in_(event_types))

            count_result = session.execute(count_stmt)
            total_count = count_result.scalar_one()

            # Get paginated results
            offset = (page_index - 1) * page_size
            stmt = base_stmt.order_by(Event.date_created.desc()).offset(offset).limit(page_size)

            result = session.execute(stmt)
            events = result.scalars().all()

            return events, total_count

    async def get_paginated_events_async(
        self,
        page_index: int = 1,
        page_size: int = 20,
        event_types: list[str] | None = None,
        days_limit: int = 30,
    ) -> tuple[Sequence[Event], int]:
        """Get paginated events within a date range.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            page_index: Page number (1-indexed).
            page_size: Number of events per page.
            event_types: Optional list of event types to filter by.
            days_limit: Limit events to the last N days.

        Returns:
            Tuple of (list of events, total count).
        """
        return await asyncio.to_thread(
            self._get_paginated_events_sync,
            page_index,
            page_size,
            event_types,
            days_limit,
        )

    def _count_events_sync(
        self, event_types: list[str] | None = None, days_limit: int | None = None
    ) -> int:
        """Sync implementation: Count events, optionally filtered by type and date."""
        with self._session_scope(commit=False) as session:
            stmt = select(func.count()).select_from(Event)

            if days_limit:
                cutoff_date = datetime.now(UTC) - timedelta(days=days_limit)
                stmt = stmt.where(Event.date_created >= cutoff_date)

            if event_types:
                stmt = stmt.where(Event.type.in_(event_types))

            result = session.execute(stmt)
            return result.scalar_one()

    async def count_events_async(
        self, event_types: list[str] | None = None, days_limit: int | None = None
    ) -> int:
        """Count events, optionally filtered by type and date.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            event_types: Optional list of event types to filter by.
            days_limit: Optional limit to events from the last N days.

        Returns:
            The count of matching events.
        """
        return await asyncio.to_thread(self._count_events_sync, event_types, days_limit)

    def _delete_old_processed_events_sync(self, older_than_days: int = 30) -> int:
        """Sync implementation: Delete old processed events for cleanup."""
        with self._session_scope() as session:
            cutoff_date = datetime.now(UTC) - timedelta(days=older_than_days)

            stmt = (
                delete(Event)
                .where(Event.is_processed == True)  # noqa: E712
                .where(Event.date_processed < cutoff_date)
            )
            result = session.execute(stmt)
            rowcount = getattr(result, "rowcount", 0)
            return int(rowcount or 0)

    async def delete_old_processed_events_async(self, older_than_days: int = 30) -> int:
        """Delete old processed events for cleanup.

        Uses asyncio.to_thread() to run sync database operations.

        Args:
            older_than_days: Delete events processed more than this many days ago.

        Returns:
            Number of events deleted.
        """
        return await asyncio.to_thread(self._delete_old_processed_events_sync, older_than_days)
