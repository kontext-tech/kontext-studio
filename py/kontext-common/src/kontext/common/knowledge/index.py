"""Provider-neutral knowledge index contracts and shared record types."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

FacetValue = str | int | float | bool | None
FacetFilterValue = FacetValue | Sequence[FacetValue]
FacetFilters = Mapping[str, FacetFilterValue]


@dataclass(frozen=True)
class KnowledgeDocument:
    """A single logical record stored in the unified project corpus."""

    document_id: str
    content: str
    scope: str
    content_kind: str
    provider_kind: str | None = None
    connection_id: str | None = None
    namespace_name: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    status: str | None = None
    updated_at: str | None = None
    title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeSearchHit:
    """Ranked search result returned by the provider-neutral index."""

    document_id: str
    content: str
    score: float
    scope: str
    content_kind: str
    provider_kind: str | None = None
    connection_id: str | None = None
    namespace_name: str | None = None
    entity_id: str | None = None
    entity_name: str | None = None
    entity_type: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    status: str | None = None
    updated_at: str | None = None
    title: str | None = None
    vector_distance: float | None = None
    lexical_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class KnowledgeIndex(Protocol):
    """Provider-neutral abstraction for hybrid retrieval backends."""

    def upsert(self, documents: Sequence[KnowledgeDocument]) -> int:
        """Upsert the provided documents and return the indexed count."""
        ...

    def delete(
        self,
        document_ids: Sequence[str] | None = None,
        *,
        filters: FacetFilters | None = None,
    ) -> int:
        """Delete indexed records by ID and/or facet filters."""
        ...

    def clear_scope(self, scope: str, *, filters: FacetFilters | None = None) -> int:
        """Delete all indexed rows within the requested scope/filter slice."""
        ...

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        filters: FacetFilters | None = None,
    ) -> list[KnowledgeSearchHit]:
        """Execute hybrid retrieval with optional facet filters."""
        ...
