from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from kontext.catalog import LanceDBKnowledgeIndex, LocalHashEmbedding
from kontext.common.knowledge.index import KnowledgeDocument


class _FixedEmbedding:
    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        seed = float((len(text) % 7) + 1)
        return [seed] * self.dimensions


def _doc(
    document_id: str,
    *,
    content: str,
    scope: str,
    content_kind: str,
    source_id: str | None = None,
) -> KnowledgeDocument:
    return KnowledgeDocument(
        document_id=document_id,
        title=document_id,
        content=content,
        scope=scope,
        content_kind=content_kind,
        source_id=source_id,
        status="active",
        updated_at=datetime.now(UTC).isoformat(),
    )


def test_lancedb_knowledge_index_supports_hybrid_search_and_scope_filters(
    tmp_path,
) -> None:
    index = LanceDBKnowledgeIndex(
        str(tmp_path / "vector-db"),
        embedding_provider=LocalHashEmbedding(),
    )
    index.upsert(
        [
            _doc(
                "catalog:customers",
                content="Entity raw.customers with columns customer_id and email",
                scope="catalog",
                content_kind="entity_summary",
            ),
            _doc(
                "document:readme",
                content="README notes about revenue forecasting and project goals",
                scope="document",
                content_kind="doc_chunk",
                source_id="README.md",
            ),
            _doc(
                "knowledge:curated",
                content="Curated note about lakehouse metadata conventions",
                scope="knowledge",
                content_kind="curated_note",
            ),
        ]
    )

    catalog_hits = index.search(
        "customer email",
        limit=5,
        filters={"scope": "catalog"},
    )
    assert len(catalog_hits) == 1
    assert catalog_hits[0].document_id == "catalog:customers"
    assert catalog_hits[0].scope == "catalog"

    knowledge_hits = index.search(
        "metadata conventions",
        limit=5,
        filters={"scope": ["knowledge", "document"]},
    )
    assert len(knowledge_hits) >= 1
    assert knowledge_hits[0].scope in {"knowledge", "document"}


def test_lancedb_knowledge_index_clear_scope_is_scoped(tmp_path) -> None:
    index = LanceDBKnowledgeIndex(
        str(tmp_path / "vector-db"),
        embedding_provider=LocalHashEmbedding(),
    )
    index.upsert(
        [
            _doc(
                "catalog:orders",
                content="Entity raw.orders with total amount",
                scope="catalog",
                content_kind="entity_summary",
            ),
            _doc(
                "document:notes",
                content="Important project notes about order processing",
                scope="document",
                content_kind="doc_chunk",
                source_id="notes.txt",
            ),
        ]
    )

    deleted_count = index.clear_scope("document")
    assert deleted_count == 1

    assert index.search("project notes", filters={"scope": "document"}) == []
    remaining_hits = index.search("total amount", filters={"scope": "catalog"})
    assert len(remaining_hits) == 1
    assert remaining_hits[0].document_id == "catalog:orders"


def test_lancedb_knowledge_index_does_not_rebuild_indexes_on_incremental_upsert(
    tmp_path,
) -> None:
    index = LanceDBKnowledgeIndex(
        str(tmp_path / "vector-db"),
        embedding_provider=LocalHashEmbedding(),
    )
    index.upsert(
        [
            _doc(
                "catalog:customers",
                content="Entity raw.customers with customer email",
                scope="catalog",
                content_kind="entity_summary",
            )
        ]
    )

    table, _ = index._open_table(create=False)
    assert table is not None

    with (
        patch.object(table, "create_fts_index") as mock_create_fts_index,
        patch.object(table, "create_index") as mock_create_index,
        patch.object(index, "_open_table", return_value=(table, False)),
    ):
        index.upsert(
            [
                _doc(
                    "catalog:orders",
                    content="Entity raw.orders with order total",
                    scope="catalog",
                    content_kind="entity_summary",
                )
            ]
        )

    mock_create_fts_index.assert_not_called()
    mock_create_index.assert_not_called()


def test_lancedb_knowledge_index_rebuilds_vectors_when_dimension_changes(
    tmp_path,
) -> None:
    storage_dir = str(tmp_path / "vector-db")

    old_index = LanceDBKnowledgeIndex(
        storage_dir,
        embedding_provider=_FixedEmbedding(384),
    )
    old_index.upsert(
        [
            _doc(
                "document:notes",
                content="Project notes about lakehouse metadata",
                scope="document",
                content_kind="doc_chunk",
                source_id="notes.txt",
            )
        ]
    )

    new_index = LanceDBKnowledgeIndex(
        storage_dir,
        embedding_provider=_FixedEmbedding(256),
    )
    new_index.upsert(
        [
            _doc(
                "catalog:customers",
                content="Entity raw.customers with customer email",
                scope="catalog",
                content_kind="entity_summary",
            )
        ]
    )

    table, _ = new_index._open_table(create=False)
    assert table is not None
    assert table.schema.field("vector").type.list_size == 256
    assert int(table.count_rows()) == 2

    hits = new_index.search("lakehouse metadata", limit=5)
    assert {hit.document_id for hit in hits} >= {
        "document:notes",
        "catalog:customers",
    }
