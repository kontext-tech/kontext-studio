"""Tests for the hand-written base model shared by the generated models."""

from __future__ import annotations

from kontext.schema import AccessTokenResponse, OkfConcept


def test_to_dict_uses_wire_aliases() -> None:
    response = AccessTokenResponse.model_validate(
        {"accessToken": "a", "expiresIn": 1, "refreshToken": "r"}
    )

    assert response.to_dict() == {
        "accessToken": "a",
        "expiresIn": 1,
        "refreshToken": "r",
    }


def test_to_dict_keeps_explicitly_null_fields() -> None:
    response = AccessTokenResponse.model_validate(
        {
            "accessToken": "a",
            "expiresIn": 1,
            "refreshToken": "r",
            "tokenType": None,
        }
    )

    assert response.to_dict()["tokenType"] is None


def test_to_dict_keeps_explicitly_null_open_model_extras() -> None:
    """Producer extensions on open models can legitimately be YAML null."""
    concept = OkfConcept.model_validate({"type": "metric", "owner": None, "freshness_sla": "30m"})

    data = concept.to_dict()

    assert data["owner"] is None
    assert data["freshness_sla"] == "30m"


def test_additional_properties_exposes_open_model_extras() -> None:
    concept = OkfConcept.model_validate({"type": "metric", "owner": "data@example.com"})

    assert concept.additional_properties == {"owner": "data@example.com"}
