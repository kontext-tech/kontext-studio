"""
Engine end-to-end tests.

Validates the runtime ``LocalRuntimeProvider`` and ``LocalJobRunService``
integration against a real local storage back-end (temporary directory).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from kontext.schema import (
    CatalogEntityDetail,
    CatalogEntitySummary,
    CatalogEntityType,
)
from kontext.storage.engine.local import LocalStorageEngine, _write_json


@pytest.fixture()
def _local_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Spin up a LocalStorageEngine backed by *tmp_path* and register it."""
    monkeypatch.setenv("KONTEXT_LAKE_PATH", str(tmp_path / "lake"))
    monkeypatch.setenv("PROJECT_DB_URL", f"sqlite:///{tmp_path}/kontext.db")

    from kontext.data.database import Base, get_session_factory
    from kontext.data.database import get_engine as get_db_engine

    get_db_engine.cache_clear()
    get_session_factory.cache_clear()
    Base.metadata.create_all(get_db_engine())

    engine = LocalStorageEngine()
    yield engine

    get_db_engine.cache_clear()
    get_session_factory.cache_clear()


def _seed_project(engine: LocalStorageEngine) -> str:
    """Create a minimal project and return its id."""
    pid = str(uuid4())
    engine.ensure_project_structure(pid)
    project_data = {
        "id": pid,
        "project_name": "test-project",
        "project_code": "test",
        "project_description": "",
        "access_level": "Private",
        "configuration": {},
        "owner_id": str(uuid4()),
        "date_created": "2025-01-01T00:00:00Z",
        "is_deleted": False,
    }
    project_dir = engine._project_dir(pid)
    _write_json(project_dir / "config" / "project.json", project_data)
    engine.put_global(
        "projects-index",
        [{"id": pid, "project_code": "test", "project_name": "test-project"}],
    )
    return pid


class TestLocalRuntimeProvider:
    """Integration tests for LocalRuntimeProvider."""

    def test_construction(self, _local_engine):
        from kontext.runtime.providers.local import LocalRuntimeProvider

        pid = _seed_project(_local_engine)
        provider = LocalRuntimeProvider(project_id=pid)
        assert provider is not None

    def test_get_file_service(self, _local_engine):
        from kontext.runtime.providers.local import LocalRuntimeProvider

        pid = _seed_project(_local_engine)
        provider = LocalRuntimeProvider(project_id=pid)
        svc = provider.get_file_service()
        assert svc is not None

    def test_get_job_run_service(self, _local_engine):
        from kontext.runtime.providers.local import LocalRuntimeProvider

        pid = _seed_project(_local_engine)
        provider = LocalRuntimeProvider(project_id=pid)
        svc = provider.get_job_run_service()
        assert svc is not None

    def test_get_live_sql_query_engine(self, _local_engine):
        from kontext.common.query.engine import QueryEngineRequest
        from kontext.runtime.providers.local import LocalRuntimeProvider
        from kontext.schema import QueryEngineType

        pid = _seed_project(_local_engine)
        provider = LocalRuntimeProvider(project_id=pid)
        engine = provider.get_query_execution_engine(
            QueryEngineType.SQLSERVER,
            request=QueryEngineRequest(
                project_id=pid,
                catalog_connection_id=str(uuid4()),
            ),
        )

        assert engine is not None
        assert engine.__class__.__name__ == "LiveSqlQueryEngine"


class TestLocalJobRunService:
    """Integration tests for LocalJobRunService."""

    def test_construction(self, _local_engine):
        from kontext.engine.adapters import LocalJobRunService

        pid = _seed_project(_local_engine)
        svc = LocalJobRunService(pid)
        assert svc is not None


class TestJobExecutionService:
    """Integration tests for the job execution pipeline."""

    def test_construction(self, _local_engine):
        from kontext.engine.adapters import LocalJobRunService
        from kontext.jobs.job_execution_service import JobExecutionService
        from kontext.runtime.providers.local import LocalRuntimeProvider

        pid = _seed_project(_local_engine)
        provider = LocalRuntimeProvider(project_id=pid)
        run_svc = LocalJobRunService(pid)
        exec_svc = JobExecutionService(project_id=pid, runtime_provider=provider, service=run_svc)
        assert exec_svc is not None


class TestJobRegistry:
    """Verify the job registry discovers built-in jobs correctly."""

    def test_discovers_document_indexing_job(self):
        from kontext.jobs.job_registry import PythonJobRegistry

        registry = PythonJobRegistry()
        assert registry.is_job_registered("python.jobs.DocumentIndexingJob")

    def test_list_all_jobs(self):
        from kontext.jobs.job_registry import PythonJobRegistry

        registry = PythonJobRegistry()
        jobs = registry.get_all_jobs()
        assert len(jobs) > 0
        types = [j.type for j in jobs]
        assert "python.jobs.DocumentIndexingJob" in types

    def test_discovers_execute_notebook_python_job(self):
        from kontext.jobs.job_registry import PythonJobRegistry

        registry = PythonJobRegistry()
        assert registry.is_job_registered("python.jobs.ExecuteNotebookPythonJob")


@pytest.mark.asyncio
async def test_duckdb_engine_dispose_keeps_persisted_query_session() -> None:
    from kontext.engine.session.duckdb import DuckDBQueryEngine, SessionConfig

    query_session_service = AsyncMock()
    engine = DuckDBQueryEngine(
        SessionConfig(
            project_id=str(uuid4()),
            session_id=str(uuid4()),
            persistent=True,
        ),
        query_session_service=query_session_service,
    )
    connection = MagicMock()
    engine.connection = connection
    engine.is_initialized = True

    await engine.dispose()

    query_session_service.close_query_session.assert_not_awaited()
    connection.close.assert_called_once()
    assert engine.connection is None
    assert engine.is_initialized is False


def _build_duckdb_engine(schema_mapping: dict[str, str]):
    import duckdb

    from kontext.engine.session.duckdb import DuckDBQueryEngine, SessionConfig

    engine = DuckDBQueryEngine(
        SessionConfig(
            project_id=str(uuid4()),
            session_id=str(uuid4()),
            persistent=False,
        ),
        query_session_service=AsyncMock(),
    )
    engine.connection = duckdb.connect()
    engine.is_initialized = True
    engine.schema_mapping = schema_mapping
    return engine


@pytest.mark.asyncio
async def test_duckdb_discover_table_escapes_hostile_identifiers() -> None:
    engine = _build_duckdb_engine({"main": "main"})
    assert engine.connection is not None
    engine.connection.execute("CREATE TABLE widgets (id INTEGER, name VARCHAR)")

    table = await engine.discover_table("main", "widgets")
    assert table is not None
    assert [column.name for column in table.table.columns] == ["id", "name"]

    # A quote in an identifier must not break out of the parameter binding.
    missing = await engine.discover_table("main' OR '1'='1", "widgets")
    assert missing is None


@pytest.mark.asyncio
async def test_duckdb_fetch_data_table_is_bounded_in_the_query_plan() -> None:
    engine = _build_duckdb_engine({"main": "main"})
    assert engine.connection is not None
    engine.connection.execute("CREATE TABLE numbers AS SELECT range AS i FROM range(1000)")

    table = await engine.fetch_data_table("SELECT * FROM numbers", max_rows=10)

    assert table is not None
    assert table.row_count == 10
    assert len(table.rows or []) == 10


@pytest.mark.asyncio
async def test_duckdb_validate_sql_rejects_writes_but_allows_reads() -> None:
    engine = _build_duckdb_engine({"main": "main"})
    assert engine.connection is not None
    engine.connection.execute("CREATE TABLE widgets (id INTEGER)")

    ok, error = await engine.validate_sql("SELECT * FROM widgets")
    assert ok is True
    assert error is None

    ok, error = await engine.validate_sql("CREATE TABLE injected (id INTEGER)")
    assert ok is False
    assert error is not None

    # The rejected statement must not have been executed.
    assert engine.connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'injected'"
    ).fetchone() == (0,)

    # Prefixed write-plan variants (BATCH_INSERT, CREATE_TABLE_AS in 1.x; the
    # title-case renderings of DuckDB 2.0) must be recognized as writes too.
    for statement in (
        "CREATE TABLE injected AS SELECT 1",
        "INSERT INTO widgets VALUES (1)",
        "DELETE FROM widgets",
        "UPDATE widgets SET id = 2",
    ):
        ok, error = await engine.validate_sql(statement)
        assert ok is False, statement
        assert error is not None

    assert engine.connection.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'injected'"
    ).fetchone() == (0,)

    # Unknown columns must still be reported as invalid.
    ok, error = await engine.validate_sql("SELECT missing_column FROM widgets")
    assert ok is False
    assert error is not None


@pytest.mark.asyncio
async def test_duckdb_execution_serializes_on_single_connection() -> None:
    engine = _build_duckdb_engine({"main": "main"})
    assert engine.connection is not None
    engine.connection.execute("CREATE TABLE t AS SELECT range AS i FROM range(100)")

    results = await asyncio.gather(
        engine.fetch_data_table("SELECT * FROM t", max_rows=5),
        engine.fetch_data_table("SELECT * FROM t", max_rows=5),
    )

    assert all(result.row_count == 5 for result in results)


@pytest.mark.asyncio
async def test_duckdb_catalog_views_use_metadata_location() -> None:
    from kontext.engine.session.duckdb import DuckDBQueryEngine, SessionConfig

    project_id = str(uuid4())
    connection_id = str(uuid4())
    entity_id = str(uuid4())
    metadata_location = "file:///tmp/lakehouse/project/bronze/orders/metadata/v1.metadata.json"
    query_session_service = AsyncMock()
    engine = DuckDBQueryEngine(
        SessionConfig(
            project_id=project_id,
            session_id=str(uuid4()),
            persistent=False,
        ),
        query_session_service=query_session_service,
    )
    engine.connection = MagicMock()
    engine.connection.execute = MagicMock(return_value=MagicMock())
    engine.catalog_entities = {
        "bronze": [
            CatalogEntityDetail(
                entity=CatalogEntitySummary(
                    id=entity_id,
                    connection_id=connection_id,
                    namespace_name="bronze",
                    entity_name="orders",
                    entity_type=CatalogEntityType.TABLE,
                    column_count=0,
                    metadata={"metadataLocation": metadata_location},
                ),
                columns=[],
            )
        ]
    }

    await engine._create_catalog_views()

    engine.connection.execute.assert_called_once_with(
        'CREATE OR REPLACE VIEW "bronze"."orders" AS '
        f"SELECT * FROM iceberg_scan('{metadata_location}')"
    )
