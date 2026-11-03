"""Knowledge curation and retrieval contracts."""

from __future__ import annotations

from typing import Protocol

from kontext.schema import OkfConcept


class IKnowledgeServiceProtocol(Protocol):
    """Protocol for durable OKF knowledge curation and retrieval."""

    async def list_concepts(self) -> list[OkfConcept]: ...

    async def get_concept(self, concept_id: str) -> OkfConcept | None: ...

    async def search_concepts(self, query: str, limit: int = 10) -> list[OkfConcept]: ...

    async def list_proposals(self) -> list[OkfConcept]: ...

    async def propose_concept(
        self,
        *,
        draft: OkfConcept,
        proposed_by: str,
        chat_session_id: str | None = None,
    ) -> OkfConcept: ...

    async def approve_concept(
        self,
        concept_id: str,
        *,
        approved_by: str,
    ) -> OkfConcept | None: ...

    async def upsert_concept(self, concept: OkfConcept) -> OkfConcept: ...

    async def delete_concept(self, concept_id: str) -> bool: ...
