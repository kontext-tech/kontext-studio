"""Catalog management and indexing contracts."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from kontext.common.knowledge.index import KnowledgeSearchHit
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


class ICatalogManagementServiceProtocol(Protocol):
    """Project-scoped catalog management service contract."""

    async def list_provider_definitions(self) -> list[CatalogProviderDefinition]: ...

    async def ensure_default_internal_connection(self) -> CatalogConnection: ...

    async def list_connections(self) -> list[CatalogConnection]: ...

    async def create_connection(
        self, request: CatalogConnectionRequest, owner_id: str | None = None
    ) -> CatalogConnection: ...

    async def update_connection(
        self,
        connection_id: str,
        request: CatalogConnectionRequest,
        owner_id: str | None = None,
    ) -> CatalogConnection: ...

    async def delete_connection(self, connection_id: str) -> bool: ...

    async def validate_connection(
        self, connection_id: str
    ) -> CatalogConnectionValidationResult: ...

    async def sync_connection(self, connection_id: str) -> CatalogSyncStatus: ...

    async def list_entities(
        self,
        *,
        connection_id: str | None = None,
        namespace_name: str | None = None,
    ) -> list[CatalogEntitySummary]: ...

    async def list_namespaces(
        self, *, connection_id: str | None = None
    ) -> list[CatalogNamespaceSummary]: ...

    async def get_entity_detail(self, entity_id: str) -> CatalogEntityDetail | None: ...

    async def refresh_entity(self, entity_id: str) -> CatalogSyncStatus: ...

    async def search(
        self,
        *,
        query: str,
        connection_id: str | None = None,
        limit: int = 5,
        engine_type: QueryEngineType = QueryEngineType.DUCKDB,
    ) -> list[CatalogSearchItem]: ...

    async def ingest_file(
        self,
        file_id: UUID | str,
        *,
        namespace_name: str | None = None,
    ) -> list[CatalogEntityDetail]: ...

    async def remove_file_entities(self, file_id: UUID | str) -> list[str]: ...

    async def get_source_entities(
        self, *, source_type: str, source_id: UUID | str
    ) -> list[CatalogEntityDetail]: ...

    async def get_entity_stats(self, entity_id: UUID | str) -> dict[str, Any] | None: ...


class ICatalogIndexServiceProtocol(Protocol):
    """Protocol defining the interface for catalog indexing and search."""

    async def search(
        self,
        query: str,
        engine_type: QueryEngineType = QueryEngineType.DUCKDB,
        limit: int = 5,
        catalog_connection_id: str | None = None,
    ) -> list[CatalogSearchItem]: ...

    async def search_knowledge(
        self,
        *,
        query: str,
        limit: int = 5,
        scopes: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        apply_trust_gate: bool = True,
    ) -> list[KnowledgeSearchHit]: ...
