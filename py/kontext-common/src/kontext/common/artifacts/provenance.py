"""Helpers for recording generation provenance on persisted artifacts.

Charts (``.chart``) and data-table (``.dt``) documents are plain JSON files, so
the only durable place to record which notebook, query session, or AI chat
session produced them is inside the document itself. These helpers are shared
by every artifact-producing service so they all write an identical metadata
shape.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from kontext.schema import (
    ArtifactProvenance,
    ChartDocument,
    ChartDocumentMetadata,
    InlineData,
    InlineDataMetadata,
    TriggerActorModel,
)

from ..utils.datetime_utils import utc_now

__all__ = [
    "apply_chart_provenance",
    "apply_inline_data_provenance",
    "build_data_identity_key",
    "flatten_provenance_metadata",
    "provenance_from_document_metadata",
]


def flatten_provenance_metadata(
    metadata: ChartDocumentMetadata | InlineDataMetadata,
    provenance: ArtifactProvenance | None,
) -> None:
    """Flatten organizational provenance into a document's metadata fields.

    The ``.chart``/``.dt`` contracts store provenance flat (origin, actor,
    execution run, identity) rather than as a nested object: these documents
    are referenced from large tool-result unions where deep zod nesting pushes
    the TypeScript types past the instantiation-depth limit.
    """
    if provenance is None:
        return
    if provenance.origin is not None:
        metadata.origin = provenance.origin
    if provenance.created_by is not None:
        metadata.created_by_type = provenance.created_by.type
        metadata.created_by_id = _as_str(provenance.created_by.id)
    if provenance.execution_run_id is not None:
        metadata.execution_run_id = provenance.execution_run_id
    if provenance.identity_key is not None:
        metadata.identity_key = provenance.identity_key


def _as_str(value: UUID | str | None) -> str | None:
    return None if value is None else str(value)


def provenance_from_document_metadata(
    metadata: ChartDocumentMetadata | InlineDataMetadata | None,
) -> ArtifactProvenance | None:
    """Reconstruct an ``ArtifactProvenance`` from flattened document metadata.

    Inverse of :func:`flatten_provenance_metadata`, plus the adjacent session
    fact both document types carry. Returns ``None`` when the document has no
    origin so file-record writers can skip mirroring. ``block_id`` stays on
    result envelopes: neither ``.dt`` nor ``.chart`` metadata has a block field.
    """
    if metadata is None or metadata.origin is None:
        return None
    created_by = None
    if metadata.created_by_type is not None:
        created_by = TriggerActorModel(type=metadata.created_by_type, id=metadata.created_by_id)
    return ArtifactProvenance(
        origin=metadata.origin,
        created_by=created_by,
        execution_run_id=metadata.execution_run_id,
        chat_session_id=metadata.chat_session_id,
        identity_key=metadata.identity_key,
    )


def _scope_str(value: Any) -> str | None:
    """Normalize an execution-scope value for identity hashing.

    Enums unwrap to their ``.value`` (``QueryEngineType.DUCKDB`` == ``"DuckDB"``)
    and everything else stringifies, so callers may pass typed or raw scope
    values and every surface still hashes an identical payload. ``None`` stays
    ``None`` and hashes as JSON null.
    """
    if value is None:
        return None
    return str(getattr(value, "value", value))


def build_data_identity_key(
    sql: str,
    *,
    catalog_connection_id: Any = None,
    default_namespace: Any = None,
    default_entity_id: Any = None,
    engine_type: Any = None,
) -> str:
    """Build a stable result identity key (reuse/dedupe) from normalized SQL and scope.

    Not a derivation lineage: identical (SQL, scope, engine) executions hash to
    the same key no matter when they ran, so consumers can reuse an existing
    durable artifact instead of regenerating an equivalent result. Scope
    values are normalized via :func:`_scope_str` so the same key is produced
    whether a caller passes enum or string forms.
    """
    payload = {
        "catalog_connection_id": _scope_str(catalog_connection_id),
        "default_entity_id": _scope_str(default_entity_id),
        "default_namespace": _scope_str(default_namespace),
        "engine_type": _scope_str(engine_type),
        "sql": " ".join(sql.split()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def apply_chart_provenance(
    chart: ChartDocument,
    *,
    notebook_id: UUID | str | None = None,
    query_session_id: UUID | str | None = None,
    chat_session_id: UUID | str | None = None,
    provenance: ArtifactProvenance | None = None,
) -> None:
    """Attach generation provenance to a chart document in place.

    A metadata block is created when provenance is supplied but the document
    has none, so the linkage is never silently dropped. The SQL behind the
    chart's data is already carried by ``ChartDocument.dataRef.code``.
    """
    if all(value is None for value in (notebook_id, query_session_id, chat_session_id, provenance)):
        return

    if chart.metadata is None:
        now = utc_now()
        chart.metadata = ChartDocumentMetadata(created_at=now, modified_at=now, version="1.0.0")

    if notebook_id is not None:
        chart.metadata.notebook_id = _as_str(notebook_id)
    if query_session_id is not None:
        chart.metadata.query_session_id = _as_str(query_session_id)
    if chat_session_id is not None:
        chart.metadata.chat_session_id = _as_str(chat_session_id)
    flatten_provenance_metadata(chart.metadata, provenance)


def apply_inline_data_provenance(
    inline_data: InlineData,
    *,
    notebook_id: UUID | str | None = None,
    query_session_id: UUID | str | None = None,
    chat_session_id: UUID | str | None = None,
    sql: str | None = None,
    data_path: str | None = None,
    row_count: int | None = None,
    provenance: ArtifactProvenance | None = None,
) -> None:
    """Attach generation provenance metadata to an inline data table in place.

    ``data_path``/``row_count`` describe the columnar row store that holds the
    full result when the inline table carries only a bounded preview. The
    ``provenance`` object is flattened into the descriptor's metadata fields
    (the ``.dt`` contract stores organizational provenance flat: origin,
    producing actor, execution run, result identity); adjacent facts like
    ``sql``/``chat_session_id`` are not duplicated from it.
    """
    if all(
        value is None
        for value in (
            notebook_id,
            query_session_id,
            chat_session_id,
            sql,
            data_path,
            row_count,
            provenance,
        )
    ):
        return

    if inline_data.metadata is None:
        inline_data.metadata = InlineDataMetadata()

    metadata = inline_data.metadata
    if notebook_id is not None:
        metadata.notebook_id = _as_str(notebook_id)
    if query_session_id is not None:
        metadata.query_session_id = _as_str(query_session_id)
    if chat_session_id is not None:
        metadata.chat_session_id = _as_str(chat_session_id)
    if sql is not None:
        metadata.sql = sql
    if data_path is not None:
        metadata.data_path = data_path
    if row_count is not None:
        metadata.row_count = row_count
    flatten_provenance_metadata(metadata, provenance)
    if metadata.created_at is None:
        metadata.created_at = utc_now()
