"""Data access layer for Kontext Core.

This module provides database utilities and models for project-scoped data.
"""

from kontext.common.pagination import PaginatedResult

from .agent_run_state_service import AgentRunStateDataService
from .base_service import ensure_uuid, parse_uuid, uuid_to_str
from .catalog_service import CatalogDataService, CatalogEntitySnapshot
from .chat_session_service import (
    ChatSessionDataService,
    ChatSessionNotFoundError,
)
from .chat_session_token_usage_service import ChatSessionTokenUsageDataService
from .converters import (
    JobConverter,
    JobRunConverter,
    JobRunLogConverter,
    JobTriggerConverter,
)
from .database import (
    Base,
    check_database_connectivity,
    get_db,
    get_engine,
    get_session_factory,
    get_sync_db_session,
    get_sync_session_for_project,
)
from .event_service import EventDataService
from .execution_run_context_service import ExecutionRunContextDataService
from .file_service import FileDataService
from .job_run_log_service import JobRunLogDataService
from .job_run_service import JobRunDataService
from .job_service import JobDataService
from .job_trigger_service import JobTriggerDataService
from .models import (
    CatalogColumnRecord,
    CatalogConnection,
    CatalogEntity,
    CatalogNamespace,
    CatalogSourceLink,
    CatalogSyncState,
    ChatSession,
    ChatSessionAttachmentContext,
    ChatSessionTokenUsage,
    Event,
    ExecutionRunContext,
    Job,
    JobRun,
    JobRunLog,
    JobTrigger,
    ProjectFile,
    Query,
    QuerySession,
)
from .query_service import QueryHistoryDataService
from .query_session_service import QuerySessionDataService, QuerySessionNotFoundError
from .types import FileStats

__all__ = [
    "AgentRunStateDataService",
    "Base",
    "CatalogColumnRecord",
    "CatalogConnection",
    "CatalogDataService",
    "CatalogEntity",
    "CatalogEntitySnapshot",
    "CatalogNamespace",
    "CatalogSourceLink",
    "CatalogSyncState",
    "ChatSession",
    "ChatSessionAttachmentContext",
    "ChatSessionDataService",
    "ChatSessionNotFoundError",
    "ChatSessionTokenUsage",
    "ChatSessionTokenUsageDataService",
    "Event",
    "EventDataService",
    "ExecutionRunContext",
    "ExecutionRunContextDataService",
    "FileDataService",
    "FileStats",
    "Job",
    "JobConverter",
    "JobDataService",
    "JobRun",
    "JobRunConverter",
    "JobRunDataService",
    "JobRunLog",
    "JobRunLogConverter",
    "JobRunLogDataService",
    "JobTrigger",
    "JobTriggerConverter",
    "JobTriggerDataService",
    "PaginatedResult",
    "ProjectFile",
    "Query",
    "QueryHistoryDataService",
    "QuerySession",
    "QuerySessionDataService",
    "QuerySessionNotFoundError",
    "check_database_connectivity",
    "ensure_uuid",
    "get_db",
    "get_engine",
    "get_session_factory",
    "get_sync_db_session",
    "get_sync_session_for_project",
    "parse_uuid",
    "uuid_to_str",
]
