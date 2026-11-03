"""OKF v0.2 concept model: the canonical unit of curated knowledge.

An ``OkfConcept`` is one markdown concept with YAML frontmatter, per the Open
Knowledge Format v0.2 spec. This model carries the frontmatter fields OKF v0.2
defines (``type``, ``title``, ``description``, ``tags``, ``status``,
``generated``, ``verified``, ``stale_after``, ``sources``, ``runtime``,
``parameters``, ``executor``, ``attester``, ``usage_window``) plus the
markdown body. It is intentionally kept aligned with the OKF spec rather than
with any older runtime-specific schema.

This is the **source-of-truth** model. The LanceDB index layer is fed from it
via :func:`concept_to_index_document` (a one-way projection) and is disposable.

The attestation fields that OKF v0.2 added (``runtime``, ``parameters``,
``computation``, ``executor``, ``attester``, ``usage_window``) are modeled
*loosely* here as plain ``dict``/``list`` scalars rather than nested Pydantic
classes. Today no internal consumer reads them; they round-trip verbatim
through the YAML serialization in :mod:`frontmatter`. When a real consumer
(e.g. an LLM enrichment pass or an attestation verifier) needs typed access,
promote the field in question to a model at that point.

Relationship edges are expressed as ordinary markdown links in the concept
``body`` (OKF §6), not as a dedicated frontmatter field, so bundles stay
interoperable with any OKF consumer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from kontext.schema import (
    OkfConcept,
)

if TYPE_CHECKING:
    from kontext.common.knowledge.index import KnowledgeDocument

#: Concept id namespace prefix used when projecting to a KnowledgeDocument.
_KNOWLEDGE_DOC_ID_PREFIX = "knowledge"


def concept_to_index_document(concept: OkfConcept) -> "KnowledgeDocument":  # noqa: UP037
    """Project a canonical OKF concept into a derived ``KnowledgeDocument`` row.

    This is the **one-way bridge** from the OKF source-of-truth layer to the
    disposable LanceDB index layer. The index row carries enough of the concept
    for hybrid search (title + body + structured metadata facets) while the OKF
    concept remains the system of record.

    Preserves the knowledge-index content shape so existing ranking logic in
    ``CatalogIndexService`` keeps working unchanged.
    """

    # Local import avoids a hard import cycle at module load (the catalog
    # package is a dependency of this one, but importing lazily here keeps the
    # model module side-effect free).
    from kontext.common.knowledge.index import KnowledgeDocument

    concept_id = concept.id or "concepts/untitled"
    title = concept.title or concept_id
    content_lines = [
        f"Knowledge: {title}",
        f"Description: {concept.description or ''}",
        f"Type: {concept.type or 'unknown'}",
        f"Status: {concept.status or 'unknown'}",
    ]
    attestation = concept.attestation
    if attestation is not None and attestation.stale_after is not None:
        content_lines.append(f"Stale After: {_iso_str(attestation.stale_after)}")
    if attestation is not None and attestation.verified:
        content_lines.append(f"Verified By: {attestation.verified[0].by}")
    if attestation is not None and attestation.sources:
        cited = ", ".join(src.title or src.resource for src in attestation.sources)
        content_lines.append(f"Sources: {cited}")
    if concept.body.strip():
        content_lines.append("")
        content_lines.append(concept.body.strip())

    return KnowledgeDocument(
        document_id=f"{_KNOWLEDGE_DOC_ID_PREFIX}:{concept_id}",
        title=title,
        content="\n".join(content_lines),
        scope="knowledge",
        content_kind="curated_note",
        source_type="okf_concept",
        source_id=concept_id,
        status=concept.status,
        metadata=_concept_metadata(concept),
    )


def _concept_metadata(concept: OkfConcept) -> dict[str, Any]:
    """Flatten the OKF concept into the metadata facet bag for the index row."""

    metadata: dict[str, Any] = {
        "knowledge_name": concept.title,
        "knowledge_description": concept.description,
        "knowledge_type": concept.type,
        "status": concept.status,
        "resource": concept.resource,
        "tags": list(concept.tags),
        "metadata": dict(concept.metadata),
    }
    att = concept.attestation
    if att is not None and att.generated is not None:
        metadata["generated_by"] = att.generated.by
        if att.generated.at is not None:
            metadata["generated_at"] = _iso_str(att.generated.at)
    if att is not None and att.verified:
        metadata["verified_by"] = att.verified[0].by
        if att.verified[0].at is not None:
            metadata["verified_at"] = _iso_str(att.verified[0].at)
    if att is not None and att.stale_after is not None:
        metadata["stale_after"] = _iso_str(att.stale_after)
    if att is not None and att.sources:
        metadata["sources"] = [src.model_dump(by_alias=True) for src in att.sources]
    return metadata


def _iso_str(value: Any) -> str:
    """Format date/datetime/string objects into a normalized ISO string."""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
