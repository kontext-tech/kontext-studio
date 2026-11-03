"""Auth-aware runtime adapter over canonical query application services."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import cast
from uuid import UUID

from kontext.common.messaging import IQueueClient
from kontext.common.protocols import IQuerySessionServiceProtocol
from kontext.common.query.session_compatibility import (
    is_session_compatible,
    sort_sessions_by_preference,
)
from kontext.data import QuerySessionDataService
from kontext.schema import (
    CreateQuerySessionRequest,
    QueryEngineType,
    QueryExecRequest,
    QueryResponse,
    QuerySessionModel,
    QuerySessionStatus,
    SessionInitRequest,
    TriggerActorModel,
    UpdateQuerySessionRequest,
)

from .context import QueryAccessContext
from .execution import execute_query_sync
from .sessions import (
    create_query_session,
    delete_query_session,
    initialize_session_sync,
    update_query_session,
)


class AuthorizedRuntimeQuerySessionService(IQuerySessionServiceProtocol):
    """Runtime query-session service that reuses canonical backend logic."""

    def __init__(
        self,
        *,
        access_context: QueryAccessContext,
        queue_client: IQueueClient | None,
    ) -> None:
        self._access_context = access_context
        self._queue_client = queue_client
        self._data_service = QuerySessionDataService(str(access_context.project_id))

    def _validate_project_id(self, project_id: UUID | str) -> None:
        if str(project_id) != str(self._access_context.project_id):
            raise ValueError(
                f"Project ID mismatch: {project_id} != {self._access_context.project_id}"
            )

    def _with_resource(self, resource: QuerySessionModel | None) -> QueryAccessContext:
        return replace(self._access_context, resource=resource)

    def _owner_filter_for_lookup(self) -> str | None:
        if self._access_context.effective_owner_id:
            return str(self._access_context.effective_owner_id)
        return None

    def _reuse_owner_filter(self) -> str:
        return str(self._access_context.user_id)

    @staticmethod
    def _optional_str(value: UUID | str | None) -> str | None:
        return str(value) if value else None

    def _coerce_engine_type(
        self, engine_type: QueryEngineType | str | None
    ) -> QueryEngineType | None:
        if engine_type is None:
            return None
        if isinstance(engine_type, QueryEngineType):
            return engine_type
        return cast(QueryEngineType, QueryEngineType(str(engine_type)))

    async def _list_compatible_sessions(
        self,
        *,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        default_entity_id: UUID | str | None = None,
        engine_type: QueryEngineType | str | None = None,
        expected_catalog_revision: str | None = None,
    ) -> list[QuerySessionModel]:
        sessions, _ = await asyncio.to_thread(
            self._data_service.list_sessions_by_status,
            self._reuse_owner_filter(),
            [QuerySessionStatus.ACTIVE, QuerySessionStatus.INITIALIZING],
            self._optional_str(catalog_connection_id),
            default_namespace,
            1,
            100,
            False,
        )
        compatible_sessions = [
            candidate
            for candidate in sessions
            if is_session_compatible(
                candidate,
                catalog_connection_id=catalog_connection_id,
                default_namespace=default_namespace,
                default_entity_id=default_entity_id,
                engine_type=engine_type,
                expected_catalog_revision=expected_catalog_revision,
            )
        ]
        return sort_sessions_by_preference(compatible_sessions)

    async def _resolve_expected_catalog_revision(
        self,
        *,
        catalog_connection_id: UUID | str | None,
        session_id: UUID | str | None,
    ) -> str | None:
        connection_id = catalog_connection_id
        if connection_id is None and session_id:
            existing = await self.get_query_session(session_id, self._access_context.project_id)
            if existing is not None:
                connection_id = existing.catalog_connection_id
        if connection_id is None:
            return None
        return await self._data_service.get_catalog_revision_async(connection_id)

    async def get_query_session(
        self, session_id: UUID | str, project_id: UUID | str
    ) -> QuerySessionModel | None:
        self._validate_project_id(project_id)
        session = self._data_service.get_session(
            str(session_id),
            owner_id=self._owner_filter_for_lookup(),
        )
        return session

    async def set_catalog_revision(self, session_id: UUID | str, revision: str | None) -> bool:
        """Record the catalog revision a session materialized."""
        return await self._data_service.set_catalog_revision_async(session_id, revision)

    async def create_query_session(
        self,
        project_id: UUID | str,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        default_entity_id: UUID | str | None = None,
        session_name: str | None = None,
        persistent: bool = True,
        engine_type: str | None = None,
    ) -> tuple[str, str | None]:
        self._validate_project_id(project_id)
        session = await create_query_session(
            request=CreateQuerySessionRequest(
                project_id=str(project_id),
                catalog_connection_id=self._optional_str(catalog_connection_id),
                default_namespace=default_namespace,
                default_entity_id=self._optional_str(default_entity_id),
                session_name=session_name,
                is_persistent=persistent,
                engine_type=self._coerce_engine_type(engine_type),
            ),
            access_context=self._access_context,
        )
        return str(session.id), None

    async def close_query_session(self, session_id: UUID | str, project_id: UUID | str) -> bool:
        self._validate_project_id(project_id)
        resource = await self.get_query_session(session_id, project_id)
        if resource is None:
            return False

        await delete_query_session(
            session_id=UUID(str(session_id)),
            access_context=self._with_resource(resource),
            queue_client=self._queue_client,
        )
        return True

    async def get_most_recent_active_session(
        self,
        project_id: UUID | str,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        engine_type: str | None = None,
    ) -> QuerySessionModel | None:
        self._validate_project_id(project_id)
        ordered_sessions = await self._list_compatible_sessions(
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            engine_type=engine_type,
        )
        return ordered_sessions[0] if ordered_sessions else None

    async def get_or_create_session(
        self,
        project_id: UUID | str,
        session_id: UUID | str | None = None,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        default_entity_id: UUID | str | None = None,
        session_name: str | None = None,
        engine_type: str | None = None,
    ) -> str:
        self._validate_project_id(project_id)
        session = None
        expected_revision = await self._resolve_expected_catalog_revision(
            catalog_connection_id=catalog_connection_id, session_id=session_id
        )

        if session_id:
            explicit_session = await self.get_query_session(session_id, project_id)
            if explicit_session and is_session_compatible(
                explicit_session,
                expected_session_id=session_id,
                catalog_connection_id=catalog_connection_id,
                default_namespace=default_namespace,
                default_entity_id=default_entity_id,
                engine_type=engine_type,
                expected_catalog_revision=expected_revision,
            ):
                session = explicit_session

        if session is None:
            ordered_sessions = await self._list_compatible_sessions(
                catalog_connection_id=catalog_connection_id,
                default_namespace=default_namespace,
                default_entity_id=default_entity_id,
                engine_type=engine_type,
                expected_catalog_revision=expected_revision,
            )
            session = ordered_sessions[0] if ordered_sessions else None

        if session is None:
            session_id, _ = await self.create_query_session(
                project_id=project_id,
                catalog_connection_id=catalog_connection_id,
                default_namespace=default_namespace,
                default_entity_id=default_entity_id,
                session_name=session_name,
                persistent=True,
                engine_type=engine_type,
            )
            session = await self.get_query_session(session_id, project_id)

        if session is None:
            raise RuntimeError("Failed to create or resolve query session.")

        if session.status == QuerySessionStatus.ACTIVE:
            return str(session.id)

        init_response = await initialize_session_sync(
            request=SessionInitRequest(
                session_id=str(session.id),
                project_id=str(project_id),
                catalog_connection_id=self._optional_str(catalog_connection_id),
                default_namespace=default_namespace,
                default_entity_id=self._optional_str(default_entity_id),
                persistent=True,
            ),
            access_context=self._access_context,
            queue_client=self._queue_client,
        )
        if not init_response.success:
            raise RuntimeError(init_response.error_message or "Failed to initialize query session.")
        return str(session.id)

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
    ) -> QueryResponse:
        self._validate_project_id(project_id)
        effective_session_id = await self.get_or_create_session(
            project_id=project_id,
            session_id=session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            session_name="Agent Session",
            engine_type=engine_type,
        )
        return await execute_query_sync(
            request=QueryExecRequest(
                project_id=str(project_id),
                session_id=effective_session_id,
                sql_query=sql_query,
                query_timeout_seconds=query_timeout_seconds,
                triggered_by=triggered_by,
                chat_session_id=self._optional_str(chat_session_id),
                parent_run_id=self._optional_str(parent_run_id),
                store_result_as_resource=store_result_as_resource,
                store_result_threshold_rows=store_result_threshold_rows,
                store_result_name=store_result_name,
            ),
            access_context=self._access_context,
            queue_client=self._queue_client,
        )

    async def update_query_session(
        self,
        session_id: UUID | str,
        project_id: UUID | str,
        session_name: str | None = None,
        status: QuerySessionStatus | None = None,
        metadata: str | None = None,
        database_size_bytes: int | None = None,
    ) -> QuerySessionModel | None:
        self._validate_project_id(project_id)
        resource = await self.get_query_session(session_id, project_id)
        if resource is None:
            return None

        return update_query_session(
            session_id=UUID(str(session_id)),
            request=UpdateQuerySessionRequest(
                session_name=session_name,
                status=status,
                metadata=metadata,
                database_size_bytes=database_size_bytes,
            ),
            access_context=self._with_resource(resource),
        )

    async def invalidate_sessions_for_catalog_connection(
        self,
        project_id: UUID | str,
        connection_id: UUID | str,
        *,
        reason: str = "Catalog structure changed",
    ) -> list[UUID]:
        self._validate_project_id(project_id)
        return await self._data_service.invalidate_sessions_for_catalog_connection_async(
            connection_id,
            reason=reason,
        )
