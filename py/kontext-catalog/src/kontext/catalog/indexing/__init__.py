"""Catalog indexing, embedding, and search over the unified knowledge index."""

from .catalog_index import CatalogIndexService
from .document_extractor import (
    DocumentExtractor,
    ExtractionResult,
    is_indexable_document_upload,
)
from .document_index import (
    DocumentIndexingOutcome,
    DocumentIndexService,
    DocumentSearchResult,
)
from .embedding import (
    EmbeddingProvider,
    FastEmbedEmbedding,
    LocalHashEmbedding,
    get_default_embedding_provider,
)
from .lancedb_index import LanceDBKnowledgeIndex
from .storage_paths import (
    ProjectKnowledgeStoragePaths,
    get_project_vector_db_path,
    resolve_project_knowledge_storage_paths,
)

__all__ = [
    "CatalogIndexService",
    "DocumentExtractor",
    "DocumentIndexService",
    "DocumentIndexingOutcome",
    "DocumentSearchResult",
    "EmbeddingProvider",
    "ExtractionResult",
    "FastEmbedEmbedding",
    "LanceDBKnowledgeIndex",
    "LocalHashEmbedding",
    "ProjectKnowledgeStoragePaths",
    "get_default_embedding_provider",
    "get_project_vector_db_path",
    "is_indexable_document_upload",
    "resolve_project_knowledge_storage_paths",
]
