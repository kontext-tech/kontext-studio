"""Tests for tolerant validation of JSON persisted by older schema versions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from kontext.common.utils.json_compat import model_validate_stored


class _Nested(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    value: int
    note: str | None = None


class _Container(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    name: str
    nested: _Nested
    items: list[_Nested] = []
    by_key: dict[str, _Nested] = {}


def test_top_level_unknown_keys_are_pruned() -> None:
    result = model_validate_stored(
        _Container,
        {
            "name": "a",
            "nested": {"value": 1},
            "removedFlag": True,
            "legacy": {"anything": 1},
        },
    )
    assert result.name == "a"
    assert result.nested.value == 1


def test_camel_case_aliases_are_honored() -> None:
    result = model_validate_stored(_Container, {"name": "a", "nested": {"value": 2}})
    assert result.nested.value == 2


def test_unknown_keys_pruned_recursively_in_nested_models() -> None:
    result = model_validate_stored(
        _Container,
        {
            "name": "a",
            "nested": {"value": 1, "stale": "x"},
            "items": [{"value": 2, "gone": 1}],
            "by_key": {"k": {"value": 3, "obsolete": True}},
        },
    )
    assert result.nested.value == 1
    assert result.items[0].value == 2
    assert result.by_key["k"].value == 3


def test_missing_known_field_still_fails_validation() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        model_validate_stored(_Container, {"nested": {"value": 1}})


def test_legacy_capabilities_payload_loads() -> None:
    from kontext.schema import CatalogConnectionCapabilities

    caps = model_validate_stored(
        CatalogConnectionCapabilities,
        {
            "supportsSync": False,
            "supportsSearch": False,
            "supportsRelationshipDiscovery": True,
            "supportsWrite": False,
        },
    )
    assert caps.supports_sync is False
    assert caps.supports_search is False
    assert caps.supports_write is False
