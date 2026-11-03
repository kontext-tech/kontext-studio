"""Catalog management and indexing services.

Organised into two cohesive subpackages:

* :mod:`.indexing` — the knowledge index, embeddings, document extraction, and
  search (semantic/lexical retrieval over the unified corpus).
* :mod:`.connections` — catalog connection management, provider registry, and
  the internal Iceberg lakehouse.
"""

from .connections import (
    CatalogManagementService,
    CatalogProviderRegistry,
    LakehouseService,
)
from .indexing import (
    CatalogIndexService,
    DocumentExtractor,
    DocumentIndexingOutcome,
    DocumentIndexService,
    DocumentSearchResult,
    EmbeddingProvider,
    ExtractionResult,
    FastEmbedEmbedding,
    LanceDBKnowledgeIndex,
    LocalHashEmbedding,
    get_default_embedding_provider,
    is_indexable_document_upload,
)
from .sync_dispatch import CatalogSyncDispatchService

__all__ = [
    "CatalogIndexService",
    "CatalogManagementService",
    "CatalogProviderRegistry",
    "CatalogSyncDispatchService",
    "DocumentExtractor",
    "DocumentIndexService",
    "DocumentIndexingOutcome",
    "DocumentSearchResult",
    "EmbeddingProvider",
    "ExtractionResult",
    "FastEmbedEmbedding",
    "LakehouseService",
    "LanceDBKnowledgeIndex",
    "LocalHashEmbedding",
    "get_default_embedding_provider",
    "is_indexable_document_upload",
]
