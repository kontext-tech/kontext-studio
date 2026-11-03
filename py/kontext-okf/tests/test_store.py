"""Tests for the durable OKF concept store."""

from __future__ import annotations

from datetime import UTC, datetime

from kontext.okf import OkfConcept, OkfConceptStore


def _concept(concept_id: str, **overrides) -> OkfConcept:
    base: dict[str, object] = {
        "id": concept_id,
        "type": "Table",
        "title": concept_id,
    }
    base.update(overrides)
    return OkfConcept(**base)  # type: ignore[arg-type]


class TestOkfConceptStore:
    def test_empty_store_returns_empty_list(self, tmp_path) -> None:
        store = OkfConceptStore(tmp_path / "okf")
        assert store.list_concepts() == []

    def test_upsert_then_list_round_trips(self, tmp_path) -> None:
        store = OkfConceptStore(tmp_path / "okf")
        store.upsert_concepts(
            [
                _concept("tables/orders", title="Orders"),
                _concept("tables/customers", title="Customers"),
            ]
        )
        concepts = store.list_concepts()
        assert len(concepts) == 2
        ids = {c.id for c in concepts}
        assert ids == {"tables/orders", "tables/customers"}

    def test_upsert_is_idempotent_by_id(self, tmp_path) -> None:
        """Re-upserting the same id replaces, not duplicates."""
        store = OkfConceptStore(tmp_path / "okf")
        store.upsert_concepts([_concept("tables/orders", title="Old")])
        store.upsert_concepts([_concept("tables/orders", title="New")])
        concepts = store.list_concepts()
        assert len(concepts) == 1
        assert concepts[0].title == "New"

    def test_upsert_empty_list_is_noop(self, tmp_path) -> None:
        store = OkfConceptStore(tmp_path / "okf")
        assert store.upsert_concepts([]) == 0
        assert store.list_concepts() == []

    def test_get_concept_by_id(self, tmp_path) -> None:
        store = OkfConceptStore(tmp_path / "okf")
        store.upsert_concepts([_concept("tables/orders")])
        assert store.get_concept("tables/orders") is not None
        assert store.get_concept("nonexistent") is None

    def test_clear_removes_all_concepts(self, tmp_path) -> None:
        store = OkfConceptStore(tmp_path / "okf")
        store.upsert_concepts([_concept("a"), _concept("b")])
        assert store.clear() == 2
        assert store.list_concepts() == []

    def test_clear_on_empty_store_is_zero(self, tmp_path) -> None:
        store = OkfConceptStore(tmp_path / "okf")
        assert store.clear() == 0

    def test_persists_across_store_instances(self, tmp_path) -> None:
        """The store is durable on disk — a new instance reads the same data."""
        path = tmp_path / "okf"
        OkfConceptStore(path).upsert_concepts([_concept("tables/orders")])
        # A fresh instance pointing at the same path sees the data.
        concepts = OkfConceptStore(path).list_concepts()
        assert len(concepts) == 1
        assert concepts[0].id == "tables/orders"

    def test_full_attestation_round_trips_through_store(self, tmp_path) -> None:
        """Trust/provenance fields survive the JSON serialize/deserialize cycle."""
        from kontext.okf import OkfAttestation, OkfProvenanceActor, OkfSource

        concept = _concept(
            "metrics/revenue",
            title="Revenue",
            attestation=OkfAttestation(
                generated=OkfProvenanceActor(by="agent/v1", at=datetime(2026, 6, 1, tzinfo=UTC)),
                stale_after=__import__("datetime").date(2026, 12, 31),
                sources=[OkfSource(id="s1", resource="https://ex.com")],
                runtime="bigquery",
            ),
        )
        store = OkfConceptStore(tmp_path / "okf")
        store.upsert_concepts([concept])
        restored = store.get_concept("metrics/revenue")
        assert restored is not None
        assert restored.attestation is not None
        assert restored.attestation.generated is not None
        assert restored.attestation.generated.by == "agent/v1"
        assert restored.attestation.stale_after is not None
        assert restored.attestation.runtime == "bigquery"
        assert len(restored.attestation.sources) == 1

    def test_corrupt_bundle_file_returns_empty_not_raise(self, tmp_path) -> None:
        """A corrupted backing file degrades to empty, never crashes callers."""
        store = OkfConceptStore(tmp_path / "okf")
        store._dir.mkdir(parents=True, exist_ok=True)
        # Write a malformed markdown concept file (missing closing delimiter).
        (store._dir / "broken.md").write_text(
            "---\nid: broken\ntype: Metric\ntitle: Broken\n", encoding="utf-8"
        )
        assert store.list_concepts() == []

    def test_reserved_files_are_not_treated_as_concepts(self, tmp_path) -> None:
        """`index.md` and `log.md` are structural, not concepts (OKF §3.1)."""
        store = OkfConceptStore(tmp_path / "okf")
        store.upsert_concepts([_concept("tables/orders", title="Orders")])
        store._dir.mkdir(parents=True, exist_ok=True)
        (store._dir / "index.md").write_text("# Tables\n\n* [Orders](tables/orders.md)\n")
        (store._dir / "log.md").write_text("# Update Log\n\n## 2026-01-01\n* **Init**\n")

        concepts = store.list_concepts()
        assert [c.id for c in concepts] == ["tables/orders"]
