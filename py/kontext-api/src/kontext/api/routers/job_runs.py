"""Project Job Run API endpoints for job run management.

These endpoints manage job runs associated with projects.
"""

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from kontext.auth import JobPermissions
from kontext.common.messaging import IQueueClient
from kontext.execution.job_management import (
    get_job_resource_service as get_job_resource,
)
from kontext.execution.job_run_management import (
    add_job_run_log_service,
    get_job_run_logs_service,
    get_job_run_service,
    list_job_runs_service,
    reset_job_runs_service,
    update_job_run_progress_service,
    update_job_run_status_service,
    update_job_run_worker_service,
)
from kontext.execution.job_run_management import (
    get_job_run_resource_service as get_job_run_resource,
)
from kontext.schema import (
    AddJobRunLogRequest,
    JobModel,
    JobResetResponse,
    JobRunLogModel,
    JobRunModel,
    PaginatedListOfJobRunModel,
    ResetJobRunsRequest,
    UpdateJobRunProgressRequest,
    UpdateJobRunStatusRequest,
    UpdateJobRunWorkerRequest,
)

from ..dependencies import (
    JOB_ID_PATH,
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_QUERY,
    QUEUE_CLIENT_DEP,
    RUN_ID_PATH,
    AuthContext,
    create_auth_dependency,
    extract_path_param,
    get_queue_client,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Authorization Dependencies
# =============================================================================


async def get_job_resource_for_auth(
    request: Request, auth_context: AuthContext[JobModel]
) -> JobModel | None:
    """Resource getter for job ownership checks."""
    job_id = extract_path_param(request, "job_id")
    if not job_id:
        return None
    return await get_job_resource(job_id=UUID(str(job_id)), auth_context=auth_context)


async def get_job_run_resource_for_auth(
    request: Request, auth_context: AuthContext[JobRunModel]
) -> JobRunModel | None:
    """Resource getter for job-run ownership checks."""
    run_id = extract_path_param(request, "run_id")
    if not run_id:
        return None
    return await get_job_run_resource(run_id=UUID(str(run_id)), auth_context=auth_context)


JOB_READ_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.READ],
    resource_getter=get_job_resource_for_auth,
    allow_owner=True,
)

JOB_WRITE_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.UPDATE],
    resource_getter=get_job_resource_for_auth,
    allow_owner=True,
)

JOB_RUN_READ_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.READ],
    resource_getter=get_job_run_resource_for_auth,
    allow_owner=True,
)

JOB_RUN_WRITE_AUTH = create_auth_dependency(
    required_permissions=[JobPermissions.UPDATE],
    resource_getter=get_job_run_resource_for_auth,
    allow_owner=True,
)

# Query parameters
JOB_ID_QUERY: UUID | None = Query(None, alias="jobId", description="Filter by job ID")
STATUS_QUERY: str | None = Query(None, alias="status", description="Filter by status")


# =============================================================================
# Job Run Endpoints
# =============================================================================


@router.get("", response_model=PaginatedListOfJobRunModel, operation_id="ListProjectJobRuns")
async def list_job_runs(
    project_id: PROJECT_ID_QUERY,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    job_id: UUID | None = JOB_ID_QUERY,
    status: str | None = STATUS_QUERY,
    auth_context: AuthContext[Any] = JOB_READ_AUTH,
) -> PaginatedListOfJobRunModel:
    """List job runs for a project with pagination."""
    return await list_job_runs_service(
        project_id=project_id,
        page_index=page_index,
        page_size=page_size,
        job_id=job_id,
        status=status,
        auth_context=auth_context,
    )


@router.get("/{runId}", response_model=JobRunModel, operation_id="GetProjectJobRun")
def get_job_run(
    run_id: Annotated[UUID, RUN_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[JobRunModel] = JOB_RUN_READ_AUTH,
) -> JobRunModel:
    """Get a specific job run by ID."""
    _ = project_id  # Used for authorization
    return get_job_run_service(run_id=run_id, auth_context=auth_context)


@router.get(
    "/{runId}/logs",
    response_model=list[JobRunLogModel],
    operation_id="GetProjectJobRunLogs",
)
async def get_job_run_logs(
    run_id: Annotated[UUID, RUN_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum logs to return"),
    auth_context: AuthContext[JobRunModel] = JOB_RUN_READ_AUTH,
) -> list[JobRunLogModel]:
    """Get logs for a specific job run."""
    _ = project_id  # Used for authorization
    return await get_job_run_logs_service(
        run_id=run_id,
        limit=limit,
        auth_context=auth_context,
    )


@router.get(
    "/job/{jobId}",
    response_model=PaginatedListOfJobRunModel,
    operation_id="ListJobRunsForJob",
)
async def list_runs_for_job(
    job_id: Annotated[UUID, JOB_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    status: str | None = STATUS_QUERY,
    auth_context: AuthContext[JobModel] = JOB_READ_AUTH,
) -> PaginatedListOfJobRunModel:
    """List job runs for a specific job."""
    return await list_job_runs_service(
        project_id=project_id,
        page_index=page_index,
        page_size=page_size,
        job_id=job_id,
        status=status,
        auth_context=auth_context,
    )


# =============================================================================
# Job Run Update Endpoints (for SDK client operations)
# =============================================================================


@router.put("/{runId}/status", response_model=None, operation_id="UpdateJobRunStatus")
async def update_job_run_status(
    run_id: Annotated[UUID, RUN_ID_PATH],
    request: UpdateJobRunStatusRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[JobRunModel] = JOB_RUN_WRITE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> None:
    """Update job run status.

    Used by remote workers to update job run status via the SDK.
    """
    _ = project_id  # Used for authorization
    await update_job_run_status_service(
        run_id=run_id,
        request=request,
        auth_context=auth_context,
        queue_client=queue_client,
    )


@router.put("/{runId}/progress", response_model=None, operation_id="UpdateJobRunProgress")
async def update_job_run_progress(
    run_id: Annotated[UUID, RUN_ID_PATH],
    request: UpdateJobRunProgressRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[JobRunModel] = JOB_RUN_WRITE_AUTH,
) -> None:
    """Update job run progress.

    Used by remote workers to update job run progress via the SDK.
    """
    _ = project_id  # Used for authorization
    await update_job_run_progress_service(
        run_id=run_id,
        request=request,
        auth_context=auth_context,
    )


@router.put("/{runId}/worker", response_model=None, operation_id="UpdateJobRunWorker")
async def update_job_run_worker(
    run_id: Annotated[UUID, RUN_ID_PATH],
    request: UpdateJobRunWorkerRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[JobRunModel] = JOB_RUN_WRITE_AUTH,
) -> None:
    """Update job run worker identifier.

    Used by remote workers to assign themselves to a job run via the SDK.
    """
    _ = project_id  # Used for authorization
    await update_job_run_worker_service(
        run_id=run_id,
        request=request,
        auth_context=auth_context,
    )


@router.post("/{runId}/logs", response_model=None, status_code=201, operation_id="AddJobRunLog")
async def add_job_run_log(
    run_id: Annotated[UUID, RUN_ID_PATH],
    request: AddJobRunLogRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[JobRunModel] = JOB_RUN_WRITE_AUTH,
) -> None:
    """Add a log entry to a job run.

    Used by remote workers to add logs to a job run via the SDK.
    """
    _ = project_id  # Used for authorization
    await add_job_run_log_service(
        run_id=run_id,
        request=request,
        auth_context=auth_context,
    )


# =============================================================================
# Job Run Reset Endpoints
# =============================================================================


@router.post("/reset", response_model=JobResetResponse, operation_id="ResetProjectJobRuns")
async def reset_job_runs(
    request: ResetJobRunsRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = JOB_WRITE_AUTH,
) -> JobResetResponse:
    """Reset job runs back to queued status for retry.

    Only job runs in certain statuses (Failed, Canceled, TimedOut,
    DeadLettered, Running, Dispatched) can be reset.

    After resetting to Queued status, the job runs are automatically
    dispatched to the execution queue for pickup by the worker.
    """

    queue_client = await get_queue_client()
    return await reset_job_runs_service(
        request=request,
        project_id=project_id,
        auth_context=auth_context,
        queue_client=queue_client,
    )
