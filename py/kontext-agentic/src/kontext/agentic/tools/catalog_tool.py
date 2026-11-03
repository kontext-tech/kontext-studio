"""Catalog discovery tools used by SQL and Python agents."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kontext.agent import RuntimeToolContext
from kontext.agent.tools import tool_meta
from kontext.data import CatalogDataService
from kontext.schema import (
    CatalogEntityStatsBatchResult,
    CatalogEntityStatsResult,
    CatalogListingResult,
    CatalogSearchResult,
    ColumnStatsModel,
    DiscoveryResult,
    DocumentSearchItem,
    ProjectModel,
    QueryEngineType,
)

from ..utils.guid_validation import validate_guid
from .kontext_toolkit import KontextToolkit, ToolkitScope

if TYPE_CHECKING:
    from kontext.catalog.indexing.document_index import DocumentSearchResult
    from kontext.common.protocols import AIToolkitServiceProviderProtocol
    from kontext.schema import (
        CatalogEntityDetail,
        CatalogEntitySummary,
        CatalogSearchItem,
        OkfConcept,
    )

# Catalog metadata and document excerpts can be arbitrarily long. Tool results
# are replayed into every later turn of a run, so cap the free-text fields that
# the model rarely needs in full. Ids/names/types/counts stay untouched.
_MAX_COLUMN_DESCRIPTION_CHARS = 300
_MAX_DOCUMENT_EXCERPT_CHARS = 2000


def _truncate_text(value: str | None, limit: int) -> str | None:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit].rstrip() + "..."
    return value


class CatalogTools(KontextToolkit):
    """Catalog-oriented discovery toolkit for namespace and entity exploration."""

    def __init__(
        self,
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: str | None = None,
        include_catalog_search: bool | None = None,
        include_catalog_listing_tools: bool | None = None,
        scope: ToolkitScope | None = None,
    ) -> None:
        can_list_catalog = (
            include_catalog_listing_tools
            if include_catalog_listing_tools is not None
            else (runtime_provider is None or runtime_provider.get_catalog_service() is not None)
        )
        can_search_catalog = (
            include_catalog_search
            if include_catalog_search is not None
            else (
                runtime_provider is None or runtime_provider.get_catalog_index_service() is not None
            )
        )

        tools: list[Callable[..., Any]] = [self.search_catalog] if can_search_catalog else []

        if can_list_catalog:
            tools.extend([self.list_namespaces, self.list_entities])
        tools.append(self.inspect_entity_columns)
        tools.append(self.inspect_entities_columns)
        tools.append(self.discover)

        super().__init__(
            name="CatalogTools",
            project=project,
            runtime_provider=runtime_provider,
            session_id=session_id,
            chat_session_id=chat_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
            scope=scope,
            tools=tools,
        )
        self.catalog_data_service = CatalogDataService(str(self.project_id))
        validate_guid(self.project_id, "project_id")

        # Entity summaries are stable within a run; cache them per namespace so
        # batch inspection does not re-list the catalog for every entity.
        self._entities_cache: dict[str | None, list[CatalogEntitySummary]] = {}

    async def _resolve_connection_id(self) -> str:
        await self.hydrate_query_scope_from_chat_session()

        if self.catalog_connection_id:
            return str(self.catalog_connection_id)

        connections = await self.catalog_data_service.list_connections_async()
        enabled = [connection for connection in connections if connection.enabled]
        if not enabled:
            raise ValueError("No enabled catalog connections found for this project.")
        connection_id = enabled[0].id
        if not connection_id:
            raise ValueError("Enabled catalog connection is missing an ID.")
        self.catalog_connection_id = connection_id
        return connection_id

    async def _list_entities_cached(
        self, connection_id: str, namespace_name: str | None
    ) -> list[CatalogEntitySummary]:
        """List entities for a namespace once per run, then serve from cache."""
        if namespace_name not in self._entities_cache:
            self._entities_cache[
                namespace_name
            ] = await self.catalog_data_service.list_entities_async(
                connection_id=connection_id,
                namespace_name=namespace_name,
            )
        return self._entities_cache[namespace_name]

    @staticmethod
    def _build_column_stats(detail: CatalogEntityDetail) -> list[ColumnStatsModel]:
        return [
            ColumnStatsModel(
                column_name=column.name,
                stats_source=column.data_type,
                samples=[
                    {
                        "nullable": column.nullable,
                        "ordinal_position": column.ordinal_position,
                        "description": _truncate_text(
                            column.description, _MAX_COLUMN_DESCRIPTION_CHARS
                        ),
                    }
                ],
            )
            for column in detail.columns
        ]

    @tool_meta(CatalogListingResult, display_name="List Namespaces", emit_tool_call=True)
    async def list_namespaces(self) -> str:
        """List namespaces in the active catalog connection."""
        try:
            connection_id = await self._resolve_connection_id()
            namespaces = await self.catalog_data_service.list_namespaces_async(connection_id)
            rows = [
                {
                    "id": namespace.id,
                    "name": namespace.name,
                    "display_name": namespace.display_name,
                    "entity_count": namespace.entity_count,
                }
                for namespace in namespaces
            ]
            return self._wrap_result(
                CatalogListingResult(
                    success=True,
                    catalog_connection_id=connection_id,
                    objects_count=len(rows),
                    objects=self.format_as_table(rows, format="csv"),
                    message=f"Found {len(rows)} namespaces in the active catalog connection.",
                )
            )
        except Exception as exc:
            return self._wrap_result(
                CatalogListingResult(
                    success=False,
                    catalog_connection_id=self.catalog_connection_id,
                    objects_count=0,
                    objects="",
                    message=f"Failed to list namespaces: {exc}",
                )
            )

    @tool_meta(CatalogListingResult, display_name="List Catalog Entities", emit_tool_call=True)
    async def list_entities(
        self, namespace_id: str | None = None, namespace_name: str | None = None
    ) -> str:
        """List entities in a namespace."""
        try:
            connection_id = await self._resolve_connection_id()
            resolved_namespace = namespace_name or namespace_id or self.default_namespace
            entities = await self._list_entities_cached(connection_id, resolved_namespace)
            rows = [
                {
                    "id": entity.id,
                    "namespace": entity.namespace_name,
                    "entity_name": entity.entity_name,
                    "entity_type": entity.entity_type.value
                    if hasattr(entity.entity_type, "value")
                    else str(entity.entity_type),
                    "column_count": entity.column_count,
                    "row_count": entity.row_count,
                }
                for entity in entities
            ]
            scope_label = resolved_namespace or "all namespaces"
            return self._wrap_result(
                CatalogListingResult(
                    success=True,
                    catalog_connection_id=connection_id,
                    objects_count=len(rows),
                    objects=self.format_as_table(rows, format="csv"),
                    message=f"Found {len(rows)} catalog entities in {scope_label}.",
                )
            )
        except Exception as exc:
            return self._wrap_result(
                CatalogListingResult(
                    success=False,
                    catalog_connection_id=self.catalog_connection_id,
                    objects_count=0,
                    objects="",
                    message=f"Failed to list catalog entities: {exc}",
                )
            )

    @tool_meta(
        CatalogEntityStatsResult,
        display_name="Inspect Entity Columns",
        emit_tool_call=False,
    )
    async def inspect_entity_columns(self, namespace_name: str, object_name: str) -> str:
        """Inspect normalized catalog columns for a namespace/entity pair."""
        try:
            connection_id = await self._resolve_connection_id()
            entities = await self._list_entities_cached(connection_id, namespace_name)
            entity = next(
                (item for item in entities if item.entity_name == object_name),
                None,
            )
            if entity is None:
                raise ValueError(f"Catalog entity '{namespace_name}.{object_name}' not found")
            detail = await self.catalog_data_service.get_entity_detail_async(entity.id)
            if detail is None:
                raise ValueError(f"Catalog detail for '{namespace_name}.{object_name}' not found")

            column_stats = self._build_column_stats(detail)
            return self._wrap_result(
                CatalogEntityStatsResult(
                    success=True,
                    message=f"Found {len(column_stats)} columns for {namespace_name}.{object_name}",
                    catalog_connection_id=connection_id,
                    namespace_name=namespace_name,
                    object_name=object_name,
                    column_stats=column_stats,
                    stats_count=len(column_stats),
                )
            )
        except Exception as exc:
            return self._wrap_result(
                CatalogEntityStatsResult(
                    success=False,
                    catalog_connection_id=self.catalog_connection_id,
                    namespace_name=namespace_name,
                    object_name=object_name,
                    message=f"Failed to inspect entity columns: {exc}",
                )
            )

    @tool_meta(
        CatalogEntityStatsBatchResult,
        display_name="Inspect Entity Columns (Batch)",
        emit_tool_call=False,
    )
    async def inspect_entities_columns(
        self, entities: list[str], namespace_name: str | None = None
    ) -> str:
        """Inspect normalized catalog columns for several namespace/entity pairs at once.

        Use this instead of calling ``inspect_entity_columns`` once per table when
        you already know the set of tables to confirm. Each entry may be a bare
        entity name (resolved against ``namespace_name`` or the active default
        namespace) or a qualified ``namespace.entity`` string.

        :param entities: Entity references, e.g. ``["orders", "crm.customers"]``.
        :param namespace_name: Optional default namespace for unqualified entries.
        """
        try:
            if not entities:
                return self._wrap_result(
                    CatalogEntityStatsBatchResult(
                        success=False,
                        message="No entities provided.",
                    )
                )

            connection_id = await self._resolve_connection_id()

            requested: list[tuple[str | None, str]] = []
            for entry in entities:
                normalized = str(entry).strip()
                if not normalized:
                    continue
                if "." in normalized:
                    entry_namespace, entry_name = normalized.split(".", 1)
                else:
                    entry_namespace, entry_name = (
                        namespace_name or self.default_namespace,
                        normalized,
                    )
                requested.append((entry_namespace, entry_name))

            # One listing per namespace, not one per entity.
            entities_by_namespace: dict[str | None, dict[str, CatalogEntitySummary]] = {}
            for entry_namespace in {namespace for namespace, _ in requested}:
                listed = await self._list_entities_cached(connection_id, entry_namespace)
                entities_by_namespace[entry_namespace] = {item.entity_name: item for item in listed}

            async def resolve_one(
                entry_namespace: str | None, entry_name: str
            ) -> CatalogEntityStatsResult:
                summary = entities_by_namespace.get(entry_namespace, {}).get(entry_name)
                if summary is None:
                    return CatalogEntityStatsResult(
                        success=False,
                        message=(f"Catalog entity '{entry_namespace}.{entry_name}' not found"),
                        catalog_connection_id=connection_id,
                        namespace_name=entry_namespace,
                        object_name=entry_name,
                    )
                detail = await self.catalog_data_service.get_entity_detail_async(summary.id)
                if detail is None:
                    return CatalogEntityStatsResult(
                        success=False,
                        message=(f"Catalog detail for '{entry_namespace}.{entry_name}' not found"),
                        catalog_connection_id=connection_id,
                        namespace_name=entry_namespace,
                        object_name=entry_name,
                    )
                column_stats = self._build_column_stats(detail)
                return CatalogEntityStatsResult(
                    success=True,
                    message=(
                        f"Found {len(column_stats)} columns for {entry_namespace}.{entry_name}"
                    ),
                    catalog_connection_id=connection_id,
                    namespace_name=entry_namespace,
                    object_id=str(summary.id),
                    object_name=entry_name,
                    column_stats=column_stats,
                    stats_count=len(column_stats),
                )

            results = await asyncio.gather(
                *(resolve_one(namespace, name) for namespace, name in requested)
            )
            failed_count = sum(1 for result in results if not result.success)
            return self._wrap_result(
                CatalogEntityStatsBatchResult(
                    success=failed_count == 0,
                    message=(
                        f"Inspected {len(results)} entities; {failed_count} could not be resolved."
                    ),
                    catalog_connection_id=connection_id,
                    entities=list(results),
                    entities_count=len(results),
                    failed_count=failed_count,
                )
            )
        except Exception as exc:
            return self._wrap_result(
                CatalogEntityStatsBatchResult(
                    success=False,
                    message=f"Failed to inspect entity columns: {exc}",
                )
            )

    @tool_meta(
        CatalogSearchResult,
        display_name="Search Catalog Tables And Columns",
        strict=True,
        description=(
            "Search catalog tables and columns relevant to the request. "
            "Use this before SQL metadata statements such as SHOW TABLES or DESCRIBE. "
            "The `query` argument is required. "
            "Example: search_catalog(query='customer orders tables', limit=5)."
        ),
    )
    async def search_catalog(
        self, query: str, limit: int = 5, run_context: RuntimeToolContext | None = None
    ) -> str:
        """Search the semantic catalog index for relevant entities."""
        try:
            if not self.runtime_provider:
                raise ValueError("Runtime provider is required for catalog search")
            connection_id = await self._resolve_connection_id()
            service = self.runtime_provider.get_catalog_index_service(
                catalog_connection_id=connection_id,
            )
            if service is None:
                raise RuntimeError(
                    "Catalog search is unavailable in this runtime. "
                    "Use in-process/server runtime with vector dependencies enabled."
                )

            found_tables = await service.search(
                query=query,
                engine_type=self.engine_type or QueryEngineType.DUCKDB,
                limit=limit,
                catalog_connection_id=connection_id,
            )
            message = (
                f"Found {len(found_tables)} entities."
                if found_tables
                else "No relevant entities found."
            )
            return self._create_result(
                success=True,
                result_class=CatalogSearchResult,
                message=message,
                tables=found_tables,
            )
        except Exception as exc:
            return self._create_result(
                success=False,
                result_class=CatalogSearchResult,
                message="Search failed",
                error=str(exc),
            )

    @tool_meta(DiscoveryResult, display_name="Discover Data Context", emit_tool_call=True)
    async def discover(self, query: str, limit: int = 5) -> str:
        """Search tables, curated knowledge, and project documents in a single call.

        Prefer this to answer a discovery step that would otherwise require
        separate catalog, knowledge, and document search calls. Any source that
        is unavailable in the current runtime is skipped rather than failing the
        whole call.

        :param query: Natural language description of what you need.
        :param limit: Maximum results per source (default 5).
        """
        errors: dict[str, str] = {}

        async def search_tables() -> list[CatalogSearchItem]:
            try:
                if not self.runtime_provider:
                    raise RuntimeError("Runtime provider is required for catalog search")
                connection_id = await self._resolve_connection_id()
                service = self.runtime_provider.get_catalog_index_service(
                    catalog_connection_id=connection_id,
                )
                if service is None:
                    raise RuntimeError("Catalog search is unavailable in this runtime.")
                return await service.search(
                    query=query,
                    engine_type=self.engine_type or QueryEngineType.DUCKDB,
                    limit=limit,
                    catalog_connection_id=connection_id,
                )
            except Exception as exc:
                errors["tables"] = str(exc)
                return []

        async def search_concepts() -> list[OkfConcept]:
            try:
                service = (
                    self.runtime_provider.get_knowledge_service() if self.runtime_provider else None
                )
                if service is None:
                    raise RuntimeError("Curated knowledge is unavailable in this runtime.")
                return await service.search_concepts(query, limit=limit)
            except Exception as exc:
                errors["knowledge"] = str(exc)
                return []

        async def search_documents() -> list[DocumentSearchResult]:
            try:
                from kontext.catalog import DocumentIndexService
                from kontext.common.protocols import resolve_agent_runtime_storage_provider

                runtime_storage_provider = resolve_agent_runtime_storage_provider(
                    self.runtime_provider
                )
                service = DocumentIndexService(
                    project_id=self.project_id,
                    runtime_provider=runtime_storage_provider,
                )
                return await service.search(query, limit=limit)
            except Exception as exc:
                errors["documents"] = str(exc)
                return []

        tables, concepts, documents = await asyncio.gather(
            search_tables(), search_concepts(), search_documents()
        )

        return self._wrap_result(
            DiscoveryResult(
                success=bool(tables or concepts or documents) or not errors,
                message=(
                    f"Found {len(tables)} tables, {len(concepts)} curated concepts, "
                    f"and {len(documents)} document excerpts."
                ),
                query=query,
                tables=tables,
                concepts=concepts,
                documents=[
                    DocumentSearchItem(
                        source=item.source,
                        content=_truncate_text(item.content, _MAX_DOCUMENT_EXCERPT_CHARS) or "",
                        score=item.score,
                    )
                    for item in documents
                ],
                errors=errors or None,
            )
        )
