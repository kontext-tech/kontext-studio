"""Project document indexing over the unified knowledge index."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from kontext.common.knowledge.index import KnowledgeDocument, KnowledgeIndex
from kontext.common.protocols import AgentRuntimeStorageProviderProtocol

from .document_extractor import DocumentExtractor, is_indexable_document_upload
from .embedding import EmbeddingProvider
from .lancedb_index import LanceDBKnowledgeIndex
from .storage_paths import resolve_project_knowledge_storage_paths

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_CHUNK_OVERLAP = 200
_PROJECT_FILE_SOURCE_TYPE = "project_file"


def _chunk_text(
    text: str,
    chunk_size: int = _DEFAULT_CHUNK_SIZE,
    overlap: int = _DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split *text* into overlapping windows of roughly *chunk_size* chars."""
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


@dataclass
class DocumentSearchResult:
    """A single hit returned by :meth:`DocumentIndexService.search`."""

    source: str
    content: str
    score: float | None = None


@dataclass(frozen=True)
class DocumentIndexingOutcome:
    """Outcome of indexing or removing a project-backed document source."""

    source_id: str
    chunks_indexed: int = 0
    parser_name: str | None = None
    skip_reason: str | None = None
    error_message: str | None = None


def _normalize_file_type_value(file_type: Any) -> str | None:
    if file_type is None:
        return None
    return str(getattr(file_type, "value", file_type))


def _project_file_source_id(file_id: str) -> str:
    return f"file:{file_id}"


class DocumentIndexService:
    """Document index wrapper backed by the unified LanceDB corpus."""

    def __init__(
        self,
        project_id: str,
        *,
        extractor: DocumentExtractor | None = None,
        runtime_provider: AgentRuntimeStorageProviderProtocol | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.project_id = str(project_id)
        storage_paths = resolve_project_knowledge_storage_paths(
            self.project_id,
            runtime_provider=runtime_provider,
        )
        self.vector_db_path = storage_paths.semantic_index_dir
        self._knowledge_index: KnowledgeIndex = LanceDBKnowledgeIndex(
            self.vector_db_path,
            embedding_provider=embedding_provider,
        )
        self._extractor = extractor or DocumentExtractor()

    def is_project_file_indexable(
        self,
        *,
        file_name: str | None,
        content_type: str | None,
        file_type: Any = None,
    ) -> bool:
        return is_indexable_document_upload(
            filename=file_name,
            content_type=content_type,
            file_type=file_type,
        )

    async def index_text(
        self,
        source: str,
        text: str,
        *,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_CHUNK_OVERLAP,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if not text.strip():
            return 0

        return self._upsert_source(
            title=source,
            text=text,
            source_type="document",
            source_id=source,
            chunk_size=chunk_size,
            overlap=overlap,
            metadata={
                **(metadata or {}),
                "source": source,
            },
        )

    async def index_project_file(
        self,
        *,
        file_id: str,
        file_name: str,
        content_type: str | None,
        file_type: Any = None,
        content_bytes: bytes,
        updated_at: str | None = None,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_CHUNK_OVERLAP,
    ) -> DocumentIndexingOutcome:
        normalized_file_id = str(file_id)
        source_id = _project_file_source_id(normalized_file_id)
        # LanceDB is only the storage/search backend. Parsing always happens
        # through DocumentExtractor before we upsert document chunks.
        extracted = self._extractor.extract(
            file_name,
            content_type,
            content_bytes,
            file_type=file_type,
        )

        if extracted.error_message:
            return DocumentIndexingOutcome(
                source_id=source_id,
                parser_name=extracted.parser_name,
                error_message=extracted.error_message,
            )

        if extracted.skip_reason or not extracted.text:
            await self.delete_project_file(normalized_file_id)
            return DocumentIndexingOutcome(
                source_id=source_id,
                parser_name=extracted.parser_name,
                skip_reason=extracted.skip_reason or "extracted text is empty",
            )

        resolved_updated_at = updated_at or datetime.now(UTC).isoformat()
        chunks_indexed = self._upsert_source(
            title=file_name,
            text=extracted.text,
            source_type=_PROJECT_FILE_SOURCE_TYPE,
            source_id=source_id,
            chunk_size=chunk_size,
            overlap=overlap,
            updated_at=resolved_updated_at,
            metadata={
                "source": file_name,
                "file_id": normalized_file_id,
                "file_name": file_name,
                "content_type": content_type,
                "file_type": _normalize_file_type_value(file_type),
                "parser_name": extracted.parser_name,
                "updated_at": resolved_updated_at,
            },
        )
        return DocumentIndexingOutcome(
            source_id=source_id,
            chunks_indexed=chunks_indexed,
            parser_name=extracted.parser_name,
        )

    def _upsert_source(
        self,
        *,
        title: str,
        text: str,
        source_type: str,
        source_id: str,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_CHUNK_OVERLAP,
        updated_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        chunks = _chunk_text(text, chunk_size, overlap)
        if not chunks:
            return 0

        resolved_updated_at = updated_at or datetime.now(UTC).isoformat()
        self._knowledge_index.delete(
            filters={
                "scope": "document",
                "source_type": source_type,
                "source_id": source_id,
            }
        )
        documents = [
            KnowledgeDocument(
                document_id=f"document:{source_type}:{source_id}:chunk:{index}",
                title=title,
                content=chunk,
                scope="document",
                content_kind="doc_chunk",
                source_type=source_type,
                source_id=source_id,
                status="active",
                updated_at=resolved_updated_at,
                metadata={
                    **(metadata or {}),
                    "chunk_index": index,
                },
            )
            for index, chunk in enumerate(chunks)
        ]
        self._knowledge_index.upsert(documents)
        logger.info(
            "Indexed %d chunks from '%s' into project %s",
            len(chunks),
            source_id,
            self.project_id,
        )
        return len(chunks)

    async def delete_source(self, source: str) -> None:
        self._knowledge_index.delete(
            filters={
                "scope": "document",
                "source_type": "document",
                "source_id": source,
            }
        )

    async def delete_project_file(self, file_id: str) -> None:
        self._knowledge_index.delete(
            filters={
                "scope": "document",
                "source_type": _PROJECT_FILE_SOURCE_TYPE,
                "source_id": _project_file_source_id(str(file_id)),
            }
        )

    async def clear_index(self) -> None:
        self._knowledge_index.clear_scope("document")

    async def search(self, query: str, *, limit: int = 5) -> list[DocumentSearchResult]:
        hits = self._knowledge_index.search(
            query,
            limit=limit,
            filters={"scope": "document"},
        )
        return [
            DocumentSearchResult(
                source=str(
                    hit.metadata.get("file_name")
                    or hit.metadata.get("source")
                    or hit.title
                    or hit.source_id
                    or ""
                ),
                content=hit.content,
                score=hit.score if hit.score > 0 else None,
            )
            for hit in hits
        ]
