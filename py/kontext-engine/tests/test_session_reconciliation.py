"""Unit tests for DuckDB session reconciliation and federated attach."""

from __future__ import annotations

import duckdb
import pytest

from kontext.engine.session.duckdb import DuckDBQueryEngine, SessionConfig
from kontext.schema import (
    CatalogConnection,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogExecutionMode,
    CatalogSourceKind,
)


class _FakeQuerySessionService:
    async def get_query_session(self, session_id, project_id):
        return None

    async def set_catalog_revision(self, session_id, revision):
        return True


class _RecordingConnection:
    """Wraps a DuckDB connection, recording SQL and optionally failing ATTACH."""

    def __init__(self, *, fail_attach: bool = False) -> None:
        self._inner = duckdb.connect(":memory:")
        self.calls: list[str] = []
        self._fail_attach = fail_attach

    def execute(self, sql, *args, **kwargs):
        self.calls.append(sql)
        if self._fail_attach and sql.strip().startswith("ATTACH"):
            raise RuntimeError("stop before real connection")
        return self._inner.execute(sql, *args, **kwargs)


def _engine(connection: _RecordingConnection | None = None) -> DuckDBQueryEngine:
    config = SessionConfig(
        project_id="c1658a20-3558-4f89-b719-9573ef5e271b",
        session_id="c5dcdeff-aba0-43e0-95a4-b60074a01381",
        persistent=False,
    )
    engine = DuckDBQueryEngine(config, query_session_service=_FakeQuerySessionService())  # type: ignore[arg-type]
    engine.connection = connection or _RecordingConnection()  # type: ignore[assignment]
    engine.schema_manager = None
    return engine


def _postgres_connection() -> CatalogConnection:
    return CatalogConnection(
        id="c5dcdeff-aba0-43e0-95a4-b60074a01381",
        provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Postgres",
        execution_mode=CatalogExecutionMode.DUCKDBFEDERATED,
        config=CatalogConnectionConfig(
            host="127.0.0.1",
            port=1,
            database_name="analytics",
            username="reader",
        ),
        capabilities=CatalogConnectionCapabilities(),
    )


def test_drop_user_schemas_removes_stale_views_but_keeps_system_schemas() -> None:
    engine = _engine()
    connection = engine.connection
    assert connection is not None
    connection.execute("CREATE SCHEMA bronze")  # type: ignore[attr-defined]
    connection.execute("CREATE SCHEMA analytics")  # type: ignore[attr-defined]
    connection.execute("CREATE TABLE bronze.orders(id INTEGER)")  # type: ignore[attr-defined]

    engine._drop_user_schemas()

    remaining = {
        row[0]
        for row in connection.execute(  # type: ignore[attr-defined]
            "SELECT schema_name FROM duckdb_schemas()"
        ).fetchall()
    }
    assert "bronze" not in remaining
    assert "analytics" not in remaining
    assert "main" in remaining


@pytest.mark.asyncio
async def test_attach_postgres_uses_secret_without_interpolating_password(monkeypatch) -> None:
    recording = _RecordingConnection(fail_attach=True)
    engine = _engine(recording)
    engine.active_connection = _postgres_connection()

    async def _secret(_connection_id):
        return "s3cr3t-password"

    monkeypatch.setattr(engine._catalog_data_service, "get_connection_secret_async", _secret)

    with pytest.raises(RuntimeError, match="stop before real connection"):
        await engine._attach_federated_catalog()

    secret_sql = next(sql for sql in recording.calls if "CREATE OR REPLACE SECRET" in sql)
    assert "s3cr3t-password" in secret_sql
    assert "TYPE postgres" in secret_sql
    assert "HOST '127.0.0.1'" in secret_sql
    attach_sql = next(sql for sql in recording.calls if sql.strip().startswith("ATTACH"))
    assert "s3cr3t-password" not in attach_sql
    assert "SECRET" in attach_sql


@pytest.mark.asyncio
async def test_attach_is_idempotent_by_detaching_first(monkeypatch) -> None:
    recording = _RecordingConnection(fail_attach=True)
    engine = _engine(recording)
    engine.active_connection = _postgres_connection()

    async def _secret(_connection_id):
        return "pw"

    monkeypatch.setattr(engine._catalog_data_service, "get_connection_secret_async", _secret)

    with pytest.raises(RuntimeError, match="stop before real connection"):
        await engine._attach_federated_catalog()

    # The DROP SECRET is issued before the ATTACH, proving attach is idempotent.
    drop_index = next(i for i, sql in enumerate(recording.calls) if "DROP SECRET IF EXISTS" in sql)
    attach_index = next(
        i for i, sql in enumerate(recording.calls) if sql.strip().startswith("ATTACH")
    )
    assert drop_index < attach_index
