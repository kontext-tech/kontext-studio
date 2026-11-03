"""Tests for OKF markdown + YAML frontmatter round-tripping."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kontext.okf import (
    OkfAttestation,
    OkfConcept,
    OkfProvenanceActor,
    OkfSource,
    concept_from_frontmatter,
    concept_to_frontmatter,
)


def _rich_concept() -> OkfConcept:
    return OkfConcept(
        id="metrics/revenue",
        type="Metric",
        title="Revenue (fiscal year)",
        description="Recognized revenue for a fiscal year.",
        tags=["finance", "revenue"],
        status="stable",
        body="Revenue is the sum of `amount` in `finance.recognized_revenue`.",
        attestation=OkfAttestation(
            generated=OkfProvenanceActor(
                by="reference_agent/gemini-2.5-pro",
                at=datetime(2026, 6, 28, 14, 0, tzinfo=UTC),
            ),
            verified=[
                OkfProvenanceActor(
                    by="human:ahormati",
                    at=datetime(2026, 6, 25, 9, 0, tzinfo=UTC),
                )
            ],
            stale_after=datetime(2026, 12, 31, tzinfo=UTC),
            sources=[
                OkfSource(
                    id="rev-policy",
                    resource="https://wiki.acme/finance/revenue-recognition",
                    title="Revenue recognition policy",
                    author="team:finance-fpa",
                    last_modified=__import__("datetime").date(2026, 6, 1),
                )
            ],
            runtime="bigquery",
        ),
    )


class TestRoundTrip:
    def test_rich_concept_round_trips_losslessly(self) -> None:
        original = _rich_concept()
        text = concept_to_frontmatter(original)
        restored = concept_from_frontmatter(text)
        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.title == original.title
        assert restored.description == original.description
        assert restored.tags == original.tags
        assert restored.status == original.status
        assert restored.body == original.body
        assert "knowledge_type" not in concept_to_frontmatter(original)
        assert "created_at" not in concept_to_frontmatter(original)
        # attestation (guards satisfy the type checker; the rich concept sets
        # all of these, so the asserts also document that invariant).
        assert original.attestation is not None
        assert restored.attestation is not None
        assert original.attestation.generated is not None
        assert restored.attestation.generated is not None
        assert restored.attestation.generated.by == original.attestation.generated.by
        assert restored.attestation.verified
        assert restored.attestation.verified[0].by == "human:ahormati"
        assert restored.attestation.stale_after == original.attestation.stale_after
        assert restored.attestation.sources[0].resource.startswith("https://wiki")
        assert restored.attestation.runtime == "bigquery"

    def test_minimal_concept_round_trips(self) -> None:
        concept = OkfConcept(id="glossary/wau", type="Reference", title="Weekly Active Users")
        restored = concept_from_frontmatter(concept_to_frontmatter(concept))
        assert restored.id == "glossary/wau"
        assert restored.title == "Weekly Active Users"
        assert restored.body == ""
        assert restored.attestation is None or restored.attestation.sources == []

    def test_frontmatter_is_delimited_markdown(self) -> None:
        text = concept_to_frontmatter(OkfConcept(id="x", type="Metric", title="X"))
        assert text.startswith("---\n")
        # closing delimiter on its own line
        assert "\n---\n" in text

    def test_nested_fields_use_snake_case_keys(self) -> None:
        """OKF wire format uses snake_case, not the API's camelCase aliases."""
        text = concept_to_frontmatter(_rich_concept())
        assert "last_modified:" in text
        assert "lastModified" not in text

    def test_timestamps_are_iso_datetimes_with_offset(self) -> None:
        """OKF v0.2 requires timestamp keys to carry an explicit UTC offset."""
        text = concept_to_frontmatter(_rich_concept())
        assert "stale_after: '2026-12-31T00:00:00Z'" in text


class TestParsingValidation:
    def test_missing_opening_delimiter_raises(self) -> None:
        with pytest.raises(ValueError, match="frontmatter delimiter"):
            concept_from_frontmatter("type: Metric\ntitle: X\n")

    def test_unclosed_frontmatter_raises(self) -> None:
        with pytest.raises(ValueError, match="not closed"):
            concept_from_frontmatter("---\ntype: Metric\n")

    def test_missing_type_raises(self) -> None:
        text = "---\nid: a\ntitle: X\n---\nbody\n"
        with pytest.raises(ValueError, match="required 'type' field"):
            concept_from_frontmatter(text)

    def test_type_only_concept_is_conformant(self) -> None:
        # OKF §9: `type` is the only required frontmatter field.
        concept = concept_from_frontmatter("---\ntype: Metric\n---\nBody\n")
        assert concept.type == "Metric"
        assert concept.id is None
        assert concept.title is None

    def test_unknown_fields_are_preserved(self) -> None:
        text = "---\nid: a\ntype: Metric\ntitle: X\nowner: data@co\nfreshness_sla: 30m\n---\n"
        concept = concept_from_frontmatter(text)
        assert concept.additional_properties["owner"] == "data@co"
        assert concept.additional_properties["freshness_sla"] == "30m"
        # Round-trip keeps them.
        restored = concept_from_frontmatter(concept_to_frontmatter(concept))
        assert restored.additional_properties["owner"] == "data@co"

    def test_legacy_single_verified_is_wrapped(self) -> None:
        # v0.1-style `verified: {by, at}` still parses into the v0.2 list shape.
        text = (
            "---\nid: a\ntype: Metric\ntitle: X\n"
            "verified: {by: human:x, at: 2026-01-01T00:00:00+00:00}\n---\n"
        )
        concept = concept_from_frontmatter(text)
        assert concept.attestation is not None
        assert [v.by for v in concept.attestation.verified] == ["human:x"]

    def test_source_id_is_optional(self) -> None:
        # OKF §5.1: `sources[].id` is optional (only needed for footnotes).
        text = "---\ntype: Metric\nsources:\n  - resource: https://x\n---\n"
        concept = concept_from_frontmatter(text)
        assert concept.attestation is not None
        assert concept.attestation.sources[0].id is None
        # Round-trips without inventing an id.
        restored = concept_from_frontmatter(concept_to_frontmatter(concept))
        assert restored.attestation is not None
        assert restored.attestation.sources[0].id is None

    def test_source_level_usage_window_round_trips_as_iso(self) -> None:
        # OKF §5.1: a source entry MAY carry its own `usage_window`.
        text = (
            "---\ntype: Metric\nsources:\n"
            "  - { id: s1, resource: https://x, usage_count: 5, "
            "usage_window: { from: 2026-06-01T00:00:00Z, to: 2026-06-30T00:00:00Z } }\n"
            "---\n"
        )
        concept = concept_from_frontmatter(text)
        assert concept.attestation is not None
        # Re-serialization uses ISO 8601 datetimes with an offset (OKF §5).
        out = concept_to_frontmatter(concept)
        assert "2026-06-01T00:00:00Z" in out
        assert "2026-06-30T00:00:00Z" in out

    def test_actor_at_is_optional(self) -> None:
        # OKF §5.2: only `by` is REQUIRED; `at` is recommended but optional.
        text = (
            "---\ntype: Metric\n"
            "generated: { by: human:jane }\n"
            "verified:\n  - { by: process:ci-lint }\n---\n"
        )
        concept = concept_from_frontmatter(text)
        assert concept.attestation is not None
        assert concept.attestation.generated is not None
        assert concept.attestation.generated.at is None
        assert concept.attestation.verified[0].at is None
        # Round-trips without fabricating a timestamp.
        out = concept_to_frontmatter(concept)
        assert "at:" not in out

    def test_usage_window_sibling_normalizes_to_iso(self) -> None:
        # Top-level `usage_window` frames every `usage_count` (OKF §5.1).
        text = (
            "---\ntype: Metric\nsources:\n  - { id: s1, resource: https://x }\n"
            "usage_window: { from: 2026-06-01T00:00:00Z, to: 2026-06-30T00:00:00Z }\n"
            "---\n"
        )
        concept = concept_from_frontmatter(text)
        out = concept_to_frontmatter(concept)
        assert "2026-06-01T00:00:00Z" in out
