"""Shared query-session compatibility helpers.

These are pure predicates over the generated ``QuerySessionModel`` contract, so
they live in ``kontext-common`` and are usable by the query orchestration layer,
the in-process execution adapter, and the Python client without any of them
depending on each other.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from kontext.schema import QueryEngineType, QuerySessionModel, QuerySessionStatus


def normalize_engine_value(engine_type: QueryEngineType | str | None) -> str | None:
    """Normalize enum and string engine values for comparisons."""
    if engine_type is None:
        return None
    if isinstance(engine_type, QueryEngineType):
        return str(engine_type.value).lower()
    return str(engine_type).lower()


def requires_catalog_connection(
    engine_type: QueryEngineType | str | None,
) -> bool:
    """Return whether the engine requires a catalog-backed live SQL scope."""
    return normalize_engine_value(engine_type) in {
        normalize_engine_value(QueryEngineType.SQLSERVER),
        normalize_engine_value(QueryEngineType.ORACLE),
        normalize_engine_value(QueryEngineType.TERADATA),
    }


def get_session_timestamp(session: QuerySessionModel) -> float:
    """Get the best available timestamp for session preference ordering."""
    for value in (
        session.last_accessed_at,
        session.updated_at,
        session.created_at,
    ):
        if not value:
            continue
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
    return 0.0


def is_session_compatible(
    session: QuerySessionModel,
    *,
    expected_session_id: UUID | str | None = None,
    catalog_connection_id: UUID | str | None = None,
    default_namespace: str | None = None,
    default_entity_id: UUID | str | None = None,
    engine_type: QueryEngineType | str | None = None,
    expected_catalog_revision: str | None = None,
) -> bool:
    """Return whether an existing session is safe to reuse."""
    if session.status not in (
        QuerySessionStatus.ACTIVE,
        QuerySessionStatus.INITIALIZING,
    ):
        return False

    if expected_session_id and str(session.id) != str(expected_session_id):
        return False

    # A session materializes the catalog at initialization time. If the catalog
    # has since changed, its DuckDB views/attachments are stale: reject reuse so
    # a fresh session is built (and the stale file is cleaned up by the caller).
    if (
        expected_catalog_revision
        and getattr(session, "catalog_revision", None)
        and session.catalog_revision != expected_catalog_revision
    ):
        return False

    effective_engine = engine_type or session.engine_type
    if (
        requires_catalog_connection(effective_engine)
        and not str(session.catalog_connection_id or "").strip()
    ):
        return False

    if catalog_connection_id and str(session.catalog_connection_id or "") != str(
        catalog_connection_id
    ):
        return False

    if default_namespace and session.default_namespace != default_namespace:
        return False

    if default_entity_id and str(session.default_entity_id or "") != str(default_entity_id):
        return False

    expected_engine = normalize_engine_value(engine_type)
    session_engine = normalize_engine_value(session.engine_type)
    return not (expected_engine and session_engine != expected_engine)


def sort_sessions_by_preference(
    sessions: list[QuerySessionModel],
) -> list[QuerySessionModel]:
    """Prefer active sessions, then the most recently touched ones."""
    return sorted(
        sessions,
        key=lambda session: (
            0 if session.status == QuerySessionStatus.ACTIVE else 1,
            -get_session_timestamp(session),
        ),
    )
