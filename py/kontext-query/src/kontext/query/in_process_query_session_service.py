"""In-process query-session adapter.

This is the local/direct-access implementation of
:class:`~kontext.common.protocols.IQuerySessionServiceProtocol`. It lives in
``kontext-query`` (the orchestration layer) rather than ``kontext-engine`` so
that the engine package stays pure compute: the engine depends only on the
``QueryExecutionEngine`` port and orchestration depends on the engine resolver,
never the other way around.

A future cloud deployment can provide a different
``IQuerySessionServiceProtocol`` implementation (for example one backed by a
remote query service) without touching either layer.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import cast
from uuid import UUID

from kontext.common.artifacts.provenance import build_data_identity_key
from kontext.common.catalog.connector_specs import resolve_query_engine_type_for_connection
from kontext.common.constants import QueryConstants
from kontext.common.protocols import (
    IQuerySessionServiceProtocol,
    RuntimeProviderProtocol,
)
from kontext.common.query.engine import QueryEngineRequest
from kontext.common.query.result_materialization import should_persist_result
from kontext.common.query.session_compatibility import (
    is_session_compatible,
    sort_sessions_by_preference,
)
from kontext.common.query.session_locks import session_execution_lock
from kontext.common.query.session_storage import (
    delete_session_database_file,
    get_session_database_path,
)
from kontext.common.utils.enum_utils import safe_enum_conversion
from kontext.schema import (
    ArtifactOrigin,
    ArtifactProvenance,
    CreateQuerySessionRequest,
    QueryEngineType,
    QueryResponse,
    QuerySessionModel,
    QuerySessionStatus,
    TriggerActorModel,
)

from .engine_factory import resolve_engine_for_session
from .query_session_service import QuerySessionService

logger = logging.getLogger(__name__)


class InProcessQuerySessionService(IQuerySessionServiceProtocol):
    """Direct-access query-session service for in-process (local) execution."""

    def __init__(self, project_id: str, *, runtime_provider: RuntimeProviderProtocol) -> None:
        from kontext.data import CatalogDataService, QuerySessionDataService

        self._project_id = str(project_id)
        self._runtime_provider = runtime_provider
        self._service = QuerySessionService(self._project_id)
        self._data_service = QuerySessionDataService(self._project_id)
        self._catalog_data_service = CatalogDataService(self._project_id)

    def _validate_project_id(self, project_id: UUID | str | None) -> None:
        if project_id is None:
            return
        if str(project_id) != self._project_id:
            raise ValueError(f"Project ID mismatch: {project_id} != {self._project_id}")

    @staticmethod
    def _is_session_compatible(
        session: QuerySessionModel,
        *,
        expected_session_id: UUID | str | None = None,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        default_entity_id: UUID | str | None = None,
        engine_type: QueryEngineType | str | None = None,
    ) -> bool:
        return is_session_compatible(
            session,
            expected_session_id=expected_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
        )

    async def _resolve_effective_engine_type(
        self,
        *,
        engine_type: QueryEngineType | str | None = None,
        catalog_connection_id: UUID | str | None = None,
        session_id: UUID | str | None = None,
    ) -> QueryEngineType:
        resolved_engine = safe_enum_conversion(QueryEngineType, engine_type, None)
        if resolved_engine is not None:
            return resolved_engine

        if session_id:
            session = await self.get_query_session(session_id, self._project_id)
            if session and session.engine_type:
                return safe_enum_conversion(
                    QueryEngineType, session.engine_type, QueryEngineType.DUCKDB
                )

        if catalog_connection_id:
            connection = await self._catalog_data_service.get_connection_async(
                str(catalog_connection_id)
            )
            return resolve_query_engine_type_for_connection(connection)

        return QueryEngineType.DUCKDB

    async def get_query_session(
        self, session_id: UUID | str, project_id: UUID | str
    ) -> QuerySessionModel | None:
        self._validate_project_id(project_id)
        return await self._service.get_query_session(session_id, project_id)

    async def set_catalog_revision(self, session_id: UUID | str, revision: str | None) -> bool:
        """Record the catalog revision a session materialized."""
        return await self._data_service.set_catalog_revision_async(session_id, revision)

    async def _resolve_expected_catalog_revision(
        self,
        *,
        catalog_connection_id: UUID | str | None,
        session_id: UUID | str | None,
    ) -> str | None:
        """Resolve the catalog revision a reusable session must match.

        Prefers the connection passed with the request; falls back to the
        session's own connection when only a session id is supplied.
        """
        connection_id = catalog_connection_id
        if connection_id is None and session_id:
            existing = await self.get_query_session(session_id, self._project_id)
            if existing is not None:
                connection_id = existing.catalog_connection_id
        if connection_id is None:
            return None
        return await self._data_service.get_catalog_revision_async(connection_id)

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
        resolved_engine = await self._resolve_effective_engine_type(
            engine_type=engine_type,
            catalog_connection_id=catalog_connection_id,
        )
        request = CreateQuerySessionRequest(
            project_id=str(project_id),
            catalog_connection_id=(str(catalog_connection_id) if catalog_connection_id else None),
            default_namespace=default_namespace,
            default_entity_id=str(default_entity_id) if default_entity_id else None,
            session_name=session_name,
            engine_type=resolved_engine,
            is_persistent=persistent,
        )
        session = await self._service.create_session_async(request, user_id=None)
        db_path = get_session_database_path(
            project_id=str(project_id),
            session_id=str(session.id),
            persistent=persistent,
        )
        return str(session.id), db_path

    async def close_query_session(self, session_id: UUID | str, project_id: UUID | str) -> bool:
        self._validate_project_id(project_id)
        closed = await asyncio.to_thread(self._data_service.delete_session, str(session_id), None)
        delete_session_database_file(str(project_id), str(session_id))
        return bool(closed)

    async def get_most_recent_active_session(
        self,
        project_id: UUID | str,
        catalog_connection_id: UUID | str | None = None,
        default_namespace: str | None = None,
        engine_type: str | None = None,
    ) -> QuerySessionModel | None:
        self._validate_project_id(project_id)
        sessions, _ = await asyncio.to_thread(
            self._data_service.list_sessions_by_status,
            None,
            [QuerySessionStatus.ACTIVE, QuerySessionStatus.INITIALIZING],
            str(catalog_connection_id) if catalog_connection_id else None,
            default_namespace,
            1,
            50,
            False,
        )

        if not sessions:
            return None

        if not engine_type:
            return sessions[0]

        engine_value = str(engine_type).lower()
        for session in sessions:
            session_engine = (
                session.engine_type.value
                if hasattr(session.engine_type, "value")
                else session.engine_type
            )
            if str(session_engine).lower() == engine_value:
                return session
        return None

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

        if not session:
            sessions, _ = await asyncio.to_thread(
                self._data_service.list_sessions_by_status,
                None,
                [QuerySessionStatus.ACTIVE, QuerySessionStatus.INITIALIZING],
                str(catalog_connection_id) if catalog_connection_id else None,
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
                    expected_catalog_revision=expected_revision,
                )
            ]
            ordered_sessions = sort_sessions_by_preference(compatible_sessions)
            session = ordered_sessions[0] if ordered_sessions else None

        if session:
            return str(session.id)

        session_id, _ = await self.create_query_session(
            project_id=project_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            session_name=session_name,
            persistent=True,
            engine_type=engine_type,
        )
        return session_id

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
        # ``parent_run_id`` chains job-routed executions only. This in-process
        # implementation runs synchronously inside the request (no managed run
        # to link) and accepts the parameter purely for protocol parity with
        # the queued-job implementation of ``execute_sql_with_session_management``.
        effective_session_id = str(session_id) if session_id else None
        resolved_engine = await self._resolve_effective_engine_type(
            engine_type=engine_type,
            catalog_connection_id=catalog_connection_id,
            session_id=effective_session_id,
        )

        if effective_session_id:
            session_info = await self.get_query_session(effective_session_id, project_id)
            if not session_info or session_info.status == QuerySessionStatus.DELETED:
                effective_session_id = None
            elif session_info.engine_type:
                session_engine = (
                    session_info.engine_type.value
                    if hasattr(session_info.engine_type, "value")
                    else session_info.engine_type
                )
                if str(session_engine).lower() != str(resolved_engine.value).lower():
                    effective_session_id = None

        effective_session_id = await self.get_or_create_session(
            project_id=project_id,
            session_id=effective_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
        )

        engine = None
        query_timed_out = False
        start_time = time.time()
        try:
            # Serialize access to the (single-writer) session database.
            lock_key = effective_session_id or f"__ephemeral__{project_id}"
            async with session_execution_lock(lock_key):
                # Stop/dispose the engine before releasing the lock: a timed-out
                # query's executor thread can still be running, and the next
                # query on this session must not open the same session database
                # while it is.
                try:
                    engine = await resolve_engine_for_session(
                        engine_type=resolved_engine,
                        runtime_provider=self._runtime_provider,
                        request=QueryEngineRequest(
                            project_id=str(project_id),
                            catalog_connection_id=(
                                str(catalog_connection_id) if catalog_connection_id else None
                            ),
                            default_namespace=default_namespace,
                            default_entity_id=(
                                str(default_entity_id) if default_entity_id else None
                            ),
                            session_id=effective_session_id,
                        ),
                    )
                    await engine.connect()

                    # Always bound the query: the session lock is held while it
                    # runs, so an unbounded query would block every later query
                    # on this session across the whole process. An explicit
                    # caller-provided timeout wins; None gets the default guard.
                    effective_timeout = (
                        query_timeout_seconds
                        if query_timeout_seconds
                        else QueryConstants.DEFAULT_QUERY_TIMEOUT_SECONDS
                    )
                    try:
                        table = await asyncio.wait_for(
                            engine.fetch_data_table(
                                sql_query, max_rows=QueryConstants.MAX_FETCH_ROWS
                            ),
                            timeout=effective_timeout,
                        )
                    except TimeoutError:
                        # Stop the orphaned query thread so disposal can close
                        # the connection without racing it. Re-raise with a
                        # message so callers (and the agent) can act on it.
                        query_timed_out = True
                        raise TimeoutError(
                            f"SQL query timed out after {effective_timeout} seconds"
                        ) from None

                    total_execution_time_ms = int((time.time() - start_time) * 1000)
                    identity_key = (
                        build_data_identity_key(
                            sql_query,
                            catalog_connection_id=catalog_connection_id,
                            default_namespace=default_namespace,
                            default_entity_id=default_entity_id,
                            engine_type=resolved_engine,
                        )
                        if table and (table.row_count or 0) > 0
                        else None
                    )
                    response = QueryResponse(
                        result=table,
                        total_execution_time_ms=total_execution_time_ms,
                        success=True,
                        error_message=None,
                        data_id=None,
                        sql=sql_query,
                        provenance=ArtifactProvenance(
                            origin=ArtifactOrigin.SQLQUERY,
                            created_by=triggered_by,
                            chat_session_id=(str(chat_session_id) if chat_session_id else None),
                            identity_key=identity_key,
                        ),
                    )

                    persist_result = bool(table) and should_persist_result(
                        row_count=(table.row_count or 0) if table else 0,
                        store_as_resource=store_result_as_resource,
                        threshold_rows=store_result_threshold_rows,
                    )

                    if persist_result and table:
                        file_service = self._runtime_provider.get_file_service()
                        if file_service is None:
                            logger.warning("File service unavailable; skipping result storage.")
                        else:
                            file_id = await file_service.store_query_results_as_file(
                                project_id=project_id,
                                query_response=response,
                                session_id=effective_session_id,
                                name=store_result_name,
                                chat_session_id=chat_session_id,
                            )
                            if file_id:
                                response.data_id = file_id
                                if response.result and response.result.rows:
                                    response.result.rows = response.result.rows[
                                        : QueryConstants.PREVIEW_ROW_LIMIT
                                    ]

                    database_size_bytes = getattr(engine, "get_session_file_size", lambda: None)()
                    await self._service.update_query_session(
                        session_id=effective_session_id,
                        project_id=project_id,
                        status=QuerySessionStatus.ACTIVE,
                        database_size_bytes=database_size_bytes,
                    )
                    return response
                finally:
                    if engine:
                        if query_timed_out:
                            # Best-effort: engines that support it stop the
                            # orphaned query thread so disposal never races it.
                            interrupt = cast(
                                "Callable[[], Awaitable[None]] | None",
                                getattr(engine, "interrupt", None),
                            )
                            if callable(interrupt):
                                with suppress(Exception):
                                    await interrupt()
                        await engine.dispose()

        except Exception as exc:
            logger.exception("Failed to execute SQL with in-process session")
            await self._service.update_query_session(
                session_id=effective_session_id,
                project_id=project_id,
                status=QuerySessionStatus.ERROR,
                metadata=str(exc),
            )
            total_execution_time_ms = int((time.time() - start_time) * 1000)
            return QueryResponse(
                result=None,
                total_execution_time_ms=total_execution_time_ms,
                success=False,
                error_message=f"SQL execution failed: {exc}",
                data_id=None,
                sql=sql_query,
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
        return await self._service.update_query_session(
            session_id=session_id,
            project_id=project_id,
            session_name=session_name,
            status=status,
            metadata=metadata,
            database_size_bytes=database_size_bytes,
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
