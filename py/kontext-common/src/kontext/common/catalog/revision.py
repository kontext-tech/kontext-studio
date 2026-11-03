"""Deterministic catalog content revision for cache invalidation.

A catalog connection's *revision* is a content hash of its normalized snapshot:
entity identity, column shape, and the Iceberg metadata pointer that DuckDB
views bind to. Persisting it lets a materialized query session detect that its
DuckDB views/attachments are stale, instead of the coarse "soft-delete every
session on sync" mechanism.

The helper is intentionally dependency-free so both the data layer (which
persists the revision) and the catalog layer (which decides whether a sync
changed anything) can call it without importing each other.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

#: Metadata keys that affect the DuckDB materialization. Other keys (row counts,
#: descriptions) are informational and intentionally excluded so a cosmetic
#: change does not force every session to rebuild.
_MATERIALIZATION_METADATA_KEYS = ("metadataLocation", "icebergIdentifier")


def _get(entry: Any, *names: str) -> Any:
    if isinstance(entry, Mapping):
        for name in names:
            if name in entry:
                return entry[name]
        return None
    for name in names:
        value = getattr(entry, name, None)
        if value is not None:
            return value
    return None


def _normalize_column(column: Any, index: int) -> dict[str, Any]:
    return {
        "name": str(_get(column, "name", "column_name") or ""),
        "data_type": _get(column, "data_type", "dataType"),
        "ordinal_position": _get(column, "ordinal_position", "ordinalPosition") or index,
        "nullable": bool(_get(column, "nullable") is not False),
    }


def _normalize_entry(entry: Any) -> dict[str, Any]:
    columns = _get(entry, "columns") or []
    metadata = _get(entry, "metadata") or {}
    if not isinstance(metadata, Mapping):
        metadata = {}
    materialization_metadata = {
        key: metadata.get(key)
        for key in _MATERIALIZATION_METADATA_KEYS
        if metadata.get(key) is not None
    }
    return {
        "namespace": str(_get(entry, "namespace_name", "namespace") or ""),
        "name": str(_get(entry, "entity_name", "name") or ""),
        "type": str(_get(entry, "entity_type", "entityType", "type") or ""),
        "location": _get(entry, "location"),
        "columns": [_normalize_column(column, index) for index, column in enumerate(columns)],
        "metadata": materialization_metadata,
    }


def compute_catalog_revision(entries: Iterable[Any]) -> str:
    """Return a stable content hash for a normalized catalog snapshot.

    The result is order-independent (entries are sorted by namespace/name) and
    only includes fields that affect query materialization, so re-syncing an
    unchanged catalog yields the same revision.
    """
    normalized = sorted(
        (_normalize_entry(entry) for entry in entries),
        key=lambda entry: (entry["namespace"], entry["name"]),
    )
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
