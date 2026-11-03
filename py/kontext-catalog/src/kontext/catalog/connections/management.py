"""High-level catalog management service."""

from __future__ import annotations

import logging
from uuid import UUID

from kontext.common.catalog.connector_specs import (
    resolve_query_engine_type_for_connection,
)
from kontext.common.utils.enum_utils import enum_value
from kontext.data import (
    CatalogDataService,
    QuerySessionDataService,
)
from kontext.schema import (
    CatalogConnection,
    CatalogConnectionRequest,
    CatalogConnectionValidationResult,
    CatalogEntityDetail,
    CatalogEntitySummary,
    CatalogNamespaceSummary,
    CatalogProviderDefinition,
    CatalogSearchItem,
    CatalogSyncStatus,
    QueryEngineType,
)

from ..indexing.catalog_index import CatalogIndexService
from .providers import CatalogProviderRegistry

logger = logging.getLogger(__name__)

DEFAULT_INTERNAL_CONNECTION_DISPLAY_NAME = "Default Lakehouse"


class CatalogManagementService:
    """Orchestrates catalog providers, persistence, and indexing."""

    def __init__(self, project_id: str, runtime_provider=None) -> None:
        self.project_id = str(project_id)
        self.runtime_provider = runtime_provider
        self.data_service = CatalogDataService(self.project_id)
        self.provider_registry = CatalogProviderRegistry(self.project_id)
        self.index_service = CatalogIndexService(self.project_id, runtime_provider=runtime_provider)

    async def list_provider_definitions(self) -> list[CatalogProviderDefinition]:
        return self.provider_registry.list_definitions()

    async def ensure_default_internal_connection(self) -> CatalogConnection:
        connections = await self.data_service.list_connections_async()
        for connection in connections:
            if connection.provider_kind.value == "iceberg_internal":
                return connection

        provider = self.provider_registry.get(
            next(
                definition.provider_kind
                for definition in self.provider_registry.list_definitions()
                if definition.provider_kind.value == "iceberg_internal"
            )
        )
        request = provider.default_request(project_id=self.project_id)
        return await self.data_service.upsert_connection_async(request)

    async def list_connections(self) -> list[CatalogConnection]:
        await self.ensure_default_internal_connection()
        return await self.data_service.list_connections_async()

    async def create_connection(
        self, request: CatalogConnectionRequest, owner_id: str | None = None
    ) -> CatalogConnection:
        request = self._normalize_connection_request(request)
        return await self.data_service.upsert_connection_async(request, owner_id=owner_id)

    async def update_connection(
        self,
        connection_id: str,
        request: CatalogConnectionRequest,
        owner_id: str | None = None,
    ) -> CatalogConnection:
        request = self._normalize_connection_request(request)
        return await self.data_service.upsert_connection_async(
            request,
            owner_id=owner_id,
            connection_id=connection_id,
        )

    def _normalize_connection_request(
        self, request: CatalogConnectionRequest
    ) -> CatalogConnectionRequest:
        provider = self.provider_registry.get(request.provider_kind)
        request_source_category = enum_value(request.source_category)
        request_auth_type = enum_value(request.auth_type)
        request_execution_mode = enum_value(request.execution_mode)

        if not provider.capabilities.supports_sync:
            raise ValueError(f"{provider.display_name} is not available in this runtime yet.")
        if request.connection_kind != provider.connection_kind:
            raise ValueError(
                f"{provider.display_name} requires connection kind "
                f"{provider.connection_kind.value}."
            )
        if (
            request_source_category is not None
            and request_source_category != provider.source_category.value
        ):
            raise ValueError(
                f"{provider.display_name} requires source category "
                f"{provider.source_category.value}."
            )
        if request_auth_type is not None and request_auth_type not in {
            auth_type.value for auth_type in provider.auth_types
        }:
            supported_auth_types = ", ".join(auth_type.value for auth_type in provider.auth_types)
            request_auth_type_value = getattr(request_auth_type, "value", request_auth_type)
            raise ValueError(
                f"{provider.display_name} does not support auth type "
                f"{request_auth_type_value}. Supported auth types: "
                f"{supported_auth_types}."
            )
        if request_execution_mode is not None and request_execution_mode not in {
            execution_mode.value for execution_mode in provider.execution_modes
        }:
            supported_execution_modes = ", ".join(
                execution_mode.value for execution_mode in provider.execution_modes
            )
            request_execution_mode_value = getattr(
                request_execution_mode, "value", request_execution_mode
            )
            raise ValueError(
                f"{provider.display_name} does not support execution mode "
                f"{request_execution_mode_value}. Supported execution modes: "
                f"{supported_execution_modes}."
            )

        normalized_auth_type = request.auth_type
        if normalized_auth_type is None and provider.auth_types:
            normalized_auth_type = provider.auth_types[0]

        normalized_execution_mode = request.execution_mode
        if normalized_execution_mode is None and provider.execution_modes:
            normalized_execution_mode = provider.execution_modes[0]

        return request.model_copy(
            update={
                "source_category": provider.source_category,
                "auth_type": normalized_auth_type,
                "execution_mode": normalized_execution_mode,
                "capabilities": provider.capabilities,
            }
        )

    async def delete_connection(self, connection_id: str) -> bool:
        return await self.data_service.delete_connection_async(connection_id)

    async def validate_connection(self, connection_id: str) -> CatalogConnectionValidationResult:
        connection = await self.data_service.get_connection_async(connection_id)
        if connection is None:
            raise ValueError(f"Catalog connection {connection_id} not found")

        provider = self.provider_registry.get(connection.provider_kind)
        result = await provider.validate(connection)
        await self.data_service.update_validation_status_async(
            connection_id,
            status=result.status,
            message=result.message,
            error_message=result.error_message,
        )
        return result

    async def sync_connection(self, connection_id: str) -> CatalogSyncStatus:
        connection = await self.data_service.get_connection_async(connection_id)
        if connection is None:
            raise ValueError(f"Catalog connection {connection_id} not found")

        provider = self.provider_registry.get(connection.provider_kind)
        await self.data_service.update_sync_status_async(connection_id, status="running")
        try:
            snapshots = await provider.sync(connection)
            status = await self.data_service.replace_connection_snapshot_async(
                connection_id,
                snapshots,
                status="succeeded",
                error_message=None,
            )
            refreshed_connection = await self.data_service.get_connection_async(connection_id)
            if refreshed_connection is None:
                raise ValueError(f"Catalog connection {connection_id} not found")
            entity_details = await self.data_service.list_entity_details_for_connection_async(
                connection_id
            )
            await self.index_service.index_catalog_entities(
                connection=refreshed_connection,
                entities=entity_details,
                engine_type=resolve_query_engine_type_for_connection(refreshed_connection),
                recreate=True,
            )
            await self._invalidate_dependent_sessions(connection_id)
            return status
        except Exception as exc:
            return await self.data_service.update_sync_status_async(
                connection_id,
                status="failed",
                error_message=str(exc),
            )

    async def _invalidate_dependent_sessions(self, connection_id: str) -> None:
        """Invalidate query sessions whose materialized catalog is now stale.

        Only sessions bound to the synced connection are touched, and chat
        sessions are deliberately left intact: their message history lives in
        the agent database and must survive catalog refreshes. The actual
        DuckDB session files are reclaimed by the orphan sweeper, so this stays
        a fast, non-blocking metadata update.
        """
        query_session_service = QuerySessionDataService(self.project_id)
        invalidated_query_ids = (
            await query_session_service.invalidate_sessions_for_catalog_connection_async(
                connection_id,
                reason="Catalog metadata changed",
            )
        )
        logger.info(
            "Invalidated %s query sessions for catalog connection %s",
            len(invalidated_query_ids),
            connection_id,
        )

    async def list_entities(
        self,
        *,
        connection_id: str | None = None,
        namespace_name: str | None = None,
    ) -> list[CatalogEntitySummary]:
        return await self.data_service.list_entities_async(
            connection_id=connection_id,
            namespace_name=namespace_name,
        )

    async def list_namespaces(
        self, *, connection_id: str | None = None
    ) -> list[CatalogNamespaceSummary]:
        resolved_connection_id = connection_id
        if resolved_connection_id is None:
            connection = await self.ensure_default_internal_connection()
            resolved_connection_id = connection.id
        if resolved_connection_id is None:
            return []
        return await self.data_service.list_namespaces_async(resolved_connection_id)

    async def get_entity_detail(self, entity_id: str) -> CatalogEntityDetail | None:
        return await self.data_service.get_entity_detail_async(entity_id)

    async def refresh_entity(self, entity_id: str) -> CatalogSyncStatus:
        detail = await self.data_service.get_entity_detail_async(entity_id)
        if detail is None:
            raise ValueError(f"Catalog entity {entity_id} not found")
        return await self.sync_connection(detail.entity.connection_id)

    async def search(
        self,
        *,
        query: str,
        connection_id: str | None = None,
        limit: int = 5,
        engine_type: QueryEngineType = QueryEngineType.DUCKDB,
    ) -> list[CatalogSearchItem]:
        candidate_connections: list[CatalogConnection]
        if connection_id:
            connection = await self.data_service.get_connection_async(connection_id)
            candidate_connections = [connection] if connection else []
        else:
            candidate_connections = [
                connection
                for connection in await self.list_connections()
                if connection.enabled and connection.capabilities.supports_search
            ]

        results: list[CatalogSearchItem] = []
        for connection in candidate_connections:
            if connection is None:
                continue
            try:
                results.extend(
                    await self.index_service.search(
                        query=query,
                        engine_type=engine_type,
                        limit=limit,
                        catalog_connection_id=connection.id,
                    )
                )
            except Exception:
                continue

        results.sort(
            key=lambda item: item.score if item.score is not None else float("-inf"),
            reverse=True,
        )
        return results[:limit]

    async def ingest_file(
        self,
        file_id: UUID | str,
        *,
        namespace_name: str | None = None,
    ) -> list[CatalogEntityDetail]:
        normalized_file_id = str(file_id)
        connection = await self.ensure_default_internal_connection()
        provider = self.provider_registry.get(connection.provider_kind)
        lakehouse_service = getattr(provider, "lakehouse_service", None)
        if lakehouse_service is None:
            raise RuntimeError(
                "Internal catalog ingest is unavailable because the internal provider "
                "does not expose a lakehouse service."
            )

        await lakehouse_service.ingest_file(
            file_id=normalized_file_id,
            namespace_name=namespace_name,
        )
        status = await self.sync_connection(connection.id or "")
        if status.entity_count == 0:
            return []
        return await self.get_source_entities(source_type="file", source_id=normalized_file_id)

    async def remove_file_entities(self, file_id: UUID | str) -> list[str]:
        connection = await self.ensure_default_internal_connection()
        provider = self.provider_registry.get(connection.provider_kind)
        lakehouse_service = getattr(provider, "lakehouse_service", None)
        if lakehouse_service is None:
            raise RuntimeError(
                "Internal catalog cleanup is unavailable because the internal provider "
                "does not expose a lakehouse service."
            )

        deleted_entity_ids = await lakehouse_service.delete_file_entities(str(file_id))
        await self.sync_connection(connection.id or "")
        return deleted_entity_ids

    async def get_source_entities(
        self, *, source_type: str, source_id: UUID | str
    ) -> list[CatalogEntityDetail]:
        source_links = await self.data_service.list_source_links_async(
            source_type=source_type,
            source_id=str(source_id),
        )
        details: list[CatalogEntityDetail] = []
        for link in source_links:
            if link.entity_id is None:
                continue
            detail = await self.data_service.get_entity_detail_async(link.entity_id)
            if detail is not None:
                details.append(detail)
        return details

    async def get_entity_stats(self, entity_id: UUID | str) -> dict[str, object] | None:
        detail = await self.get_entity_detail(str(entity_id))
        if detail is None:
            return None
        return {
            "entity_id": detail.entity.id,
            "entity_name": detail.entity.entity_name,
            "namespace_name": detail.entity.namespace_name,
            "row_count": detail.entity.row_count,
            "column_count": detail.entity.column_count,
            "metadata": detail.entity.metadata,
        }
