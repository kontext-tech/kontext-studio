"""
Query-session business service owned by the query domain.
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from kontext.catalog import LakehouseService
from kontext.common.catalog.connector_specs import (
    resolve_query_engine_type_for_connection,
)
from kontext.common.project_scoped import ProjectScopedService
from kontext.data import CatalogDataService, QuerySessionDataService
from kontext.schema import (
    CreateQuerySessionRequest,
    QueryEngineType,
    QuerySessionModel,
    QuerySessionStatus,
    UpdateQuerySessionRequest,
)

logger = logging.getLogger(__name__)


class QuerySessionService(ProjectScopedService):
    """Business service for managing query sessions."""

    def __init__(self, project_id: UUID | str):
        super().__init__(project_id)
        self._session_data_service = QuerySessionDataService(project_id)
        self._catalog_data_service = CatalogDataService(project_id)

    async def create_session_async(
        self, request: CreateQuerySessionRequest, user_id: str | None
    ) -> QuerySessionModel:
        if not request.catalog_connection_id:
            connection = await LakehouseService(str(self.project_id)).ensure_internal_connection()
            request.catalog_connection_id = str(connection.id) if connection.id else None
            if not request.default_namespace:
                request.default_namespace = connection.config.default_namespace or "bronze"
        engine_type = await self._resolve_engine_type(request)
        return await self._session_data_service.create_session_async(
            request=request, user_id=user_id, engine_type=engine_type
        )

    async def get_query_session(
        self, session_id: UUID | str, project_id: UUID | str
    ) -> QuerySessionModel | None:
        self._validate_project_id(project_id)
        return await self._session_data_service.get_by_id_async(session_id)

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
        request = UpdateQuerySessionRequest(
            session_name=session_name,
            status=status,
            metadata=metadata,
            database_size_bytes=database_size_bytes,
        )
        try:
            return await asyncio.to_thread(
                self._session_data_service.update_session,
                str(session_id),
                request,
                None,
            )
        except Exception:
            logger.exception(
                "Failed to update query session %s for project %s",
                session_id,
                project_id,
            )
            return None

    async def _resolve_engine_type(self, request: CreateQuerySessionRequest) -> QueryEngineType:
        if request.engine_type:
            return request.engine_type

        if request.catalog_connection_id:
            connection = await self._catalog_data_service.get_connection_async(
                request.catalog_connection_id
            )
            return resolve_query_engine_type_for_connection(connection)

        config = await self._session_data_service.get_project_config_async()
        if config and config.default_query_engine:
            return config.default_query_engine

        return QueryEngineType.DUCKDB
