"""
Data API endpoints for query execution.

Uses queue-based job dispatch for query execution. Synchronous execution polls
for completion; asynchronous execution returns the execution run immediately.

TODO: Result Storage Size Limits
Currently, query results are stored in the job run's result_data column when
store_result_as_resource is False (default). This may exceed database column
size limits for large result sets. Future improvements:
1. Implement automatic threshold-based storage (e.g., >500KB → resource file)
2. Add configurable size limits per project/tenant
3. Consider compression for result data
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException

from kontext.auth import QuerySessionPermissions
from kontext.common.messaging import IQueueClient
from kontext.schema import (
    ExecutionRunModel,
    ProjectFeature,
    QueryExecRequest,
    QueryResponse,
)

from ..dependencies import (
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_QUERY,
    QUEUE_CLIENT_DEP,
    SESSION_ID_PATH,
    AuthContext,
    create_auth_dependency,
)
from ..services.query_execution import (
    execute_query_async_service,
    execute_query_service,
    get_session_query_history_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Module-level dependency singletons to satisfy linters
# Uses permission-based authorization matching .NET backend
QUERY_EXECUTE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.DATALAKE],
    required_permissions=[QuerySessionPermissions.EXECUTE],
)
QUERY_READ_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.DATALAKE],
    required_permissions=[QuerySessionPermissions.READ],
)


@router.post("/execute", response_model=QueryResponse, operation_id="ExecuteQuery")
async def execute_query(
    request: QueryExecRequest,
    auth_context: AuthContext[Any] = QUERY_EXECUTE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> QueryResponse:
    """
    Execute a query in a DuckDB session.

    This endpoint dispatches query execution to the job worker queue and polls
    for completion. The query is executed within a DuckDB session with proper
    authentication and authorization.

    The endpoint is synchronous for backward compatibility - it waits for the
    query to complete before returning. For long-running queries, consider
    the async execution pattern (future enhancement).
    """
    return await execute_query_service(
        request=request,
        auth_context=auth_context,
        queue_client=queue_client,
    )


@router.post(
    "/execute-async",
    response_model=ExecutionRunModel,
    status_code=202,
    operation_id="ExecuteQueryAsync",
)
async def execute_query_async(
    request: QueryExecRequest,
    auth_context: AuthContext[Any] = QUERY_EXECUTE_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> ExecutionRunModel:
    return await execute_query_async_service(
        request=request,
        auth_context=auth_context,
        queue_client=queue_client,
    )


@router.get("/sessions/{sessionId}/history", operation_id="GetSessionQueryHistory")
def get_session_query_history(
    session_id: Annotated[str, SESSION_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[Any] = QUERY_READ_AUTH,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
):
    """
    Get query execution history for a session.

    Returns a list of all queries executed in the specified session,
    with pagination support. The project_id query parameter is required
    for authorization.

    Declared sync so FastAPI runs the blocking history lookup in its
    threadpool instead of blocking the event loop.
    """
    _ = project_id  # Used for OpenAPI parameter generation and authorization
    if not auth_context.project:
        raise HTTPException(status_code=400, detail="Project context required")
    return get_session_query_history_service(
        project_id=str(auth_context.project.id),
        session_id=session_id,
        page_index=page_index,
        page_size=page_size,
    )
