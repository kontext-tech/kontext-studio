"""Helpers for detecting managed Kontext helper usage in Python code."""

from __future__ import annotations

import re
from collections.abc import Iterable

_GUID_PATTERN = (
    r"[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}"
)

# Notebook-scope alias for SQL block results (df_1, sales_summary, ...).
# Mirrors the pattern on SqlBlockData in the ts/schema contract; disjoint
# from the GUID pattern (no dashes allowed), so one literal is never both.
_SLUG_ALIAS_PATTERN = r"[A-Za-z_][A-Za-z0-9_]{0,63}"

_LOAD_DATA_PATTERN_GUID = re.compile(
    rf"kontext\s*\.\s*load_data\s*\(\s*(['\"])(?P<reference>{_GUID_PATTERN})\1",
    re.IGNORECASE,
)
_LOAD_DATA_PATTERN_ALIAS = re.compile(
    rf"kontext\s*\.\s*load_data\s*\(\s*(['\"])(?P<reference>{_SLUG_ALIAS_PATTERN})\1",
    re.IGNORECASE,
)
_EXECUTE_SQL_PATTERN = re.compile(
    r"kontext\s*\.\s*execute_sql\s*\(",
    re.IGNORECASE,
)


_NAME_ALIAS_PATTERN = re.compile(rf"^{_SLUG_ALIAS_PATTERN}$")


def is_kontext_data_alias(name: str) -> bool:
    """Whether a ``kontext.load_data`` name is a slug alias vs a UUID.

    Aliases are notebook-scoped names (resolved per notebook at execution);
    UUIDs identify durable tables across sessions and must never be
    materialized or validated as notebook-local data table blocks.
    """
    return bool(_NAME_ALIAS_PATTERN.match(name or ""))


def classify_data_source_names(names: Iterable[str]) -> dict[str, list[str]]:
    """Split loadable names into notebook-scope aliases vs durable data ids.

    The two flavors share one ``load_data`` surface; this keeps
    ``list_data_sources`` (the kernel helper agents read) self-describing
    instead of one ambiguous list.
    """
    classified: dict[str, list[str]] = {"aliases": [], "data_ids": []}
    values = sorted(dict.fromkeys(names))
    for name in values:
        flavor = "aliases" if is_kontext_data_alias(name) else "data_ids"
        classified[flavor].append(name)
    return classified


def extract_kontext_load_data_ids(code: str) -> list[str]:
    """Return unique literal data references from ``kontext.load_data(...)``.

    Includes both durable data ids (UUIDs) and notebook-scope aliases; use
    :func:`is_kontext_data_alias` to tell the two apart.
    """
    seen: set[str] = set()
    data_ids: list[str] = []
    for pattern in (_LOAD_DATA_PATTERN_GUID, _LOAD_DATA_PATTERN_ALIAS):
        for match in pattern.finditer(code or ""):
            reference = match.group("reference")
            if reference in seen:
                continue
            seen.add(reference)
            data_ids.append(reference)
    return data_ids


def uses_kontext_execute_sql(code: str) -> bool:
    """Return ``True`` when the code references ``kontext.execute_sql(...)``."""
    return bool(_EXECUTE_SQL_PATTERN.search(code or ""))


__all__ = [
    "extract_kontext_load_data_ids",
    "is_kontext_data_alias",
    "uses_kontext_execute_sql",
]
