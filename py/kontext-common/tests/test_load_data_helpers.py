"""Tests for kontext.load_data reference extraction (UUIDs and notebook aliases)."""

from kontext.common.python_execution.helpers import (
    classify_data_source_names,
    extract_kontext_load_data_ids,
    is_kontext_data_alias,
)

GUID = "1ffe5a68-2503-4d30-9217-e4f1245002df"
UPPER_GUID = "1FFE5A68-2503-4D30-9217-E4F1245002DF"


def test_extracts_guid_literals() -> None:
    code = f'df = await kontext.load_data("{GUID}")'
    assert extract_kontext_load_data_ids(code) == [GUID]


def test_guid_extraction_is_case_insensitive() -> None:
    code = f"df = await kontext.load_data('{UPPER_GUID}')"
    assert extract_kontext_load_data_ids(code) == [UPPER_GUID]


def test_extracts_slug_aliases() -> None:
    code = "a = await kontext.load_data(\"df_1\")\nb = kontext.load_data('sales_summary')"
    assert extract_kontext_load_data_ids(code) == ["df_1", "sales_summary"]


def test_extraction_dedupes_and_preserves_order() -> None:
    code = (
        f'x = kontext.load_data("{GUID}")\n'
        'y = kontext.load_data("df_1")\n'
        f'z = kontext.load_data("{GUID}")\n'
    )
    assert extract_kontext_load_data_ids(code) == [GUID, "df_1"]


def test_guid_literal_never_matches_alias_branch() -> None:
    assert extract_kontext_load_data_ids(f'kontext.load_data("{GUID}")') == [GUID]
    assert not is_kontext_data_alias(GUID)


def test_hex_slug_never_matches_guid_branch() -> None:
    # 32-char hex-with-no-dashes is a valid slug; not a UUID literal.
    hex_slug = "deadbeef00112233445566778899aabb"
    assert extract_kontext_load_data_ids(f'kontext.load_data("{hex_slug}")') == [hex_slug]
    assert is_kontext_data_alias(hex_slug)


def test_invalid_slug_identifiers_are_not_extracted() -> None:
    # Dashes (UUID-shaped without the rest) and leading digits never resolve.
    assert extract_kontext_load_data_ids('kontext.load_data("bad-name")') == []
    assert extract_kontext_load_data_ids('kontext.load_data("9bad")') == []


def test_prefix_case_insensitivity_matches_guid_branch() -> None:
    code = 'X = Kontext.load_data("df_1")'
    assert extract_kontext_load_data_ids(code) == ["df_1"]


def test_is_kontext_data_alias() -> None:
    assert is_kontext_data_alias("df_1")
    assert is_kontext_data_alias("Sales_Summary")
    assert not is_kontext_data_alias("9bad")
    assert not is_kontext_data_alias("with-dash")
    assert not is_kontext_data_alias("")
    assert not is_kontext_data_alias("x" * 65)


def test_non_load_data_kontext_calls_are_ignored() -> None:
    code = 'await kontext.save_table(df, "df_9")\nkontext.list_data_sources()'
    assert extract_kontext_load_data_ids(code) == []


def test_classify_data_source_names_splits_by_flavor() -> None:
    names = ["df_1", "afe88abc-6287-4b99-af2e-e97ce9b35517", "sales_summary", "df_10"]
    assert classify_data_source_names(names) == {
        "aliases": ["df_1", "df_10", "sales_summary"],
        "data_ids": ["afe88abc-6287-4b99-af2e-e97ce9b35517"],
    }
    # Duplicates collapse; empty input stays valid.
    assert classify_data_source_names(["df_1", "df_1"]) == {"aliases": ["df_1"], "data_ids": []}
    assert classify_data_source_names([]) == {"aliases": [], "data_ids": []}


def test_empty_or_none_code_is_safe() -> None:
    assert extract_kontext_load_data_ids("") == []
    assert extract_kontext_load_data_ids(None) == []  # type: ignore[arg-type]
