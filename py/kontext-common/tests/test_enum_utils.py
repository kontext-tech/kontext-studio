from __future__ import annotations

from enum import IntEnum, StrEnum

from kontext.common.utils.enum_utils import enum_value, safe_enum_conversion


class _Color(StrEnum):
    RED = "red"


class _Rank(IntEnum):
    FIRST = 1


def test_enum_value_returns_plain_string() -> None:
    assert enum_value("red") == "red"


def test_enum_value_returns_member_value_for_string_enum() -> None:
    assert enum_value(_Color.RED) == "red"


def test_enum_value_returns_none_for_missing_or_non_string_values() -> None:
    assert enum_value(None) is None
    # IntEnum's value is an int, not a string, so it has no string form here.
    assert enum_value(_Rank.FIRST) is None
    assert enum_value(object()) is None


def test_safe_enum_conversion_by_value_and_name() -> None:
    assert safe_enum_conversion(_Color, "red", None) is _Color.RED
    assert safe_enum_conversion(_Color, "RED", None) is _Color.RED
    assert safe_enum_conversion(_Color, "missing", None) is None
