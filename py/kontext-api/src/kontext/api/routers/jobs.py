"""Project Job API endpoints for job management.

These endpoints manage jobs associated with projects.
Uses refactored data services that return view models.
"""

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from kontext.auth import JobPermissions
from kontext.execution.job_management import (
    create_job_service,
    delete_job_service,
    get_job_service,
    get_job_type_service,
    list_job_types_service,
    list_jobs_service,
    schedule_job_service,
    update_job_service,
)
from kontext.execution.job_management import (
    get_job_resource_service as load_job_resource,
)
from kontext.schema import (
    CreateJobRequest,
    ExecuteJobNowRequest,
    JobModel,
    JobRunModel,
    PaginatedListOfJobModel,
    UnifiedJobTypeModel,
    UpdateJobRequest,
)

from ..dependencies import (
    JOB_ID_PATH,
    JOB_TYPE_PATH,
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_QUERY,
    AuthContext,
    create_auth_dependency,
    extract_path_param,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Authorization Dependencies
# =============================================================================


async def get_job_resource(
    request: Request, auth_context: AuthContext[JobModel]
) -> JobModel | None:
    """Resource getter for job ownership checks."""
    job_id = extract_path_param(request, "job_id")
    if not job_id:
        return None
    return await load_job_resource(job_id=UUID(str(job_id)), auth_context=auth_context)


JOB_CREATE_AUTH = create_auth_dependency(required_permissions=[JobPermissions.CREATE])
JOB_READ_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.READ],
    resource_getter=get_job_resource,
    allow_owner=True,
)
JOB_UPDATE_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.UPDATE],
    resource_getter=get_job_resource,
    allow_owner=True,
)
JOB_DELETE_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.DELETE],
    resource_getter=get_job_resource,
    allow_owner=True,
)
JOB_EXECUTE_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.EXECUTE],
    resource_getter=get_job_resource,
    allow_owner=True,
)

# Query parameters
FILTER_QUERY: str | None = Query(None, alias="filterString", description="Filter by name")
IS_ENABLED_QUERY: bool | None = Query(
    None, alias="isEnabled", description="Filter by enabled status"
)


# =============================================================================
# Job Endpoints
# =============================================================================


@router.get("", response_model=PaginatedListOfJobModel, operation_id="ListProjectJobs")
async def list_jobs(
    project_id: PROJECT_ID_QUERY,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    filter_string: str | None = FILTER_QUERY,
    is_enabled: bool | None = IS_ENABLED_QUERY,
    auth_context: AuthContext[Any] = JOB_READ_AUTH,
) -> PaginatedListOfJobModel:
    """List jobs for a project with pagination."""
    return await list_jobs_service(
        project_id=project_id,
        page_index=page_index,
        page_size=page_size,
        is_enabled=is_enabled,
        auth_context=auth_context,
    )


@router.get(
    "/types",
    response_model=list[UnifiedJobTypeModel],
    operation_id="GetProjectJobTypes",
)
def get_job_types(
    project_id: PROJECT_ID_QUERY, auth_context: AuthContext[Any] = JOB_READ_AUTH
) -> list[UnifiedJobTypeModel]:
    """Get available job types from the Python job registry."""
    _ = project_id  # Used for authorization
    return list_job_types_service()


@router.get(
    "/types/{jobType:path}",
    response_model=UnifiedJobTypeModel,
    operation_id="GetProjectJobType",
)
def get_job_type(
    job_type: Annotated[str, JOB_TYPE_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = JOB_READ_AUTH,
) -> UnifiedJobTypeModel:
    """Get details for a specific job type."""
    _ = project_id  # Used for authorization
    return get_job_type_service(job_type)


@router.get("/{jobId}", response_model=JobModel, operation_id="GetProjectJob")
async def get_job(
    job_id: Annotated[UUID, JOB_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[JobModel] = JOB_READ_AUTH,
) -> JobModel:
    """Get a specific job by ID."""
    _ = project_id  # Used for authorization
    if not auth_context.resource:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return await get_job_service(job_id=job_id, auth_context=auth_context)


@router.post("", response_model=JobModel, status_code=201, operation_id="CreateProjectJob")
async def create_job(
    request: CreateJobRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = JOB_CREATE_AUTH,
) -> JobModel:
    """Create a new job."""
    return await create_job_service(
        request=request,
        project_id=project_id,
        auth_context=auth_context,
    )


@router.put("/{jobId}", response_model=JobModel, operation_id="UpdateProjectJob")
async def update_job(
    job_id: Annotated[UUID, JOB_ID_PATH],
    request: UpdateJobRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[JobModel] = JOB_UPDATE_AUTH,
) -> JobModel:
    """Update a job."""
    _ = project_id  # Used for authorization
    if not auth_context.resource:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return await update_job_service(
        job_id=job_id,
        request=request,
        auth_context=auth_context,
    )


@router.delete("/{jobId}", status_code=204, operation_id="DeleteProjectJob")
async def delete_job(
    job_id: Annotated[UUID, JOB_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[JobModel] = JOB_DELETE_AUTH,
) -> None:
    """Soft delete a job."""
    _ = project_id  # Used for authorization
    if not auth_context.resource:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    await delete_job_service(job_id=job_id, auth_context=auth_context)


@router.post(
    "/{jobId}/schedule",
    response_model=JobRunModel,
    status_code=201,
    operation_id="ScheduleProjectJob",
)
async def schedule_job(
    job_id: Annotated[UUID, JOB_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    request: ExecuteJobNowRequest | None = None,
    auth_context: AuthContext[JobModel] = JOB_EXECUTE_AUTH,
) -> JobRunModel:
    """Manually schedule a job for execution."""
    _ = project_id  # Used for authorization
    if not auth_context.resource:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    try:
        return await schedule_job_service(
            job_id=job_id,
            request=request,
            project_id=project_id,
            auth_context=auth_context,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
