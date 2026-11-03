from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from kontext.common.query.session_compatibility import is_session_compatible
from kontext.schema import QueryEngineType, QuerySessionModel, QuerySessionStatus


def _session(
    *,
    engine_type: QueryEngineType,
    catalog_connection_id: str | None,
) -> QuerySessionModel:
    return QuerySessionModel.model_construct(
        id=str(uuid4()),
        project_id=str(uuid4()),
        session_name="Session",
        status=QuerySessionStatus.ACTIVE,
        engine_type=engine_type,
        catalog_connection_id=catalog_connection_id,
        created_at=datetime.now(UTC),
    )


def test_inprocess_session_compatibility_rejects_broken_live_sql_session() -> None:
    session = _session(
        engine_type=QueryEngineType.SQLSERVER,
        catalog_connection_id=None,
    )

    assert is_session_compatible(session, engine_type=QueryEngineType.SQLSERVER) is False


def test_inprocess_session_compatibility_allows_duckdb_without_catalog_connection() -> None:
    session = _session(
        engine_type=QueryEngineType.DUCKDB,
        catalog_connection_id=None,
    )

    assert is_session_compatible(session) is True
