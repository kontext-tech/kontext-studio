"""
Project management API endpoints.

Provides CRUD operations for local projects backed by SQLite. The read-only
host project boundary is implemented under /host/projects*.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends

from kontext.account import UserProfile
from kontext.project import (
    create_project_service,
    delete_project_service,
    get_filtered_projects_service,
    get_project_by_code_service,
    get_project_service,
    update_project_service,
)
from kontext.schema import (
    CreateProjectRequest,
    PaginatedListOfProjectModel,
    ProjectModel,
    UpdateProjectRequest,
)

from ..dependencies import (
    FILTER_QUERY,
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_PATH,
)
from ..dependencies.local_auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/project", tags=["Projects"])


@router.get("/foundation-models")
def get_foundation_models() -> list[dict[str, Any]]:
    """Return available LLM foundation models."""
    from kontext.llm import LanguageModelService

    svc = LanguageModelService()
    models = svc.list_model_definitions()
    return [m.model_dump(by_alias=True) for m in models]


@router.get("/code/{code}")
def get_project_by_code(code: str) -> ProjectModel:
    """Look up a project by its unique code."""
    return get_project_by_code_service(code)


@router.get("/filtered")
def get_filtered_projects(
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    filter: FILTER_QUERY = None,
) -> PaginatedListOfProjectModel:
    """List projects with optional text filter and pagination."""
    return get_filtered_projects_service(
        page_index=page_index,
        page_size=page_size,
        filter_string=filter,
    )


@router.post("")
def create_project(
    request: CreateProjectRequest,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> ProjectModel:
    """Create a new local project."""
    result = create_project_service(request, current_user)
    logger.info("Created local project '%s' (%s)", request.project_name, result.id)
    return result


@router.get("/{projectId}")
def get_project(project_id: Annotated[str, PROJECT_ID_PATH]) -> ProjectModel:
    """Get a project by ID."""
    return get_project_service(project_id)


@router.put("/{projectId}")
def update_project(
    project_id: Annotated[str, PROJECT_ID_PATH],
    request: UpdateProjectRequest,
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> ProjectModel:
    """Update project metadata."""
    return update_project_service(project_id, request, current_user)


@router.delete("/{projectId}")
def delete_project(
    project_id: Annotated[str, PROJECT_ID_PATH],
    current_user: Annotated[UserProfile, Depends(get_current_user)],
) -> dict[str, str]:
    """Soft-delete a project."""
    _ = current_user
    return delete_project_service(project_id)
