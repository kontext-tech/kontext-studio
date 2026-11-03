"""Tests for the OKF freshness/trust gate."""

from __future__ import annotations

from datetime import date

from kontext.okf import is_concept_fresh


class TestTrustGate:
    def test_concept_without_trust_fields_is_fresh(self) -> None:
        assert is_concept_fresh({}) is True

    def test_draft_status_is_not_fresh(self) -> None:
        # OKF lifecycle value.
        assert is_concept_fresh({"status": "draft"}) is False

    def test_legacy_proposed_status_is_not_fresh(self) -> None:
        # Kontext's historical alias for `draft`.
        assert is_concept_fresh({"status": "proposed"}) is False

    def test_stable_status_is_fresh(self) -> None:
        assert is_concept_fresh({"status": "stable"}) is True

    def test_expired_iso_datetime_stale_after_is_not_fresh(self) -> None:
        # OKF v0.2 emits full ISO datetimes with an offset.
        assert (
            is_concept_fresh(
                {"stale_after": "2020-01-01T00:00:00Z"},
                now=date(2026, 1, 1),
            )
            is False
        )

    def test_legacy_date_only_stale_after_still_parses(self) -> None:
        assert (
            is_concept_fresh(
                {"stale_after": "2020-01-01"},
                now=date(2026, 1, 1),
            )
            is False
        )

    def test_future_stale_after_is_fresh(self) -> None:
        assert (
            is_concept_fresh(
                {"stale_after": "2030-01-01T00:00:00+00:00"},
                now=date(2026, 1, 1),
            )
            is True
        )
