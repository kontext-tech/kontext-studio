from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from kontext.catalog.connections.management import CatalogManagementService
from kontext.catalog.connections.providers import (
    SUPPORTED_EXTERNAL_PROFILES,
    DuckDbExternalCatalogProvider,
    SqlAlchemyExternalCatalogProvider,
)
from kontext.common.catalog.connector_specs import build_sqlalchemy_connection_url
from kontext.common.utils.path_policy import PathAccessDeniedError
from kontext.data.catalog_service import CatalogEntitySnapshot
from kontext.schema import (
    CatalogColumn,
    CatalogConnection,
    CatalogConnectionAuthType,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogConnectionRequest,
    CatalogConnectionValidationResult,
    CatalogEntityType,
    CatalogExecutionMode,
    CatalogSourceCategory,
    CatalogSourceKind,
)


@pytest.mark.asyncio
async def test_search_combines_enabled_connections(monkeypatch):
    project_id = "00000000-0000-0000-0000-000000000001"
    service = CatalogManagementService(project_id)

    connection_a = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
        connection_kind=CatalogConnectionKind.INTERNAL,
        display_name="A",
        enabled=True,
        config=CatalogConnectionConfig(),
        capabilities=CatalogConnectionCapabilities(),
    )
    connection_b = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000b",
        provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="B",
        enabled=False,
        config=CatalogConnectionConfig(),
        capabilities=CatalogConnectionCapabilities(),
    )

    async def fake_list_connections():
        return [connection_a, connection_b]

    async def fake_search(**kwargs):
        return [
            SimpleNamespace(
                schema_name="raw",
                table_name="customers",
                description="Customers",
                content="customers",
                score=0.2,
                connection_id=kwargs["catalog_connection_id"],
            )
        ]

    monkeypatch.setattr(service, "list_connections", fake_list_connections)
    monkeypatch.setattr(service.index_service, "search", fake_search)

    results = await service.search(query="customers")

    assert len(results) == 1
    assert results[0].connection_id == connection_a.id


@pytest.mark.asyncio
async def test_search_orders_combined_results_by_descending_score(monkeypatch):
    project_id = "00000000-0000-0000-0000-0000000000f1"
    service = CatalogManagementService(project_id)

    connection_a = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
        connection_kind=CatalogConnectionKind.INTERNAL,
        display_name="A",
        enabled=True,
        config=CatalogConnectionConfig(),
        capabilities=CatalogConnectionCapabilities(),
    )
    connection_b = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000b",
        provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="B",
        enabled=True,
        config=CatalogConnectionConfig(),
        capabilities=CatalogConnectionCapabilities(),
    )

    async def fake_list_connections():
        return [connection_a, connection_b]

    async def fake_search(**kwargs):
        score = 0.2 if kwargs["catalog_connection_id"] == connection_a.id else 0.9
        table_name = "customers" if score == 0.2 else "orders"
        return [
            SimpleNamespace(
                schema_name="raw",
                table_name=table_name,
                description=table_name.title(),
                content=table_name,
                score=score,
                connection_id=kwargs["catalog_connection_id"],
            )
        ]

    monkeypatch.setattr(service, "list_connections", fake_list_connections)
    monkeypatch.setattr(service.index_service, "search", fake_search)

    results = await service.search(query="tables", limit=2)

    assert [item.table_name for item in results] == ["orders", "customers"]
    assert [item.score for item in results] == [0.9, 0.2]


@pytest.mark.asyncio
async def test_sync_connection_indexes_provider_snapshot(monkeypatch):
    project_id = "00000000-0000-0000-0000-000000000001"
    service = CatalogManagementService(project_id)
    initial_connection = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        project_id=project_id,
        provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
        connection_kind=CatalogConnectionKind.INTERNAL,
        display_name="Default",
        config=CatalogConnectionConfig(),
        capabilities=CatalogConnectionCapabilities(),
    )
    refreshed_connection = initial_connection.model_copy(update={"last_sync_status": "succeeded"})

    snapshot = CatalogEntitySnapshot(
        namespace_name="raw",
        entity_name="customers",
        entity_type=CatalogEntityType.TABLE,
        columns=[CatalogColumn(name="customer_id", data_type="TEXT")],
    )

    get_connection_calls = 0

    async def fake_get_connection_async(connection_id):
        nonlocal get_connection_calls
        get_connection_calls += 1
        return initial_connection if get_connection_calls == 1 else refreshed_connection

    async def fake_update_sync_status_async(connection_id, **kwargs):
        return SimpleNamespace(connection_id=connection_id, status=kwargs["status"])

    async def fake_replace_connection_snapshot_async(connection_id, entities, **kwargs):
        assert entities == [snapshot]
        return SimpleNamespace(connection_id=connection_id, status="succeeded")

    async def fake_list_entity_details_for_connection_async(connection_id):
        return []

    async def fake_index_catalog_entities(**kwargs):
        assert kwargs["connection"] == refreshed_connection
        return None

    async def fake_index_knowledge(*, recreate: bool = False):
        assert recreate is True
        return 0

    async def fake_provider_sync(_connection):
        return [snapshot]

    def fake_invalidate_sessions_for_catalog_connection(
        self, connection_id, reason="Catalog metadata changed"
    ):
        _ = self
        assert connection_id == initial_connection.id
        assert reason == "Catalog metadata changed"
        return []

    monkeypatch.setattr(service.data_service, "get_connection_async", fake_get_connection_async)
    monkeypatch.setattr(
        service.data_service, "update_sync_status_async", fake_update_sync_status_async
    )
    monkeypatch.setattr(
        service.data_service,
        "replace_connection_snapshot_async",
        fake_replace_connection_snapshot_async,
    )
    monkeypatch.setattr(
        service.data_service,
        "list_entity_details_for_connection_async",
        fake_list_entity_details_for_connection_async,
    )
    monkeypatch.setattr(
        service.index_service, "index_catalog_entities", fake_index_catalog_entities
    )
    monkeypatch.setattr(service.index_service, "index_knowledge", fake_index_knowledge)
    monkeypatch.setattr(
        service.provider_registry,
        "get",
        lambda provider_kind: SimpleNamespace(sync=fake_provider_sync),
    )
    monkeypatch.setattr(
        "kontext.catalog.connections.management.QuerySessionDataService.invalidate_sessions_for_catalog_connection",
        fake_invalidate_sessions_for_catalog_connection,
    )

    result = await service.sync_connection(initial_connection.id or "")

    assert result.status == "succeeded"
    assert get_connection_calls == 2


@pytest.mark.asyncio
async def test_validate_connection_updates_validation_status(monkeypatch):
    project_id = "00000000-0000-0000-0000-000000000001"
    service = CatalogManagementService(project_id)
    connection = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        project_id=project_id,
        provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Postgres",
        config=CatalogConnectionConfig(
            host="localhost",
            port=5432,
            database_name="postgres",
            username="postgres",
        ),
        capabilities=CatalogConnectionCapabilities(),
    )
    validation_result = CatalogConnectionValidationResult(
        connection_id=connection.id or "",
        status="succeeded",
        validated_at=datetime.now(UTC),
        message="ok",
    )
    recorded: dict[str, object] = {}

    async def fake_get_connection_async(connection_id):
        assert connection_id == connection.id
        return connection

    async def fake_update_validation_status_async(connection_id, **kwargs):
        recorded["connection_id"] = connection_id
        recorded["status"] = kwargs["status"]
        recorded["message"] = kwargs["message"]
        return validation_result

    async def fake_validate(_connection):
        return validation_result

    monkeypatch.setattr(service.data_service, "get_connection_async", fake_get_connection_async)
    monkeypatch.setattr(
        service.data_service,
        "update_validation_status_async",
        fake_update_validation_status_async,
    )
    monkeypatch.setattr(
        service.provider_registry,
        "get",
        lambda provider_kind: SimpleNamespace(validate=fake_validate),
    )

    result = await service.validate_connection(connection.id or "")

    assert result.status == "succeeded"
    assert recorded["connection_id"] == connection.id
    assert recorded["message"] == "ok"


@pytest.mark.asyncio
async def test_list_connections_always_ensures_default_internal_connection(
    monkeypatch,
):
    project_id = "00000000-0000-0000-0000-000000000001"
    service = CatalogManagementService(project_id)
    ensured_connection = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        project_id=project_id,
        provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
        connection_kind=CatalogConnectionKind.INTERNAL,
        display_name="Default Lakehouse",
        enabled=True,
        config=CatalogConnectionConfig(),
        capabilities=CatalogConnectionCapabilities(),
    )
    ensure_calls = 0

    async def fake_ensure_default_internal_connection():
        nonlocal ensure_calls
        ensure_calls += 1
        return ensured_connection

    async def fake_list_connections_async():
        return [ensured_connection]

    monkeypatch.setattr(
        service,
        "ensure_default_internal_connection",
        fake_ensure_default_internal_connection,
    )
    monkeypatch.setattr(service.data_service, "list_connections_async", fake_list_connections_async)

    result = await service.list_connections()

    assert ensure_calls == 1
    assert result == [ensured_connection]


def test_postgres_external_provider_build_url_preserves_password() -> None:
    project_id = "00000000-0000-0000-0000-000000000001"
    profile = next(
        item
        for item in SUPPORTED_EXTERNAL_PROFILES
        if item.provider_kind == CatalogSourceKind.POSTGRESQLEXTERNAL
    )
    provider = SqlAlchemyExternalCatalogProvider(project_id, profile)
    connection = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        project_id=project_id,
        provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Postgres",
        config=CatalogConnectionConfig(
            host="localhost",
            port=5432,
            database_name="postgres",
            username="postgres",
        ),
        capabilities=CatalogConnectionCapabilities(),
    )

    url = provider._build_url(connection, "secret-password")

    assert url == ("postgresql+psycopg://postgres:secret-password@localhost:5432/postgres")


@pytest.mark.asyncio
async def test_sqlite_external_provider_introspects_live_database(tmp_path, monkeypatch):
    db_path = tmp_path / "external.db"
    # The database lives outside the managed storage tree, so it must be
    # explicitly allowlisted for the connection to be usable.
    monkeypatch.setenv("KONTEXT_ALLOWED_PATHS", str(tmp_path))
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE customers (customer_id TEXT PRIMARY KEY, email TEXT)"))
    finally:
        engine.dispose()

    provider = SqlAlchemyExternalCatalogProvider(
        "00000000-0000-0000-0000-000000000001",
        next(
            profile
            for profile in SUPPORTED_EXTERNAL_PROFILES
            if profile.provider_kind == CatalogSourceKind.SQLITEEXTERNAL
        ),
    )

    async def fake_get_connection_secret_async(_connection_id):
        return None

    monkeypatch.setattr(
        provider._catalog_data_service,
        "get_connection_secret_async",
        fake_get_connection_secret_async,
    )

    connection = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="SQLite",
        config=CatalogConnectionConfig(database_path=str(db_path)),
        capabilities=CatalogConnectionCapabilities(),
    )

    snapshots = await provider.sync(connection)

    assert len(snapshots) == 1
    assert snapshots[0].namespace_name == "main"
    assert snapshots[0].entity_name == "customers"
    assert [column.name for column in snapshots[0].columns] == [
        "customer_id",
        "email",
    ]


def _sqlite_connection(database_path: str) -> CatalogConnection:
    return CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="SQLite",
        config=CatalogConnectionConfig(database_path=database_path),
        capabilities=CatalogConnectionCapabilities(),
    )


def test_sqlite_connection_url_rejects_path_outside_allowed_roots(monkeypatch, tmp_path):
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("KONTEXT_ALLOWED_PATHS", raising=False)

    with pytest.raises(PathAccessDeniedError):
        build_sqlalchemy_connection_url(_sqlite_connection("/etc/passwd"))


def test_sqlite_connection_url_allows_path_under_allowed_root(monkeypatch, tmp_path):
    allowed = tmp_path / "data"
    allowed.mkdir()
    monkeypatch.setenv("KONTEXT_ALLOWED_PATHS", str(allowed))

    url = build_sqlalchemy_connection_url(_sqlite_connection(str(allowed / "external.db")))

    assert url == f"sqlite:///{allowed / 'external.db'}"


@pytest.mark.asyncio
async def test_duckdb_external_validate_rejects_path_outside_allowed_roots(monkeypatch, tmp_path):
    monkeypatch.setenv("FILE_STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.delenv("KONTEXT_ALLOWED_PATHS", raising=False)
    provider = DuckDbExternalCatalogProvider(
        "00000000-0000-0000-0000-000000000001",
        next(
            profile
            for profile in SUPPORTED_EXTERNAL_PROFILES
            if profile.provider_kind == CatalogSourceKind.DUCKDBEXTERNAL
        ),
    )
    connection = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        provider_kind=CatalogSourceKind.DUCKDBEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="DuckDB",
        config=CatalogConnectionConfig(database_path="/etc/passwd"),
        capabilities=CatalogConnectionCapabilities(),
    )

    result = await provider.validate(connection)

    assert result.status == "failed"
    assert result.error_message and "allowed" in result.error_message.lower()


@pytest.mark.asyncio
async def test_list_provider_definitions_excludes_unavailable_providers():
    service = CatalogManagementService("00000000-0000-0000-0000-000000000001")

    definitions = await service.list_provider_definitions()

    provider_kinds = {definition.provider_kind for definition in definitions}
    assert CatalogSourceKind.ICEBERGINTERNAL in provider_kinds
    assert CatalogSourceKind.DUCKDBEXTERNAL in provider_kinds
    assert CatalogSourceKind.MYSQLEXTERNAL in provider_kinds
    assert CatalogSourceKind.ORACLEEXTERNAL in provider_kinds
    assert CatalogSourceKind.POSTGRESQLEXTERNAL in provider_kinds
    assert CatalogSourceKind.SQLSERVEREXTERNAL in provider_kinds
    assert CatalogSourceKind.TERADATAEXTERNAL in provider_kinds
    assert CatalogSourceKind.SQLITEEXTERNAL in provider_kinds
    assert CatalogSourceKind.SNOWFLAKEEXTERNAL not in provider_kinds


@pytest.mark.asyncio
async def test_create_connection_normalizes_provider_metadata(monkeypatch):
    project_id = "00000000-0000-0000-0000-000000000001"
    service = CatalogManagementService(project_id)
    recorded: dict[str, object] = {}

    async def fake_upsert_connection_async(request, **kwargs):
        recorded["request"] = request
        return CatalogConnection(
            id="00000000-0000-0000-0000-00000000000a",
            project_id=project_id,
            provider_kind=request.provider_kind,
            connection_kind=request.connection_kind,
            display_name=request.display_name,
            source_category=request.source_category,
            auth_type=request.auth_type,
            execution_mode=request.execution_mode,
            config=request.config,
            capabilities=request.capabilities or CatalogConnectionCapabilities(),
        )

    monkeypatch.setattr(
        service.data_service, "upsert_connection_async", fake_upsert_connection_async
    )

    request = CatalogConnectionRequest(
        provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="SQLite",
        source_category=CatalogSourceCategory.API,
        auth_type=CatalogConnectionAuthType.SECRETREF,
        config=CatalogConnectionConfig(database_path="/tmp/demo.db"),
        capabilities=CatalogConnectionCapabilities(supports_write=True),
    )

    with pytest.raises(ValueError, match=r"SQLite requires source category sql\."):
        await service.create_connection(request)

    valid_request = request.model_copy(
        update={
            "source_category": None,
            "auth_type": None,
            "capabilities": CatalogConnectionCapabilities(supports_write=True),
        }
    )

    result = await service.create_connection(valid_request)

    normalized_request = recorded["request"]
    assert isinstance(normalized_request, CatalogConnectionRequest)
    assert normalized_request.source_category == CatalogSourceCategory.SQL
    assert normalized_request.auth_type == CatalogConnectionAuthType.NONE
    assert normalized_request.execution_mode == CatalogExecutionMode.DUCKDBFEDERATED
    assert normalized_request.capabilities is not None
    assert normalized_request.capabilities.supports_write is False
    assert result.execution_mode == CatalogExecutionMode.DUCKDBFEDERATED


@pytest.mark.asyncio
async def test_create_connection_rejects_unsupported_execution_mode():
    service = CatalogManagementService("00000000-0000-0000-0000-000000000001")

    request = CatalogConnectionRequest(
        provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Postgres",
        execution_mode=CatalogExecutionMode.NATIVEPUSHDOWN,
        config=CatalogConnectionConfig(
            host="localhost",
            port=5432,
            database_name="postgres",
            username="postgres",
        ),
    )

    with pytest.raises(
        ValueError,
        match=("PostgreSQL does not support execution mode native_pushdown"),
    ):
        await service.create_connection(request)
