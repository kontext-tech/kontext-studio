from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from kontext.data.catalog_service import CatalogDataService, _connection_from_row
from kontext.data.models import CatalogConnection as CatalogConnectionRecord
from kontext.schema import (
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogConnectionRequest,
    CatalogSourceKind,
)


def test_connection_from_row_tolerates_legacy_capability_keys() -> None:
    """Rows persisted before a capability was removed must still load.

    Regression: an old ``supportsRelationshipDiscovery`` key in the stored
    JSON used to make ``CatalogConnectionCapabilities`` validation fail with
    ``extra_forbidden`` and break ``GET /catalog/connections``.
    """
    row = CatalogConnectionRecord(
        id=uuid4(),
        project_id=uuid4(),
        provider_kind="iceberg_internal",
        connection_kind="internal",
        display_name="Default Lakehouse",
        enabled=True,
        connection_config_json={"defaultNamespace": "bronze"},
        secret_configured=False,
        capabilities_json={
            "supportsSync": True,
            "supportsSearch": True,
            "supportsRelationshipDiscovery": True,
            "supportsWrite": True,
        },
    )

    connection = _connection_from_row(row)

    assert connection.capabilities.supports_sync is True
    assert connection.capabilities.supports_write is True


def test_connection_from_row_normalizes_catalog_timestamps_to_utc() -> None:
    row = CatalogConnectionRecord(
        id=uuid4(),
        project_id=uuid4(),
        provider_kind="postgresql_external",
        connection_kind="external",
        display_name="Postgres",
        enabled=True,
        connection_config_json={"host": "localhost", "databaseName": "postgres"},
        secret_configured=False,
        capabilities_json={},
        last_validated_at=datetime(2026, 5, 7, 0, 30, 0),
        last_synced_at=datetime(2026, 5, 7, 1, 45, 0),
    )

    connection = _connection_from_row(row)

    assert connection.last_validated_at is not None
    assert connection.last_synced_at is not None
    assert connection.last_validated_at.tzinfo == UTC
    assert connection.last_synced_at.tzinfo == UTC
    assert connection.is_query_ready is False
    assert connection.readiness_reason == "not_synced"


def test_connection_from_row_marks_external_successful_sync_as_ready() -> None:
    row = CatalogConnectionRecord(
        id=uuid4(),
        project_id=uuid4(),
        provider_kind="postgresql_external",
        connection_kind="external",
        display_name="Postgres",
        enabled=True,
        connection_config_json={"host": "localhost", "databaseName": "postgres"},
        secret_configured=False,
        capabilities_json={},
        last_sync_status="succeeded",
    )

    connection = _connection_from_row(row)

    assert connection.is_query_ready is True
    assert connection.readiness_reason is None


def test_connection_from_row_marks_secret_as_configured_when_value_is_present() -> None:
    row = CatalogConnectionRecord(
        id=uuid4(),
        project_id=uuid4(),
        provider_kind="sqlserver_external",
        connection_kind="external",
        display_name="SQL Server",
        enabled=True,
        connection_config_json={"host": "localhost", "databaseName": "master"},
        secret_configured=False,
        secret_value="P@ssw0rd!",
        capabilities_json={},
    )

    connection = _connection_from_row(row)

    assert connection.secret_configured is True


def test_connection_from_row_keeps_internal_connection_query_ready() -> None:
    row = CatalogConnectionRecord(
        id=uuid4(),
        project_id=uuid4(),
        provider_kind="iceberg_internal",
        connection_kind="internal",
        display_name="Lakehouse",
        enabled=True,
        connection_config_json={},
        secret_configured=False,
        capabilities_json={},
    )

    connection = _connection_from_row(row)

    assert connection.is_query_ready is True
    assert connection.readiness_reason is None


def test_upsert_connection_clears_stale_external_validation_and_sync_state() -> None:
    project_id = str(uuid4())
    service = CatalogDataService(project_id)
    project_uuid = UUID(project_id)
    row = CatalogConnectionRecord(
        id=uuid4(),
        project_id=project_uuid,
        provider_kind="postgresql_external",
        connection_kind="external",
        display_name="Warehouse",
        enabled=True,
        connection_config_json={"host": "old-host", "databaseName": "analytics"},
        secret_configured=False,
        capabilities_json={},
        health_status="healthy",
        last_validated_at=datetime(2026, 5, 7, 0, 30, 0, tzinfo=UTC),
        validation_error="old validation error",
        last_synced_at=datetime(2026, 5, 7, 1, 45, 0, tzinfo=UTC),
        last_sync_status="succeeded",
        last_sync_error="old sync error",
    )

    class FakeScalarResult:
        def scalar_one_or_none(self):
            return row

    class FakeSession:
        def execute(self, _stmt):
            return FakeScalarResult()

        def add(self, _row):
            return None

        def flush(self):
            return None

        def refresh(self, _row):
            return None

    @contextmanager
    def fake_session_scope(*, commit: bool = True):
        _ = commit
        yield FakeSession()

    service._session_scope = fake_session_scope  # type: ignore[method-assign]

    request = CatalogConnectionRequest(
        provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Warehouse",
        config=CatalogConnectionConfig(
            host="new-host",
            database_name="analytics",
        ),
        capabilities=CatalogConnectionCapabilities(),
    )

    connection = service.upsert_connection(request, connection_id=row.id)

    assert row.health_status is None
    assert row.last_validated_at is None
    assert row.validation_error is None
    assert row.last_synced_at is None
    assert row.last_sync_status is None
    assert row.last_sync_error is None
    assert connection.is_query_ready is False
    assert connection.readiness_reason == "not_synced"
