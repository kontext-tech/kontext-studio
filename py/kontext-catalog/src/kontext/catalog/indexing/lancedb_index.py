"""LanceDB-backed implementation of the provider-neutral knowledge index."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import logging
import re
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import pyarrow as pa

from kontext.common.knowledge.index import (
    FacetFilters,
    FacetValue,
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeSearchHit,
)

from .embedding import EmbeddingProvider, get_default_embedding_provider

try:
    import lancedb

    _LANCEDB_AVAILABLE = True
except ImportError:
    lancedb = None  # type: ignore[assignment]
    _LANCEDB_AVAILABLE = False

_FIELD_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_TABLE_NAME = "knowledge_corpus"
_RRF_K = 60
_USE_TANTIVY = importlib.util.find_spec("tantivy") is not None
_MIN_VECTOR_INDEX_ROWS = 256
logger = logging.getLogger(__name__)


class LanceDBKnowledgeIndex(KnowledgeIndex):
    """Hybrid dense + lexical search over a unified project corpus."""

    def __init__(
        self,
        storage_dir: str,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        table_name: str = _TABLE_NAME,
    ) -> None:
        self.storage_dir = storage_dir
        self.table_name = table_name
        self.embedding_provider = embedding_provider or get_default_embedding_provider()
        self._vector_dimensions: int | None = None

    def _get_vector_dimensions(self) -> int:
        if self._vector_dimensions is None:
            probe = self.embedding_provider.embed_query("dimension probe")
            if not probe:
                raise RuntimeError("Embedding provider returned an empty vector.")
            self._vector_dimensions = len(probe)
        return self._vector_dimensions

    def _schema(self) -> pa.Schema:
        vector_type = pa.list_(pa.float32(), self._get_vector_dimensions())
        return pa.schema(
            [
                pa.field("document_id", pa.string(), nullable=False),
                pa.field("title", pa.string()),
                pa.field("content", pa.string(), nullable=False),
                pa.field("vector", vector_type, nullable=False),
                pa.field("scope", pa.string(), nullable=False),
                pa.field("content_kind", pa.string(), nullable=False),
                pa.field("provider_kind", pa.string()),
                pa.field("connection_id", pa.string()),
                pa.field("namespace_name", pa.string()),
                pa.field("entity_id", pa.string()),
                pa.field("entity_name", pa.string()),
                pa.field("entity_type", pa.string()),
                pa.field("source_type", pa.string()),
                pa.field("source_id", pa.string()),
                pa.field("status", pa.string()),
                pa.field("updated_at", pa.string()),
                pa.field("metadata_json", pa.string()),
            ]
        )

    def _connect(self):
        if not _LANCEDB_AVAILABLE:
            raise RuntimeError("lancedb is required for the unified knowledge index.")
        Path(self.storage_dir).mkdir(parents=True, exist_ok=True)
        return lancedb.connect(self.storage_dir)  # type: ignore[union-attr]

    def _open_table(self, *, create: bool = False):
        db = self._connect()
        try:
            table = db.open_table(self.table_name)
            if create:
                migrated_table = self._migrate_table_vectors_if_needed(db, table)
                if migrated_table is not table:
                    return migrated_table, True
            return table, False
        except Exception:
            if not create:
                return None, False
        return (
            db.create_table(
                self.table_name,
                schema=self._schema(),
                mode="create",
                exist_ok=True,
            ),
            True,
        )

    def _get_table_vector_dimension(self, table: Any) -> int | None:
        try:
            field = table.schema.field("vector")
        except Exception:
            return None

        list_size = getattr(field.type, "list_size", None)
        if isinstance(list_size, int) and list_size > 0:
            return list_size
        return None

    def _serialize_row_with_vector(
        self,
        row: dict[str, Any],
        *,
        vector: Sequence[float],
    ) -> dict[str, Any]:
        return {
            "document_id": row.get("document_id"),
            "title": row.get("title"),
            "content": row.get("content") or "",
            "vector": [float(value) for value in vector],
            "scope": row.get("scope") or "",
            "content_kind": row.get("content_kind") or "",
            "provider_kind": row.get("provider_kind"),
            "connection_id": row.get("connection_id"),
            "namespace_name": row.get("namespace_name"),
            "entity_id": row.get("entity_id"),
            "entity_name": row.get("entity_name"),
            "entity_type": row.get("entity_type"),
            "source_type": row.get("source_type"),
            "source_id": row.get("source_id"),
            "status": row.get("status"),
            "updated_at": row.get("updated_at"),
            "metadata_json": row.get("metadata_json") or "{}",
        }

    def _migrate_table_vectors_if_needed(self, db: Any, table: Any) -> Any:
        existing_dimension = self._get_table_vector_dimension(table)
        current_dimension = self._get_vector_dimensions()
        if existing_dimension == current_dimension:
            return table

        logger.warning(
            "Rebuilding knowledge index table %s at %s because vector dimension changed from %s to %s",
            self.table_name,
            self.storage_dir,
            existing_dimension,
            current_dimension,
        )

        try:
            existing_rows = table.to_arrow().to_pylist()
        except Exception:
            existing_rows = []

        if existing_rows:
            vectors = self.embedding_provider.embed_documents(
                [str(row.get("content") or "") for row in existing_rows]
            )
            rebuilt_rows = [
                self._serialize_row_with_vector(row, vector=vector)
                for row, vector in zip(existing_rows, vectors, strict=True)
            ]
            db.create_table(
                self.table_name,
                data=rebuilt_rows,
                schema=self._schema(),
                mode="overwrite",
            )
        else:
            db.create_table(
                self.table_name,
                schema=self._schema(),
                mode="overwrite",
            )
        return db.open_table(self.table_name)

    def _list_indices(self, table: Any) -> list[Any]:
        try:
            return list(table.list_indices())
        except Exception:
            return []

    def _has_fts_index(self, table: Any) -> bool:
        return any(
            str(getattr(index, "index_type", "")).lower() == "fts"
            and "content" in list(getattr(index, "columns", []) or [])
            for index in self._list_indices(table)
        )

    def _has_vector_index(self, table: Any) -> bool:
        return any(
            "vector" in list(getattr(index, "columns", []) or [])
            and "ivf" in str(getattr(index, "index_type", "")).lower()
            for index in self._list_indices(table)
        )

    def _ensure_indexes(self, table: Any) -> None:
        try:
            row_count = int(table.count_rows())
        except Exception:
            row_count = 0
        if row_count <= 0:
            return

        if not self._has_fts_index(table):
            try:
                table.create_fts_index(
                    "content",
                    replace=False,
                    use_tantivy=_USE_TANTIVY,
                )
            except Exception:
                if _USE_TANTIVY:
                    with contextlib.suppress(Exception):
                        table.create_fts_index(
                            "content",
                            replace=False,
                            use_tantivy=False,
                        )

        if row_count < _MIN_VECTOR_INDEX_ROWS or self._has_vector_index(table):
            return

        with contextlib.suppress(Exception):
            # Vector search still works without an ANN index.
            table.create_index(
                vector_column_name="vector",
                replace=False,
            )

    def _delete_existing_documents(
        self,
        table: Any,
        documents: Sequence[KnowledgeDocument],
    ) -> None:
        document_ids = [document.document_id for document in documents if document.document_id]
        if not document_ids:
            return
        where = self._build_where_clause(document_ids=document_ids)
        if where:
            table.delete(where)

    def _serialize_document(
        self,
        document: KnowledgeDocument,
        *,
        vector: Sequence[float],
    ) -> dict[str, Any]:
        return {
            "document_id": document.document_id,
            "title": document.title,
            "content": document.content,
            "vector": [float(value) for value in vector],
            "scope": document.scope,
            "content_kind": document.content_kind,
            "provider_kind": document.provider_kind,
            "connection_id": document.connection_id,
            "namespace_name": document.namespace_name,
            "entity_id": document.entity_id,
            "entity_name": document.entity_name,
            "entity_type": document.entity_type,
            "source_type": document.source_type,
            "source_id": document.source_id,
            "status": document.status,
            "updated_at": document.updated_at,
            "metadata_json": json.dumps(document.metadata, default=str),
        }

    def upsert(self, documents: Sequence[KnowledgeDocument]) -> int:
        if not documents:
            return 0

        vectors = self.embedding_provider.embed_documents(
            [document.content for document in documents]
        )
        table, _ = self._open_table(create=True)
        assert table is not None

        self._delete_existing_documents(table, documents)
        rows = [
            self._serialize_document(document, vector=vector)
            for document, vector in zip(documents, vectors, strict=True)
        ]
        table.add(rows)
        self._ensure_indexes(table)
        return len(rows)

    def delete(
        self,
        document_ids: Sequence[str] | None = None,
        *,
        filters: FacetFilters | None = None,
    ) -> int:
        table, _ = self._open_table(create=False)
        if table is None:
            return 0

        where = self._build_where_clause(
            filters=filters,
            document_ids=document_ids,
        )
        if where is None:
            return 0

        deleted_count = int(table.count_rows(filter=where))
        if deleted_count > 0:
            table.delete(where)
        return deleted_count

    def clear_scope(self, scope: str, *, filters: FacetFilters | None = None) -> int:
        filter_values = dict(filters or {})
        filter_values["scope"] = scope
        return self.delete(filters=filter_values)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        filters: FacetFilters | None = None,
    ) -> list[KnowledgeSearchHit]:
        normalized_query = query.strip()
        if not normalized_query or limit <= 0:
            return []

        table, _ = self._open_table(create=False)
        if table is None:
            return []

        self._ensure_indexes(table)

        where = self._build_where_clause(filters=filters)
        candidate_limit = max(limit * 5, 20)

        vector_rows: list[dict[str, Any]] = []
        try:
            vector_builder = table.search(
                self.embedding_provider.embed_query(normalized_query),
                query_type="vector",
                vector_column_name="vector",
            )
            if where:
                vector_builder = vector_builder.where(where, prefilter=True)
            vector_rows = cast(
                list[dict[str, Any]], vector_builder.limit(candidate_limit).to_list()
            )
        except Exception:
            vector_rows = []

        lexical_rows: list[dict[str, Any]] = []
        try:
            lexical_builder = table.search(
                normalized_query,
                query_type="fts",
                fts_columns="content",
            )
            if where:
                lexical_builder = lexical_builder.where(where, prefilter=True)
            lexical_rows = cast(
                list[dict[str, Any]], lexical_builder.limit(candidate_limit).to_list()
            )
        except Exception:
            lexical_rows = []

        if not vector_rows and not lexical_rows:
            return []

        hit_rows: dict[str, dict[str, Any]] = {}
        hit_scores: dict[str, float] = defaultdict(float)
        vector_distances: dict[str, float] = {}
        lexical_scores: dict[str, float] = {}

        for rank, row in enumerate(vector_rows, start=1):
            document_id = str(row.get("document_id") or "")
            if not document_id:
                continue
            hit_rows[document_id] = row
            hit_scores[document_id] += 1.0 / (_RRF_K + rank)
            distance = row.get("_distance")
            if distance is not None:
                vector_distances[document_id] = float(distance)

        for rank, row in enumerate(lexical_rows, start=1):
            document_id = str(row.get("document_id") or "")
            if not document_id:
                continue
            hit_rows[document_id] = row
            hit_scores[document_id] += 1.0 / (_RRF_K + rank)
            lexical_score = row.get("_score")
            if lexical_score is not None:
                lexical_scores[document_id] = float(lexical_score)

        ordered_hits = sorted(
            hit_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]

        return [
            self._row_to_hit(
                hit_rows[document_id],
                score=score,
                vector_distance=vector_distances.get(document_id),
                lexical_score=lexical_scores.get(document_id),
            )
            for document_id, score in ordered_hits
        ]

    def _row_to_hit(
        self,
        row: dict[str, Any],
        *,
        score: float,
        vector_distance: float | None,
        lexical_score: float | None,
    ) -> KnowledgeSearchHit:
        metadata_json = row.get("metadata_json")
        metadata: dict[str, Any] = {}
        if metadata_json:
            try:
                metadata = json.loads(str(metadata_json))
            except json.JSONDecodeError:
                metadata = {"raw_metadata": str(metadata_json)}

        return KnowledgeSearchHit(
            document_id=str(row.get("document_id") or ""),
            title=str(row.get("title") or "") or None,
            content=str(row.get("content") or ""),
            score=float(score),
            scope=str(row.get("scope") or ""),
            content_kind=str(row.get("content_kind") or ""),
            provider_kind=self._optional_str(row.get("provider_kind")),
            connection_id=self._optional_str(row.get("connection_id")),
            namespace_name=self._optional_str(row.get("namespace_name")),
            entity_id=self._optional_str(row.get("entity_id")),
            entity_name=self._optional_str(row.get("entity_name")),
            entity_type=self._optional_str(row.get("entity_type")),
            source_type=self._optional_str(row.get("source_type")),
            source_id=self._optional_str(row.get("source_id")),
            status=self._optional_str(row.get("status")),
            updated_at=self._optional_str(row.get("updated_at")),
            vector_distance=vector_distance,
            lexical_score=lexical_score,
            metadata=metadata,
        )

    def _build_where_clause(
        self,
        *,
        filters: FacetFilters | None = None,
        document_ids: Sequence[str] | None = None,
    ) -> str | None:
        clauses: list[str] = []

        if document_ids:
            ids = [document_id for document_id in document_ids if document_id]
            if ids:
                clauses.append(self._in_clause("document_id", ids))

        for field_name, raw_value in (filters or {}).items():
            if not _FIELD_NAME_PATTERN.match(field_name):
                raise ValueError(f"Unsupported facet field: {field_name}")
            if isinstance(raw_value, Sequence) and not isinstance(raw_value, str):
                values = list(raw_value)
                if not values:
                    return "1 = 0"
                clauses.append(self._multi_value_clause(field_name, values))
            else:
                clauses.append(self._single_value_clause(field_name, cast(FacetValue, raw_value)))

        if not clauses:
            return None
        return " AND ".join(f"({clause})" for clause in clauses)

    def _single_value_clause(self, field_name: str, value: FacetValue) -> str:
        if value is None:
            return f"{field_name} IS NULL"
        return f"{field_name} = {self._quote(value)}"

    def _multi_value_clause(
        self,
        field_name: str,
        values: Sequence[FacetValue],
    ) -> str:
        non_null_values = [value for value in values if value is not None]
        has_null = any(value is None for value in values)
        clauses: list[str] = []
        if non_null_values:
            clauses.append(self._in_clause(field_name, non_null_values))
        if has_null:
            clauses.append(f"{field_name} IS NULL")
        if not clauses:
            return "1 = 0"
        return " OR ".join(f"({clause})" for clause in clauses)

    def _in_clause(self, field_name: str, values: Sequence[FacetValue]) -> str:
        quoted_values = ", ".join(self._quote(value) for value in values)
        return f"{field_name} IN ({quoted_values})"

    def _quote(self, value: FacetValue) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, int | float):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    def _optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value)
        return normalized or None
