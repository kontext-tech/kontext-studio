"""
Project Events API endpoints for listing project-level events.

These endpoints provide access to project-scoped events stored in SQLite databases.

Note: The response models (EventModel, PaginatedListOfEventModel) are imported
from kontext.schema, which are generated from the .NET OpenAPI spec. This ensures
consistency with the .NET API models and enables reuse of frontend components.

The Event model in project SQLite databases matches the .NET Event<TKey> structure,
allowing the same EventModel to be used for both platform events (SQL Server)
and project events (SQLite).
"""

import logging
from typing import Any

from fastapi import APIRouter, Query

from kontext.auth import EventPermissions
from kontext.project.events import list_project_events as list_project_events_impl
from kontext.schema import PaginatedListOfEventModel

from ..dependencies import (
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_QUERY,
    AuthContext,
    create_auth_dependency,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Authorization Dependencies
# =============================================================================

EVENTS_READ_AUTH = create_auth_dependency(required_permissions=[EventPermissions.READ])


# =============================================================================
# Event Endpoints
# =============================================================================


@router.get("", response_model=PaginatedListOfEventModel, operation_id="ListProjectEvents")
async def list_project_events(
    project_id: PROJECT_ID_QUERY,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    event_types: str | None = Query(
        None, alias="eventTypes", description="Comma-separated list of event types to filter"
    ),
    days_limit: int = Query(
        30, alias="daysLimit", ge=1, le=365, description="Limit events to the last N days"
    ),
    auth_context: AuthContext[Any] = EVENTS_READ_AUTH,
) -> PaginatedListOfEventModel:
    """
    List events for a project with pagination.

    Returns paginated list of events within the specified date range.
    The project_id query parameter is required for authorization.
    """
    return await list_project_events_impl(
        project_id=auth_context.project_id,
        page_index=page_index,
        page_size=page_size,
        event_types=event_types,
        days_limit=days_limit,
    )
