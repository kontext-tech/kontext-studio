"""Query orchestration package for query execution and session workflows."""

from .context import QueryAccessContext
from .engine_factory import resolve_engine_for_session
from .errors import QueryServiceError
from .execution import (
    execute_query_async,
    execute_query_sync,
    get_session_query_history,
)
from .in_process_query_session_service import InProcessQuerySessionService
from .sessions import (
    create_query_session,
    delete_query_session,
    get_query_session_resource,
    initialize_session_async,
    initialize_session_sync,
    list_query_sessions,
    update_query_session,
)
from .sql_validator import (
    SqlValidator,
    get_project_schema_info,
    validate_sql_for_project,
)

__all__ = [
    "InProcessQuerySessionService",
    "QueryAccessContext",
    "QueryServiceError",
    "SqlValidator",
    "create_query_session",
    "delete_query_session",
    "execute_query_async",
    "execute_query_sync",
    "get_project_schema_info",
    "get_query_session_resource",
    "get_session_query_history",
    "initialize_session_async",
    "initialize_session_sync",
    "list_query_sessions",
    "resolve_engine_for_session",
    "update_query_session",
    "validate_sql_for_project",
]
