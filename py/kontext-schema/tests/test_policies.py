"""Tests for the hand-written contract policy bases used by generated models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from kontext.schema import OkfConcept, UpdateChatSessionRequest


def test_okf_date_only_timestamp_is_stamped_utc() -> None:
    concept = OkfConcept.model_validate({"type": "metric", "timestamp": "2026-12-31"})

    assert concept.timestamp == datetime(2026, 12, 31, tzinfo=UTC)
    assert '"timestamp":"2026-12-31T00:00:00Z"' in concept.model_dump_json(by_alias=True)


def test_okf_nested_timestamps_are_stamped_utc() -> None:
    concept = OkfConcept.model_validate(
        {
            "type": "metric",
            "attestation": {
                "stale_after": "2026-12-31",
                "verified": [{"by": "data@example.com", "at": "2026-01-01"}],
            },
        }
    )

    assert concept.attestation is not None
    assert concept.attestation.stale_after == datetime(2026, 12, 31, tzinfo=UTC)
    assert concept.attestation.verified[0].at == datetime(2026, 1, 1, tzinfo=UTC)


def test_okf_aware_timestamp_keeps_its_offset() -> None:
    concept = OkfConcept.model_validate(
        {"type": "metric", "timestamp": "2026-12-31T10:00:00+02:00"}
    )

    assert concept.timestamp is not None
    assert concept.timestamp.utcoffset() == timedelta(hours=2)


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        ({"sessionName": None}, "sessionName"),
        ({"modelSelectionId": None}, "modelSelectionId"),
        ({"defaultCatalogConnectionId": None}, "defaultCatalogConnectionId"),
        ({"pythonExecutionApprovalMode": None}, "pythonExecutionApprovalMode"),
    ],
)
def test_omit_only_fields_reject_explicit_nulls(payload, field_name) -> None:
    with pytest.raises(ValidationError, match=field_name):
        UpdateChatSessionRequest.from_dict(payload)


def test_omit_only_fields_allow_omission_and_values() -> None:
    assert UpdateChatSessionRequest.from_dict({}).to_dict() == {}
    assert UpdateChatSessionRequest.from_dict({"sessionName": "review"}).to_dict() == {
        "sessionName": "review"
    }
