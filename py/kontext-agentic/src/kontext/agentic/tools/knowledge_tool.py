"""Knowledge (OKF) tools for curated business context.

Agents use these tools to look up curated concepts (metric definitions, join
semantics, golden queries) and to *propose* new concepts. Proposals are stored
with ``status='proposed'`` and are hidden from retrieval by the OKF trust gate
until a human approves them, closing the chat -> curation loop.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from kontext.agent import RuntimeToolContext
from kontext.agent.tools import tool_meta
from kontext.schema import (
    KnowledgeProposalResult,
    KnowledgeSearchResult,
    OkfConcept,
)

from .kontext_toolkit import KontextToolkit, ToolkitScope

if TYPE_CHECKING:
    from kontext.common.protocols import AIToolkitServiceProviderProtocol
    from kontext.schema import ProjectModel


class KnowledgeTools(KontextToolkit):
    """Toolkit for searching and proposing curated OKF knowledge."""

    def __init__(
        self,
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        scope: ToolkitScope | None = None,
    ) -> None:
        super().__init__(
            name="KnowledgeTools",
            project=project,
            runtime_provider=runtime_provider,
            session_id=session_id,
            chat_session_id=chat_session_id,
            scope=scope,
            tools=[self.search_knowledge, self.propose_knowledge_concept],
        )

    def _knowledge_service(self):
        if not self.runtime_provider:
            return None
        return self.runtime_provider.get_knowledge_service()

    @tool_meta(KnowledgeSearchResult, display_name="Search Curated Knowledge")
    async def search_knowledge(
        self,
        query: str,
        limit: int = 5,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Search curated business knowledge (metric definitions, join semantics).

        Use this before writing SQL when the request references business terms,
        KPIs, or documented relationships that may be defined outside the schema.

        :param query: Natural language search query describing what you need.
        :param limit: Maximum number of concepts to return (default 5).
        """
        try:
            service = self._knowledge_service()
            if service is None:
                raise RuntimeError("Curated knowledge search is unavailable in this runtime.")
            concepts = await service.search_concepts(query, limit=limit)
            message = (
                f"Found {len(concepts)} curated concepts."
                if concepts
                else "No relevant curated knowledge found."
            )
            return self._create_result(
                success=True,
                result_class=KnowledgeSearchResult,
                message=message,
                concepts=concepts,
            )
        except Exception as exc:
            return self._create_result(
                success=False,
                result_class=KnowledgeSearchResult,
                message="Knowledge search failed",
                error=str(exc),
            )

    @tool_meta(KnowledgeProposalResult, display_name="Propose Curated Concept")
    async def propose_knowledge_concept(
        self,
        title: str,
        body: str,
        concept_type: str = "Metric",
        description: str | None = None,
        tags: list[str] | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Propose a new curated knowledge concept for the user to approve.

        Use this when you and the user have agreed on a durable business
        definition (e.g. a metric formula or an approved join path). The concept
        is stored as a proposal and only becomes searchable after the user
        approves it.

        :param title: Short human-readable concept title.
        :param body: Markdown body with the definition, formula, or notes.
            Reference related tables or concepts as ordinary markdown links
            (OKF §6), e.g. ``[orders](/tables/orders.md)``.
        :param concept_type: Concept type, e.g. Metric, Definition, JoinPath.
        :param description: Optional one-line summary.
        :param tags: Optional tags for organization.
        """
        try:
            service = self._knowledge_service()
            if service is None:
                raise RuntimeError("Curated knowledge is unavailable in this runtime.")
            draft = OkfConcept(
                id=f"concepts/{uuid.uuid4().hex}",
                type=concept_type,
                title=title,
                description=description,
                body=body,
                tags=tags or [],
            )
            proposed = await service.propose_concept(
                draft=draft,
                # OKF actor convention: ``<producer>/<version>`` for agents.
                proposed_by="kontext-agent/1.0",
                chat_session_id=self.chat_session_id,
            )
            return self._create_result(
                success=True,
                result_class=KnowledgeProposalResult,
                message=(f"Proposed concept '{proposed.title}'. Awaiting user approval."),
                concept=proposed,
            )
        except Exception as exc:
            return self._create_result(
                success=False,
                result_class=KnowledgeProposalResult,
                message="Knowledge proposal failed",
                error=str(exc),
            )
