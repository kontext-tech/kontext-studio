"""Tests for the OKF -> KnowledgeDocument projection and bundle I/O."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kontext.okf import (
    OkfAttestation,
    OkfBundle,
    OkfConcept,
    OkfProvenanceActor,
    OkfSource,
    concept_to_index_document,
    load_bundle,
    write_bundle,
)


def _concept(**overrides) -> OkfConcept:
    base: dict[str, object] = {
        "id": "notes/lakehouse",
        "type": "Reference",
        "title": "Lakehouse conventions",
    }
    base.update(overrides)
    return OkfConcept(**base)  # type: ignore[arg-type]


class TestProjection:
    """concept_to_index_document is the bridge to the existing index layer."""

    def test_projection_produces_knowledge_scope_document(self) -> None:
        doc = concept_to_index_document(_concept(status="stable"))
        assert doc.scope == "knowledge"
        assert doc.content_kind == "curated_note"
        assert doc.source_type == "okf_concept"
        assert doc.source_id == "notes/lakehouse"
        assert doc.document_id == "knowledge:notes/lakehouse"

    def test_projection_content_includes_title_description_and_body(self) -> None:
        doc = concept_to_index_document(
            _concept(
                description="How we name tables.",
                body="Bronze layer holds raw ingested data.",
            )
        )
        assert "Lakehouse conventions" in doc.content
        assert "How we name tables." in doc.content
        assert "Bronze layer holds raw ingested data." in doc.content

    def test_projection_carries_trust_fields_into_metadata(self) -> None:
        concept = _concept(
            attestation=OkfAttestation(
                verified=[
                    OkfProvenanceActor(
                        by="human:rachel",
                        at=datetime(2026, 7, 1, tzinfo=UTC),
                    )
                ],
                stale_after=datetime(2026, 12, 31, tzinfo=UTC),
                sources=[OkfSource(id="s1", resource="https://example.com")],
            ),
        )
        doc = concept_to_index_document(concept)
        assert doc.metadata["verified_by"] == "human:rachel"
        assert doc.metadata["stale_after"] == "2026-12-31T00:00:00+00:00"
        assert doc.metadata["sources"][0]["id"] == "s1"

    def test_projection_keeps_expected_knowledge_shape(self) -> None:
        projected = concept_to_index_document(_concept(title="Lakehouse conventions"))
        assert projected.scope == "knowledge"
        assert projected.content_kind == "curated_note"
        assert projected.title == "Lakehouse conventions"


class TestBundleIO:
    def test_bundle_round_trips_through_directory(self, tmp_path) -> None:
        bundle = OkfBundle(
            name="demo",
            concepts=[
                _concept(id="metrics/revenue", title="Revenue"),
                _concept(id="glossary/wau", title="Weekly Active Users"),
            ],
        )
        written = write_bundle(bundle, tmp_path / "demo")
        assert written.is_dir()

        loaded = load_bundle(written)
        assert len(loaded) == 2
        ids = {c.id for c in loaded}
        assert ids == {"metrics/revenue", "glossary/wau"}

    def test_bundle_concept_id_derived_from_relative_path(self, tmp_path) -> None:
        write_bundle(
            OkfBundle(
                name="d",
                concepts=[_concept(id="folder/nested/concept", title="Nested")],
            ),
            tmp_path / "d",
        )
        loaded = load_bundle(tmp_path / "d")
        assert loaded.get("folder/nested/concept") is not None

    def test_bundle_preserves_dotted_concept_ids(self, tmp_path) -> None:
        """Concept ids with dots (e.g. bronze.orders) round-trip intact."""
        write_bundle(
            OkfBundle(
                name="d",
                concepts=[_concept(id="tables/bronze.orders", title="Orders")],
            ),
            tmp_path / "d",
        )
        loaded = load_bundle(tmp_path / "d")
        assert loaded.get("tables/bronze.orders") is not None
        # The file on disk must be bronze.orders.md, not bronze.md.
        assert (tmp_path / "d" / "tables" / "bronze.orders.md").exists()

    def test_load_missing_directory_raises(self, tmp_path) -> None:
        from kontext.okf import OkfBundleReadError

        with pytest.raises(OkfBundleReadError):
            load_bundle(tmp_path / "does-not-exist")
