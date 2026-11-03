"""Tests for DocumentIndexService."""

import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest

from kontext.catalog import LocalHashEmbedding
from kontext.catalog.indexing.document_index import (
    DocumentIndexingOutcome,
    DocumentIndexService,
    DocumentSearchResult,
    _chunk_text,
)
from kontext.common.knowledge.index import KnowledgeIndex, KnowledgeSearchHit
from kontext.common.protocols import (
    AgentRuntimeStorageConfig,
    AgentRuntimeStorageProviderProtocol,
)


@pytest.fixture
def temp_workspace():
    temp_dir = tempfile.mkdtemp()
    with patch("kontext.catalog.indexing.storage_paths.get_project_vector_db_path") as mock_vdb:
        mock_vdb.return_value = str(Path(temp_dir) / "vector_db")
        yield temp_dir
    shutil.rmtree(temp_dir)


class TestChunking:
    def test_short_text_single_chunk(self):
        chunks = _chunk_text("short text", chunk_size=100, overlap=20)
        assert chunks == ["short text"]

    def test_long_text_multiple_chunks(self):
        text = "a" * 200
        chunks = _chunk_text(text, chunk_size=80, overlap=20)
        assert len(chunks) > 1
        # Each chunk should be at most chunk_size chars
        for ch in chunks:
            assert len(ch) <= 80

    def test_overlap_present(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        chunks = _chunk_text(text, chunk_size=10, overlap=3)
        assert len(chunks) > 1
        # The end of chunk[0] should overlap with the start of chunk[1]
        assert chunks[0][-3:] == chunks[1][:3]

    def test_empty_text(self):
        chunks = _chunk_text("", chunk_size=10, overlap=3)
        assert chunks == [""]


class TestDocumentIndexService:
    def test_runtime_provider_storage_path_overrides_default(self, temp_workspace):
        runtime_vector_path = str(Path(temp_workspace) / "runtime_vector_db")

        storage_service = SimpleNamespace(
            get_storage_config=lambda project_id: AgentRuntimeStorageConfig(
                scratchboard_dir=f"/tmp/{project_id}/scratchboard",
                semantic_index_dir=runtime_vector_path,
            )
        )
        runtime_provider = cast(
            AgentRuntimeStorageProviderProtocol,
            SimpleNamespace(get_agent_runtime_storage_service=lambda: storage_service),
        )

        svc = DocumentIndexService(
            project_id="test-project-runtime",
            runtime_provider=runtime_provider,
            embedding_provider=LocalHashEmbedding(),
        )

        assert svc.vector_db_path == runtime_vector_path

    @pytest.mark.asyncio
    async def test_index_and_search(self, temp_workspace):
        svc = DocumentIndexService(
            project_id="test-project-1",
            embedding_provider=LocalHashEmbedding(),
        )
        count = await svc.index_text("readme.md", "Revenue grew 15% in Q3 2024.")
        assert count >= 1

        results = await svc.search("revenue growth", limit=3)
        assert len(results) >= 1
        assert isinstance(results[0], DocumentSearchResult)
        assert results[0].source == "readme.md"

    @pytest.mark.asyncio
    async def test_delete_source(self, temp_workspace):
        svc = DocumentIndexService(
            project_id="test-project-2",
            embedding_provider=LocalHashEmbedding(),
        )
        await svc.index_text("notes.txt", "Some important notes about the project.")
        await svc.delete_source("notes.txt")

        results = await svc.search("important notes", limit=3)
        # After deletion, should return empty or no match for that source
        matching = [r for r in results if r.source == "notes.txt"]
        assert len(matching) == 0

    @pytest.mark.asyncio
    async def test_search_empty_index(self, temp_workspace):
        svc = DocumentIndexService(
            project_id="test-project-3",
            embedding_provider=LocalHashEmbedding(),
        )
        results = await svc.search("anything", limit=5)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_preserves_backend_scores(self, temp_workspace):
        svc = DocumentIndexService(
            project_id="test-project-score",
            embedding_provider=LocalHashEmbedding(),
        )
        svc._knowledge_index = cast(
            KnowledgeIndex,
            SimpleNamespace(
                search=lambda query, limit, filters: [
                    KnowledgeSearchHit(
                        document_id="document:1",
                        content="Lakehouse conventions",
                        score=0.25,
                        scope="document",
                        content_kind="doc_chunk",
                        source_type="project_file",
                        source_id="file:file-1",
                        title="notes.txt",
                        metadata={"file_name": "notes.txt"},
                    )
                ]
            ),
        )

        results = await svc.search("lakehouse", limit=1)

        assert results == [
            DocumentSearchResult(
                source="notes.txt",
                content="Lakehouse conventions",
                score=0.25,
            )
        ]

    @pytest.mark.asyncio
    async def test_index_project_file_adds_file_metadata(self, temp_workspace):
        svc = DocumentIndexService(
            project_id="test-project-4",
            embedding_provider=LocalHashEmbedding(),
        )

        outcome = await svc.index_project_file(
            file_id="file-123",
            file_name="notes.md",
            content_type="text/markdown",
            file_type="Markdown",
            content_bytes=b"# Notes\nRevenue grew 15% in Q3 2024.\n",
            updated_at="2026-04-29T00:00:00+00:00",
        )

        assert isinstance(outcome, DocumentIndexingOutcome)
        assert outcome.chunks_indexed >= 1
        hits = svc._knowledge_index.search(
            "Revenue",
            limit=5,
            filters={"scope": "document", "source_id": "file:file-123"},
        )
        assert len(hits) >= 1
        assert hits[0].source_type == "project_file"
        assert hits[0].metadata["file_id"] == "file-123"
        assert hits[0].metadata["file_name"] == "notes.md"
        assert hits[0].metadata["parser_name"] == "direct_utf8"

    @pytest.mark.asyncio
    async def test_delete_project_file_removes_rows(self, temp_workspace):
        svc = DocumentIndexService(
            project_id="test-project-5",
            embedding_provider=LocalHashEmbedding(),
        )
        await svc.index_project_file(
            file_id="file-456",
            file_name="guide.txt",
            content_type="text/plain",
            file_type="Text",
            content_bytes=b"Lakehouse guide for analysts.",
        )

        await svc.delete_project_file("file-456")

        hits = svc._knowledge_index.search(
            "Lakehouse",
            limit=5,
            filters={"scope": "document", "source_id": "file:file-456"},
        )
        assert hits == []
