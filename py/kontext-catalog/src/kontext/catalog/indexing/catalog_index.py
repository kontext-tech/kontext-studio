"""Catalog indexing and search services built on the unified knowledge index."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, cast
from uuid import UUID

from kontext.common.knowledge.index import (
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeSearchHit,
)
from kontext.common.protocols import (
    AgentRuntimeStorageProviderProtocol,
    JobRuntimeProviderProtocol,
)
from kontext.data import CatalogDataService, FileDataService
from kontext.schema import (
    CatalogConnection,
    CatalogEntityDetail,
    CatalogSearchItem,
    FileSchemaModel,
    FileStatsModel,
    QueryEngineType,
)

from .embedding import EmbeddingProvider
from .lancedb_index import LanceDBKnowledgeIndex
from .storage_paths import resolve_project_knowledge_storage_paths

try:
    # optional dependency: kontext-okf provides freshness/trust helpers
    from kontext.okf.trust import filter_fresh_hits
except Exception:  # pragma: no cover - optional import
    filter_fresh_hits = None

DEFAULT_SCHEMA_NAME = "default"
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
logger = logging.getLogger(__name__)


class CatalogIndexService:
    """Compatibility wrapper over the provider-neutral knowledge index."""

    def __init__(
        self,
        project_id: str,
        catalog_connection_id: str | None = None,
        runtime_provider: (
            AgentRuntimeStorageProviderProtocol | JobRuntimeProviderProtocol | None
        ) = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        self.project_id = str(project_id)
        self.catalog_connection_id = catalog_connection_id
        self._runtime_provider = runtime_provider
        storage_paths = resolve_project_knowledge_storage_paths(
            self.project_id,
            runtime_provider=self._get_storage_runtime_provider(runtime_provider),
        )
        self.vector_db_path = storage_paths.semantic_index_dir

        self._knowledge_index: KnowledgeIndex = LanceDBKnowledgeIndex(
            self.vector_db_path,
            embedding_provider=embedding_provider,
        )
        self._catalog_data_service = CatalogDataService(self.project_id)
        self._file_data_service = FileDataService(self.project_id)

    def _get_storage_runtime_provider(
        self,
        runtime_provider: (AgentRuntimeStorageProviderProtocol | JobRuntimeProviderProtocol | None),
    ) -> AgentRuntimeStorageProviderProtocol | None:
        from kontext.common.protocols import resolve_agent_runtime_storage_provider

        return resolve_agent_runtime_storage_provider(runtime_provider)

    def get_vector_client(self) -> LanceDBKnowledgeIndex:
        """Return the provider-neutral index wrapper for compatibility."""
        return cast(LanceDBKnowledgeIndex, self._knowledge_index)

    async def search(
        self,
        query: str,
        engine_type: QueryEngineType = QueryEngineType.DUCKDB,
        limit: int = 5,
        catalog_connection_id: str | None = None,
    ) -> list[CatalogSearchItem]:
        _ = engine_type
        resolved_connection_id = catalog_connection_id or self.catalog_connection_id
        raw_hits = await self.search_knowledge(
            query=query,
            limit=max(limit * 4, 10),
            scopes=["catalog"],
            filters={"connection_id": resolved_connection_id} if resolved_connection_id else None,
        )
        collapsed_hits = self._collapse_catalog_hits(raw_hits, limit=limit, query=query)
        logger.info(
            "Catalog search query=%r returned %d raw hits and %d ranked entities",
            query,
            len(raw_hits),
            len(collapsed_hits),
        )
        return collapsed_hits

    async def search_knowledge(
        self,
        *,
        query: str,
        limit: int = 5,
        scopes: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        apply_trust_gate: bool = True,
    ) -> list[KnowledgeSearchHit]:
        effective_filters = dict(filters or {})
        if scopes:
            effective_filters["scope"] = scopes if len(scopes) > 1 else scopes[0]
        hits = self._knowledge_index.search(
            query,
            limit=limit,
            filters=effective_filters or None,
        )
        if apply_trust_gate:
            hits = _apply_trust_gate(hits)
        return hits

    # _apply_trust_gate is defined at module bottom to avoid interrupting the
    # `CatalogIndexService` class body when this file is imported. See below.

    async def index_catalog_entities(
        self,
        *,
        connection: CatalogConnection,
        entities: list[CatalogEntityDetail],
        engine_type: QueryEngineType,
        recreate: bool = False,
    ) -> int:
        _ = engine_type
        if recreate:
            self._knowledge_index.clear_scope(
                "catalog",
                filters={"connection_id": connection.id} if connection.id else None,
            )

        source_links = await self._catalog_data_service.list_source_links_for_connection_async(
            connection.id or ""
        )
        links_by_entity: dict[str, list[Any]] = {}
        file_ids: list[UUID] = []
        for link in source_links:
            if link.entity_id is None:
                continue
            entity_key = str(link.entity_id)
            links_by_entity.setdefault(entity_key, []).append(link)
            if link.source_type == "file":
                try:
                    file_ids.append(UUID(str(link.source_id)))
                except ValueError:
                    continue

        files_by_id = {
            str(file_record.id): file_record
            for file_record in await self._file_data_service.get_files_by_ids_async(
                list(dict.fromkeys(file_ids))
            )
        }

        documents: list[KnowledgeDocument] = []
        for detail in entities:
            entity_links = links_by_entity.get(detail.entity.id, [])
            primary_link = entity_links[0] if entity_links else None
            entity_document = self._catalog_entity_document(
                connection=connection,
                detail=detail,
                source_link=primary_link,
            )
            documents.append(entity_document)
            documents.extend(
                self._catalog_column_documents(
                    connection=connection,
                    detail=detail,
                    entity_document=entity_document,
                    source_link=primary_link,
                )
            )
            documents.extend(
                self._catalog_file_profile_documents(
                    connection=connection,
                    detail=detail,
                    entity_document=entity_document,
                    source_links=entity_links,
                    files_by_id=files_by_id,
                )
            )

        if documents:
            self._knowledge_index.upsert(documents)

        return len(documents)

    async def index_knowledge(self, *, recreate: bool = False) -> int:
        """Index all OKF concepts into the unified ``knowledge`` scope.

        Reads from the project's durable OKF concept store (the ``.okf`` bundle
        directory) and projects each concept into the knowledge index via
        :func:`concept_to_index_document`. This is the single knowledge source
        for human-authored and agent-proposed concepts.

        When ``recreate`` is set, the entire ``knowledge`` scope is cleared first
        so the index is rebuilt from scratch. Returns the number of documents
        upserted.
        """
        return await asyncio.to_thread(self._index_knowledge_sync, recreate)

    def _index_knowledge_sync(self, recreate: bool) -> int:
        if recreate:
            self._knowledge_index.clear_scope("knowledge")
        return self.index_okf_concepts()

    def index_okf_concepts(self, concepts: list[Any] | None = None) -> int:
        """Project OKF concepts from the durable store into the knowledge index.

        When ``concepts`` is ``None`` (the common case), concepts are read from
        the project's :class:`OkfConceptStore` (the ``.okf`` bundle). Pass an
        explicit list to project a freshly-drafted set without persisting first
        (used by the enrichment job, which persists then indexes).
        """
        from kontext.okf import OkfConceptStore, concept_to_index_document

        if concepts is None:
            concepts = OkfConceptStore.for_project(self.project_id).list_concepts()
        if not concepts:
            return 0
        documents = [concept_to_index_document(concept) for concept in concepts]
        return self._knowledge_index.upsert(documents)

    def _catalog_entity_document(
        self,
        *,
        connection: CatalogConnection,
        detail: CatalogEntityDetail,
        source_link: Any | None,
    ) -> KnowledgeDocument:
        entity = detail.entity
        full_name = f"{entity.namespace_name}.{entity.entity_name}"
        columns_desc = ", ".join(
            f"{column.name} ({column.data_type or 'UNKNOWN'})" for column in detail.columns
        )
        metadata_bits = ""
        if entity.metadata:
            metadata_bits = "\nMetadata: " + json.dumps(
                entity.metadata, default=str, sort_keys=True
            )
        content = (
            f"Entity: {full_name}\n"
            f"Connection: {connection.display_name}\n"
            f"Type: {entity.entity_type.value}\n"
            f"Description: {entity.description or ''}\n"
            f"Row Count: {entity.row_count if entity.row_count is not None else 'unknown'}\n"
            f"Columns: {columns_desc}{metadata_bits}"
        )
        return KnowledgeDocument(
            document_id=f"catalog:entity:{entity.id}",
            title=full_name,
            content=content,
            scope="catalog",
            content_kind="entity_summary",
            provider_kind=connection.provider_kind.value,
            connection_id=connection.id,
            namespace_name=entity.namespace_name,
            entity_id=entity.id,
            entity_name=entity.entity_name,
            entity_type=entity.entity_type.value,
            source_type=source_link.source_type if source_link is not None else None,
            source_id=(
                str(source_link.source_id)
                if source_link is not None and source_link.source_id is not None
                else None
            ),
            status=connection.last_sync_status or "active",
            updated_at=(
                connection.last_synced_at.isoformat()
                if connection.last_synced_at is not None
                else None
            ),
            metadata={
                "connection_name": connection.display_name,
                "entity_content": content,
                "entity_description": entity.description or "",
                "entity_metadata": entity.metadata,
            },
        )

    def _catalog_column_documents(
        self,
        *,
        connection: CatalogConnection,
        detail: CatalogEntityDetail,
        entity_document: KnowledgeDocument,
        source_link: Any | None,
    ) -> list[KnowledgeDocument]:
        documents: list[KnowledgeDocument] = []
        entity = detail.entity
        full_name = f"{entity.namespace_name}.{entity.entity_name}"
        for column in detail.columns:
            content = (
                f"Column: {column.name}\n"
                f"Entity: {full_name}\n"
                f"Connection: {connection.display_name}\n"
                f"Data Type: {column.data_type or 'UNKNOWN'}\n"
                f"Nullable: {column.nullable}\n"
                f"Description: {column.description or ''}"
            )
            documents.append(
                KnowledgeDocument(
                    document_id=f"catalog:column:{entity.id}:{column.id or column.name}",
                    title=f"{full_name}.{column.name}",
                    content=content,
                    scope="catalog",
                    content_kind="column_metadata",
                    provider_kind=connection.provider_kind.value,
                    connection_id=connection.id,
                    namespace_name=entity.namespace_name,
                    entity_id=entity.id,
                    entity_name=entity.entity_name,
                    entity_type=entity.entity_type.value,
                    source_type=(source_link.source_type if source_link is not None else None),
                    source_id=(
                        str(source_link.source_id)
                        if source_link is not None and source_link.source_id is not None
                        else None
                    ),
                    status=connection.last_sync_status or "active",
                    updated_at=entity_document.updated_at,
                    metadata={
                        "connection_name": connection.display_name,
                        "column_name": column.name,
                        "entity_content": entity_document.content,
                        "entity_description": detail.entity.description or "",
                    },
                )
            )
        return documents

    def _catalog_file_profile_documents(
        self,
        *,
        connection: CatalogConnection,
        detail: CatalogEntityDetail,
        entity_document: KnowledgeDocument,
        source_links: list[Any],
        files_by_id: dict[str, Any],
    ) -> list[KnowledgeDocument]:
        documents: list[KnowledgeDocument] = []
        entity = detail.entity
        for source_link in source_links:
            if source_link.source_type != "file" or source_link.source_id is None:
                continue
            file_record = files_by_id.get(str(source_link.source_id))
            if file_record is None:
                continue

            schema_model = self._parse_file_schema(file_record.schema_definition)
            stats_model = self._parse_file_stats(file_record.statistics_data)
            if (
                schema_model is None
                and stats_model is None
                and file_record.row_count is None
                and file_record.column_count is None
            ):
                continue

            full_name = f"{entity.namespace_name}.{entity.entity_name}"
            lines = [
                f"File Profile: {file_record.name}",
                f"Linked Entity: {full_name}",
                f"Connection: {connection.display_name}",
                f"File Type: {file_record.file_type}",
            ]
            if file_record.uri:
                lines.append(f"File URI: {file_record.uri}")
            if file_record.row_count is not None:
                lines.append(f"Row Count: {file_record.row_count}")
            if file_record.column_count is not None:
                lines.append(f"Column Count: {file_record.column_count}")
            if schema_model is not None:
                lines.extend(self._schema_lines(schema_model))
            if stats_model is not None:
                lines.extend(self._stats_lines(stats_model))

            documents.append(
                KnowledgeDocument(
                    document_id=f"catalog:file_profile:{entity.id}:{file_record.id}",
                    title=f"{full_name}::{file_record.name}",
                    content="\n".join(lines),
                    scope="catalog",
                    content_kind="file_profile",
                    provider_kind=connection.provider_kind.value,
                    connection_id=connection.id,
                    namespace_name=entity.namespace_name,
                    entity_id=entity.id,
                    entity_name=entity.entity_name,
                    entity_type=entity.entity_type.value,
                    source_type="file",
                    source_id=str(file_record.id),
                    status=connection.last_sync_status or "active",
                    updated_at=entity_document.updated_at,
                    metadata={
                        "connection_name": connection.display_name,
                        "file_name": file_record.name,
                        "file_uri": file_record.uri,
                        "entity_content": entity_document.content,
                        "entity_description": detail.entity.description or "",
                    },
                )
            )
        return documents

    def _schema_lines(self, schema_model: FileSchemaModel) -> list[str]:
        lines: list[str] = []
        for sub_schema in schema_model.sub_schemas[:5]:
            columns_desc = ", ".join(
                f"{column.name} ({column.physical_type})" for column in sub_schema.columns or []
            )
            label = sub_schema.table_name or "table"
            lines.append(f"Schema[{label}]: {columns_desc}")
        return lines

    def _stats_lines(self, stats_model: FileStatsModel) -> list[str]:
        lines: list[str] = []
        for sub_stats in stats_model.sub_schemas[:5]:
            label = getattr(sub_stats, "table_name", None) or "table"
            row_count = getattr(sub_stats, "estimated_row_count", None)
            lines.append(f"Stats[{label}]: estimated_row_count={row_count}")
        if stats_model.warnings:
            lines.append("Warnings: " + "; ".join(stats_model.warnings[:5]))
        return lines

    def _parse_file_schema(self, raw_value: str | None) -> FileSchemaModel | None:
        if not raw_value:
            return None
        try:
            return FileSchemaModel.model_validate_json(raw_value)
        except Exception:
            return None

    def _parse_file_stats(self, raw_value: str | None) -> FileStatsModel | None:
        if not raw_value:
            return None
        try:
            return FileStatsModel.model_validate_json(raw_value)
        except Exception:
            return None

    def _collapse_catalog_hits(
        self,
        hits: list[KnowledgeSearchHit],
        *,
        limit: int,
        query: str,
    ) -> list[CatalogSearchItem]:
        grouped: dict[str, KnowledgeSearchHit] = {}
        best_scores: dict[str, float] = {}

        for hit in hits:
            group_key = (
                hit.entity_id or f"{hit.connection_id}:{hit.namespace_name}:{hit.entity_name}"
            )
            best_score = best_scores.get(group_key)
            if best_score is None or hit.score > best_score:
                grouped[group_key] = hit
                best_scores[group_key] = hit.score

        grouped_hits = list(grouped.values())
        if not grouped_hits:
            return []

        scored_hits = self._score_catalog_hits(grouped_hits, query=query)
        if not scored_hits:
            return []

        top_score = scored_hits[0][1]
        ranked_hits: list[tuple[KnowledgeSearchHit, float]] = []
        short_table_like_query = self._is_short_table_like_query(query)
        short_query_token_count = len(self._normalize_catalog_text(query).split())
        for hit, relevance_score in scored_hits:
            name_match = self._has_name_match(hit, query=query)
            column_match = self._has_column_match(hit, query=query)
            token_overlap = self._token_overlap_ratio(hit, query=query)
            strict_token_overlap = self._strict_token_overlap_ratio(hit, query=query)
            keep_hit = relevance_score >= max(30.0, top_score * 0.45)
            if short_table_like_query:
                overlap_gate = (
                    strict_token_overlap if short_query_token_count == 1 else token_overlap
                )
                keep_hit = keep_hit and (name_match or column_match or overlap_gate >= 0.5)
            elif name_match or column_match or token_overlap >= 0.5:
                keep_hit = True

            if keep_hit:
                ranked_hits.append((hit, relevance_score))
            if len(ranked_hits) >= limit:
                break

        return [
            self._catalog_item_from_hit(hit, score=relevance_score, rank=index)
            for index, (hit, relevance_score) in enumerate(ranked_hits, start=1)
        ]

    def _catalog_item_from_hit(
        self,
        hit: KnowledgeSearchHit,
        *,
        score: float,
        rank: int,
    ) -> CatalogSearchItem:
        entity_content = str(hit.metadata.get("entity_content") or hit.content)
        raw_description = str(hit.metadata.get("entity_description") or "")
        description = raw_description or entity_content[:200]
        if len(entity_content) > 200 and not raw_description:
            description += "..."

        return CatalogSearchItem(
            schema_name=hit.namespace_name or DEFAULT_SCHEMA_NAME,
            table_name=hit.entity_name or hit.title or "",
            description=description,
            content=entity_content,
            score=score,
            rank=rank,
            connection_id=hit.connection_id,
            connection_name=str(hit.metadata.get("connection_name") or "")
            if hit.metadata.get("connection_name")
            else None,
            entity_id=hit.entity_id,
            entity_type=hit.entity_type,
        )

    def _score_catalog_hits(
        self,
        hits: list[KnowledgeSearchHit],
        *,
        query: str,
    ) -> list[tuple[KnowledgeSearchHit, float]]:
        top_raw_score = max((hit.score for hit in hits), default=0.0)
        ranked_hits: list[tuple[KnowledgeSearchHit, float]] = []

        for hit in hits:
            relative_raw = (hit.score / top_raw_score) if top_raw_score > 0 else 0.0
            score = min(relative_raw, 1.0) * 35.0

            if self._is_exact_full_name_match(hit, query=query):
                score += 55.0
            elif self._is_exact_name_match(hit, query=query):
                score += 50.0
            elif self._has_name_match(hit, query=query):
                score += 25.0

            score += 10.0 * self._token_overlap_ratio(hit, query=query)

            if self._has_column_match(hit, query=query):
                score += 12.0

            if hit.content_kind == "entity_summary":
                score += 3.0

            ranked_hits.append((hit, round(score, 2)))

        ranked_hits.sort(key=lambda item: item[1], reverse=True)
        return ranked_hits

    def _is_short_table_like_query(self, query: str) -> bool:
        normalized_query = self._normalize_catalog_text(query)
        if not normalized_query:
            return False
        return len(normalized_query.split()) <= 3 and len(normalized_query) <= 32

    def _is_exact_name_match(self, hit: KnowledgeSearchHit, *, query: str) -> bool:
        query_compact = self._compact_catalog_text(query)
        entity_compact = self._compact_catalog_text(hit.entity_name or hit.title or "")
        return bool(query_compact and query_compact == entity_compact)

    def _is_exact_full_name_match(self, hit: KnowledgeSearchHit, *, query: str) -> bool:
        entity_name = hit.entity_name or hit.title or ""
        full_name = (
            f"{hit.namespace_name}.{entity_name}"
            if hit.namespace_name and entity_name
            else entity_name
        )
        query_compact = self._compact_catalog_text(query)
        full_compact = self._compact_catalog_text(full_name)
        return bool(query_compact and query_compact == full_compact)

    def _has_name_match(self, hit: KnowledgeSearchHit, *, query: str) -> bool:
        query_compact = self._compact_catalog_text(query)
        entity_compact = self._compact_catalog_text(hit.entity_name or hit.title or "")
        return bool(query_compact and entity_compact and query_compact in entity_compact)

    def _has_column_match(self, hit: KnowledgeSearchHit, *, query: str) -> bool:
        column_name = str(hit.metadata.get("column_name") or "")
        if not column_name:
            return False
        query_tokens = self._normalize_catalog_text(query).split()
        normalized_column = self._normalize_catalog_text(column_name)
        return any(token and token in normalized_column for token in query_tokens)

    def _token_overlap_ratio(self, hit: KnowledgeSearchHit, *, query: str) -> float:
        query_tokens = set(self._normalize_catalog_text(query).split())
        if not query_tokens:
            return 0.0

        entity_tokens = set()
        for candidate in (
            hit.entity_name or hit.title or "",
            str(hit.metadata.get("entity_description") or ""),
        ):
            entity_tokens.update(self._normalize_catalog_text(candidate).split())
        if not entity_tokens:
            return 0.0

        return len(query_tokens & entity_tokens) / len(query_tokens)

    def _strict_token_overlap_ratio(self, hit: KnowledgeSearchHit, *, query: str) -> float:
        query_tokens = set(self._normalize_catalog_text(query).split())
        if not query_tokens:
            return 0.0

        entity_name_tokens = set(
            self._normalize_catalog_text(hit.entity_name or hit.title or "").split()
        )
        if not entity_name_tokens:
            return 0.0

        return len(query_tokens & entity_name_tokens) / len(query_tokens)

    def _normalize_catalog_text(self, value: str) -> str:
        normalized = _NON_ALNUM_PATTERN.sub(" ", value.lower()).strip()
        return " ".join(part for part in normalized.split() if part)

    def _compact_catalog_text(self, value: str) -> str:
        return self._normalize_catalog_text(value).replace(" ", "")


def _apply_trust_gate(hits: list[KnowledgeSearchHit]) -> list[KnowledgeSearchHit]:
    """Apply OKF freshness/trust filtering to a list of KnowledgeSearchHit items.

    This uses kontext.okf.trust.filter_fresh_hits when available. If the OKF
    helper is not importable, the function is a no-op and returns the original
    hits unchanged.
    """
    if filter_fresh_hits is None:
        return hits

    try:
        fresh_meta_list = filter_fresh_hits([hit.metadata for hit in hits])
    except Exception:
        logger.exception("Failed to apply OKF trust gate; returning all hits")
        return hits

    # Build a set of identity markers of fresh metadata entries. We prefer
    # matching by 'source_id' or 'external_id' when available; otherwise fall
    # back to identity of the metadata mapping.
    fresh_keys = set()
    for meta in fresh_meta_list:
        sid = meta.get("source_id") or meta.get("external_id")
        if sid is not None:
            fresh_keys.add(str(sid))
        else:
            fresh_keys.add(id(meta))

    fresh_hits: list[KnowledgeSearchHit] = []
    for hit in hits:
        meta = hit.metadata
        sid = meta.get("source_id") or meta.get("external_id")
        if (
            (sid is not None and str(sid) in fresh_keys)
            or id(meta) in fresh_keys
            or meta in fresh_meta_list
        ):
            fresh_hits.append(hit)

    return fresh_hits
