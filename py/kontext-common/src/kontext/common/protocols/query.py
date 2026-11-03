"""Query session contracts."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from kontext.schema import QueryResponse, QuerySessionModel, QuerySessionStatus, TriggerActorModel


class IQuerySessionServiceProtocol(Protocol):
    """Protocol defining the interface for query session operations."""

    async def get_query_session(
        self, session_id: UUID | str, project_id: UUID | str
    ) -> QuerySessionModel | None: ...

    async def set_catalog_revision(self, session_id: UUID | str, revision: str | None) -> bool: ...

    async def create_query_session(
        self,
        project_id: UUID | str,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        default_entity_id: UUID | str | None = None,
        session_name: str | None = None,
        persistent: bool = True,
        engine_type: str | None = None,
    ) -> tuple[str, str | None]: ...

    async def close_query_session(self, session_id: UUID | str, project_id: UUID | str) -> bool: ...

    async def get_most_recent_active_session(
        self,
        project_id: UUID | str,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        engine_type: str | None = None,
    ) -> QuerySessionModel | None: ...

    async def get_or_create_session(
        self,
        project_id: UUID | str,
        session_id: UUID | str | None = None,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        default_entity_id: UUID | str | None = None,
        session_name: str | None = None,
        engine_type: str | None = None,
    ) -> str: ...

    async def execute_sql_with_session_management(
        self,
        project_id: UUID | str,
        sql_query: str,
        session_id: UUID | str | None = None,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        default_entity_id: UUID | str | None = None,
        query_timeout_seconds: int | None = None,
        triggered_by: TriggerActorModel | None = None,
        chat_session_id: UUID | str | None = None,
        parent_run_id: UUID | str | None = None,
        store_result_as_resource: bool = False,
        store_result_threshold_rows: int | None = None,
        store_result_name: str | None = None,
        engine_type: str | None = None,
    ) -> QueryResponse: ...

    async def update_query_session(
        self,
        session_id: UUID | str,
        project_id: UUID | str,
        session_name: str | None = None,
        status: QuerySessionStatus | None = None,
        metadata: str | None = None,
        database_size_bytes: int | None = None,
    ) -> QuerySessionModel | None: ...

    async def invalidate_sessions_for_catalog_connection(
        self,
        project_id: UUID | str,
        connection_id: UUID | str,
        *,
        reason: str = "Catalog structure changed",
    ) -> list[UUID]:
        """Soft-delete reusable sessions bound to *connection_id*.

        Called by workers after catalog-structure changes (ingest, cleanup)
        so stale DuckDB views are never reused. Returns the invalidated
        session IDs so callers can reclaim their session files.
        """
        ...
