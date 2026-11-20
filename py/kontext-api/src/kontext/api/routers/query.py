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
from typing import Any

from fastapi import APIRouter

from kontext.auth import QuerySessionPermissions
from kontext.common.messaging import IQueueClient
from kontext.schema import (
    ExecutionRunModel,
    ProjectFeature,
    QueryExecRequest,
    QueryResponse,
)

from ..dependencies import (
    QUEUE_CLIENT_DEP,
    AuthContext,
    create_auth_dependency,
)
from ..services.query_execution import (
    execute_query_async_service,
    execute_query_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Module-level dependency singletons to satisfy linters
# Uses permission-based authorization matching .NET backend
QUERY_EXECUTE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.DATALAKE],
    required_permissions=[QuerySessionPermissions.EXECUTE],
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
