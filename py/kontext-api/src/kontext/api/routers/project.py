"""
Project API endpoints for project statistics and metadata.

These endpoints provide project-level operations and statistics.
"""

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter

from kontext.auth import ProjectPermissions
from kontext.project.stats import get_project_stats as get_project_stats_impl
from kontext.schema import ProjectStatsModel

from ..dependencies import PROJECT_ID_PATH, AuthContext, create_auth_dependency

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Authorization Dependencies
# =============================================================================

PROJECT_READ_AUTH = create_auth_dependency(required_permissions=[ProjectPermissions.READ])

# =============================================================================
# Project Endpoints
# =============================================================================


@router.get(
    "/{projectId}/stats",
    response_model=ProjectStatsModel,
    summary="Get project statistics",
    description=(
        "Get file and job statistics for a project including file count, "
        "total size, and job run duration."
    ),
)
async def get_project_stats(
    project_id: Annotated[UUID, PROJECT_ID_PATH], _: AuthContext[Any] = PROJECT_READ_AUTH
) -> ProjectStatsModel:
    """
    Get project statistics.

    Returns file count, total size in bytes, and total job run duration in milliseconds
    for all completed job runs in the project.
    """
    return await get_project_stats_impl(project_id)
