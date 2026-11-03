"""Provider-neutral knowledge index contracts and shared record types."""

from .index import (
    FacetFilters,
    FacetFilterValue,
    FacetValue,
    KnowledgeDocument,
    KnowledgeIndex,
    KnowledgeSearchHit,
)

__all__ = [
    "FacetFilterValue",
    "FacetFilters",
    "FacetValue",
    "KnowledgeDocument",
    "KnowledgeIndex",
    "KnowledgeSearchHit",
]
