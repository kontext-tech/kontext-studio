from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from kontext.common.catalog.connector_specs import get_catalog_connector_spec
from kontext.engine.session.live_sql import LiveSqlQueryEngine, LiveSqlSessionConfig
from kontext.schema import (
    CatalogConnection,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogSourceKind,
)


def _build_query_engine(database_path: Path) -> LiveSqlQueryEngine:
    engine = LiveSqlQueryEngine(
        LiveSqlSessionConfig(
            project_id="project-1",
            catalog_connection_id="connection-1",
        )
    )
    engine._engine = create_engine(f"sqlite:///{database_path}")
    engine._connection = CatalogConnection(
        id=str(uuid4()),
        provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="SQLite Test",
        config=CatalogConnectionConfig(
            database_path=str(database_path),
            default_namespace="main",
        ),
        capabilities=CatalogConnectionCapabilities(),
    )
    engine._spec = get_catalog_connector_spec(CatalogSourceKind.SQLITEEXTERNAL)
    return engine


@pytest.mark.asyncio
async def test_fetch_data_table_uses_string_column_types(tmp_path: Path) -> None:
    query_engine = _build_query_engine(tmp_path / "live-sql-fetch.db")
    sqlalchemy_engine = query_engine._engine
    assert sqlalchemy_engine is not None

    with sqlalchemy_engine.begin() as connection:
        connection.execute(text("CREATE TABLE metrics (total INTEGER NOT NULL)"))
        connection.execute(text("INSERT INTO metrics (total) VALUES (1)"))

    table = await query_engine.fetch_data_table("SELECT total FROM metrics")
    columns = table.columns
    assert columns is not None

    assert len(columns) == 1
    assert columns[0].name == "total"
    assert columns[0].type == "unknown"
    assert table.rows == [[1]]
    assert table.row_count == 1


@pytest.mark.asyncio
async def test_discover_table_uses_connected_catalog_spec(tmp_path: Path) -> None:
    query_engine = _build_query_engine(tmp_path / "live-sql-discover.db")
    sqlalchemy_engine = query_engine._engine
    assert sqlalchemy_engine is not None

    with sqlalchemy_engine.begin() as connection:
        connection.execute(text("CREATE TABLE widgets (id INTEGER PRIMARY KEY, name TEXT)"))

    table = await query_engine.discover_table("main", "widgets")

    assert table is not None
    assert table.catalog_name == "SQLite Test"
    assert (
        table.engine_type
        == get_catalog_connector_spec(CatalogSourceKind.SQLITEEXTERNAL).query_engine_type
    )
    assert table.table.table_name == "widgets"
    assert [column.name for column in table.table.columns] == ["id", "name"]
