"""Project event queries."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from kontext.common.utils.datetime_utils import normalize_datetime_utc
from kontext.data import EventDataService
from kontext.schema import ChannelType, EventModel, EventType, PaginatedListOfEventModel


async def list_project_events(
    *,
    project_id: UUID,
    page_index: int,
    page_size: int,
    event_types: str | None,
    days_limit: int,
) -> PaginatedListOfEventModel:
    service = EventDataService(project_id)

    event_types_list: list[str] | None = None
    if event_types:
        event_types_list = [et.strip() for et in event_types.split(",") if et.strip()]

    events, total_count = await service.get_paginated_events_async(
        page_index=page_index,
        page_size=page_size,
        event_types=event_types_list,
        days_limit=days_limit,
    )

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    event_models = [
        EventModel(
            id=str(event.id),
            type=EventType(event.type),
            title=event.title,
            content=event.content,
            user_id=str(event.user_id) if event.user_id else None,
            project_id=str(event.project_id) if event.project_id else None,
            content_id=str(event.content_id) if event.content_id else None,
            channel_type=(
                ChannelType(event.channel_type) if event.channel_type else ChannelType.OTHER
            ),
            ip_address=event.ip_address,
            path=event.path,
            date_created=(normalize_datetime_utc(event.date_created) or datetime.now(UTC)),
        )
        for event in events
    ]

    return PaginatedListOfEventModel(
        items=event_models,
        total_count=total_count,
        page_index=page_index,
        page_size=page_size,
        total_pages=total_pages,
    )
