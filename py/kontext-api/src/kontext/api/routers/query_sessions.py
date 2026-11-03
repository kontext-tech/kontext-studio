"""Data API endpoints for session management."""

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from kontext.auth import QuerySessionPermissions
from kontext.common.messaging import IQueueClient
from kontext.schema import (
    CreateQuerySessionRequest,
    ExecutionRunModel,
    PaginatedListOfQuerySessionModel,
    ProjectFeature,
    QuerySessionModel,
    SessionInitRequest,
    SessionInitResponse,
    UpdateQuerySessionRequest,
)

from ..dependencies import (
    MY_OWNED_ONLY_QUERY,
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_QUERY,
    QUEUE_CLIENT_DEP,
    SESSION_ID_PATH,
    AuthContext,
    create_auth_dependency,
)
from ..services.query_sessions import (
    create_query_session_service,
    delete_query_session_service,
    get_query_session_resource_service,
    initialize_session_async_service,
    initialize_session_service,
    list_query_sessions_service,
    update_query_session_service,
)

logger = logging.getLogger(__name__)


async def get_query_session_resource(
    request: Request, auth_context: AuthContext[QuerySessionModel]
) -> QuerySessionModel | None:
    """Helper to fetch query session for authorization dependency."""
    return await get_query_session_resource_service(request, auth_context)


router = APIRouter()

# Module-level dependency singletons to satisfy linters
# Uses permission-based authorization matching .NET backend
SESSION_CREATE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.DATALAKE],
    required_permissions=[QuerySessionPermissions.CREATE],
)
SESSION_READ_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.DATALAKE],
    required_permissions=[QuerySessionPermissions.READ],
    resource_getter=get_query_session_resource,
    allow_owner=True,
)
SESSION_UPDATE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.DATALAKE],
    required_permissions=[QuerySessionPermissions.UPDATE],
    resource_getter=get_query_session_resource,
    allow_owner=True,
)
SESSION_DELETE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.DATALAKE],
    required_permissions=[QuerySessionPermissions.DELETE],
    resource_getter=get_query_session_resource,
    allow_owner=True,
)
SESSION_EXECUTE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.DATALAKE],
    required_permissions=[QuerySessionPermissions.EXECUTE],
)


@router.post(
    "",
    response_model=QuerySessionModel,
    operation_id="CreateQuerySession",
    status_code=201,
)
async def create_query_session(
    request: CreateQuerySessionRequest,
    auth_context: AuthContext[Any] = SESSION_CREATE_AUTH,
) -> QuerySessionModel:
    """
    Create a new query session in the database.

    This creates the session record with INITIALIZING status.
    Call /init endpoint afterwards to initialize the DuckDB session.
    """
    logger.info(
        f"Creating query session for project {request.project_id}, "
        f"catalog {request.catalog_connection_id or 'auto'}"
    )
    session = await create_query_session_service(
        request=request,
        auth_context=auth_context,
    )
    logger.info("Created query session %s with status INITIALIZING", session.id)
    return session


@router.post("/init", response_model=SessionInitResponse, operation_id="InitializeSession")
async def initialize_session(
    request: SessionInitRequest,
    auth_context: AuthContext[Any] = SESSION_EXECUTE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> SessionInitResponse:
    """
    Initialize a query session and wait for the initialization job to finish.

    This endpoint dispatches an InitializeSessionJob to the Python worker queue,
    then blocks until the job completes or the wait times out. The job creates
    the DuckDB session, loads catalog metadata, creates storage connections,
    and sets up external tables for data querying.

    Returns a SessionInitResponse containing the updated session when
    initialization succeeds. A job_run_id may also be returned for traceability.
    If the initialization times out or fails, the response includes an
    error_message describing the outcome.
    """
    return await initialize_session_service(
        request=request,
        auth_context=auth_context,
        queue_client=queue_client,
    )


@router.post(
    "/init-async",
    response_model=ExecutionRunModel,
    status_code=202,
    operation_id="InitializeSessionAsync",
)
async def initialize_session_async(
    request: SessionInitRequest,
    auth_context: AuthContext[Any] = SESSION_EXECUTE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> ExecutionRunModel:
    return await initialize_session_async_service(
        request=request,
        auth_context=auth_context,
        queue_client=queue_client,
    )


@router.get(
    "",
    response_model=PaginatedListOfQuerySessionModel,
    operation_id="ListQuerySessions",
)
def list_query_sessions(
    project_id: PROJECT_ID_QUERY,
    my_sessions_only: MY_OWNED_ONLY_QUERY = False,
    auth_context: AuthContext[Any] = SESSION_READ_AUTH,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
) -> PaginatedListOfQuerySessionModel:
    """
    List query sessions for the authorized project.

    Optional parameters:
    - my_sessions_only: If true, returns only the current user's sessions.
    """
    # Note:
    # project_id is used by require_project_authorization to set auth_context.project
    # The query_session_data_service is already scoped to the project via auth_context
    _ = project_id  # Used for OpenAPI parameter generation and authorization
    return list_query_sessions_service(
        auth_context=auth_context,
        my_sessions_only=my_sessions_only,
        page_index=page_index,
        page_size=page_size,
    )


@router.get("/{sessionId}", response_model=QuerySessionModel, operation_id="GetQuerySession")
def get_query_session(
    session_id: Annotated[UUID, SESSION_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[QuerySessionModel] = SESSION_READ_AUTH,
) -> QuerySessionModel:
    """
    Get a specific query session by ID.

    Returns detailed information about a single query session.
    The project_id query parameter is required for authorization.
    """
    _ = project_id  # Used for OpenAPI parameter generation and authorization
    if not auth_context.resource:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return auth_context.resource


@router.patch("/{sessionId}", response_model=QuerySessionModel, operation_id="UpdateQuerySession")
def update_query_session(
    session_id: Annotated[UUID, SESSION_ID_PATH],
    request: UpdateQuerySessionRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[QuerySessionModel] = SESSION_UPDATE_AUTH,
) -> QuerySessionModel:
    """
    Update a query session.

    Allows updating session properties like name, status, and metadata.
    The project_id query parameter is required for authorization.

    Users can only update their own sessions (user-level isolation).
    Administrators can update any session, including changing status to Closed.
    """
    _ = project_id  # Used for OpenAPI parameter generation and authorization
    return update_query_session_service(
        session_id=session_id,
        request=request,
        auth_context=auth_context,
    )


@router.delete("/{sessionId}", status_code=204, operation_id="DeleteQuerySession")
async def delete_query_session(
    session_id: Annotated[UUID, SESSION_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[QuerySessionModel] = SESSION_DELETE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> None:
    """
    Delete a query session.

    Permanently removes a query session and dispatches an async job to delete
    the associated database file. The project_id query parameter is required
    for authorization.

    Users can only delete their own sessions (user-level isolation).
    """
    await delete_query_session_service(
        session_id=session_id,
        project_id=project_id,
        auth_context=auth_context,
        queue_client=queue_client,
    )
