from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from kontext.api.dependencies import AuthContext
from kontext.api.main import app
from kontext.api.routers.catalog import CATALOG_READ_AUTH, CATALOG_WRITE_AUTH
from kontext.schema import (
    AccessLevel,
    CatalogColumn,
    CatalogConnection,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogConnectionRequest,
    CatalogConnectionValidationResult,
    CatalogEntityDetail,
    CatalogEntitySummary,
    CatalogEntityType,
    CatalogNamespaceSummary,
    CatalogProviderDefinition,
    CatalogSearchItem,
    CatalogSourceKind,
    CatalogSyncStatus,
    ProjectConfiguration,
    ProjectModel,
    UserType,
    UserWithRolesModel,
)


class _BenignRuntimeProfile:
    """Lifespan tests must not initialize a real runtime (DB, storage, seed).

    Kontext fails fast when the active runtime profile cannot initialize;
    these tests enter the lifespan in the default (cloud) profile, so they
    swap in a benign stand-in instead of forcing local mode and touching real
    infrastructure.
    """

    name = "test"
    identity_backend = "test-identity"
    relational_backend = "test-relational"
    storage_backend = "test-storage"
    execution_backend = "test-execution"

    def initialize(self) -> None:
        return None


def _mock_auth(project_id: str) -> AuthContext:
    user_id = str(uuid.uuid4())
    project = ProjectModel(
        access_level=AccessLevel.PRIVATE,
        date_created=datetime.now(UTC),
        id=project_id,
        project_name="Test Project",
        project_code="TEST",
        owner_id=str(uuid.uuid4()),
        is_deleted=False,
        configuration=ProjectConfiguration(
            allowed_file_types=[],
            max_file_bytes_size=0,
            total_storage_allocation_bytes=0,
            features=[],
        ),
    )
    user = UserWithRolesModel(
        id=user_id,
        first_name="Test",
        last_name="User",
        user_type=UserType.USER,
        roles=[],
        permission_claims=[],
        project_roles={},
    )
    return AuthContext(project=project, user=user)


def test_catalog_routes_use_management_service(monkeypatch):
    project_id = str(uuid.uuid4())
    recorded: dict[str, Any] = {}
    recorded_connection_id = str(uuid.uuid4())
    recorded_entity_id = str(uuid.uuid4())
    runtime_provider = object()

    monkeypatch.setattr(
        "kontext.api.main.get_runtime_profile",
        lambda: _BenignRuntimeProfile(),
    )

    class FakeCatalogManagementService:
        def __init__(self, project_id: str, runtime_provider=None) -> None:
            recorded["project_id"] = project_id
            recorded["runtime_provider"] = runtime_provider

        async def list_provider_definitions(self):
            return [
                CatalogProviderDefinition(
                    provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
                    connection_kind=CatalogConnectionKind.INTERNAL,
                    display_name="Internal",
                    capabilities=CatalogConnectionCapabilities(),
                )
            ]

        async def list_connections(self):
            return [
                CatalogConnection(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
                    connection_kind=CatalogConnectionKind.INTERNAL,
                    display_name="Default",
                    config=CatalogConnectionConfig(),
                    capabilities=CatalogConnectionCapabilities(),
                )
            ]

        async def create_connection(self, request, owner_id=None):
            recorded["created"] = request.display_name
            return CatalogConnection(
                id=str(uuid.uuid4()),
                project_id=project_id,
                provider_kind=request.provider_kind,
                connection_kind=request.connection_kind,
                display_name=request.display_name,
                config=request.config,
                capabilities=request.capabilities or CatalogConnectionCapabilities(),
            )

        async def update_connection(self, connection_id, request, owner_id=None):
            recorded["updated"] = connection_id
            return CatalogConnection(
                id=connection_id,
                project_id=project_id,
                provider_kind=request.provider_kind,
                connection_kind=request.connection_kind,
                display_name=request.display_name,
                config=request.config,
                capabilities=request.capabilities or CatalogConnectionCapabilities(),
            )

        async def delete_connection(self, connection_id):
            recorded["deleted"] = connection_id
            return True

        async def validate_connection(self, connection_id):
            recorded["validated"] = connection_id
            return CatalogConnectionValidationResult(
                connection_id=connection_id,
                status="succeeded",
                validated_at=datetime.now(UTC),
                message="validated",
            )

        async def sync_connection(self, connection_id):
            recorded["synced"] = connection_id
            return CatalogSyncStatus(
                connection_id=connection_id,
                status="succeeded",
                entity_count=1,
            )

        async def list_entities(self, connection_id=None, namespace_name=None):
            recorded["entity_connection_id"] = connection_id
            return [
                CatalogEntitySummary(
                    id=recorded_entity_id,
                    connection_id=recorded_connection_id,
                    namespace_name="raw",
                    entity_name="customers",
                    entity_type=CatalogEntityType.TABLE,
                    column_count=3,
                )
            ]

        async def list_namespaces(self, connection_id=None):
            recorded["namespace_connection_id"] = connection_id
            return [
                CatalogNamespaceSummary(
                    id=str(uuid.uuid4()),
                    connection_id=connection_id or recorded_connection_id,
                    name="raw",
                    display_name="Raw",
                    entity_count=1,
                )
            ]

        async def get_entity_detail(self, entity_id):
            recorded["detail_entity_id"] = entity_id
            return CatalogEntityDetail(
                entity=CatalogEntitySummary(
                    id=entity_id,
                    connection_id=recorded_connection_id,
                    namespace_name="raw",
                    entity_name="customers",
                    entity_type=CatalogEntityType.TABLE,
                    column_count=1,
                ),
                columns=[
                    CatalogColumn(
                        id=str(uuid.uuid4()),
                        entity_id=entity_id,
                        name="customer_id",
                        ordinal_position=0,
                        data_type="string",
                        nullable=False,
                    )
                ],
            )

        async def refresh_entity(self, entity_id):
            recorded["refreshed_entity_id"] = entity_id
            return CatalogSyncStatus(
                connection_id=recorded_connection_id,
                status="succeeded",
                entity_count=1,
            )

        async def search(self, query, connection_id=None, limit=5):
            recorded["search_query"] = query
            return [
                CatalogSearchItem(
                    schema_name="raw",
                    table_name="customers",
                    description="Customers",
                    content="customer table",
                    connection_id=connection_id,
                )
            ]

    class FakeCatalogSyncDispatchService:
        def __init__(self, *, project_id: str, queue_client=None) -> None:
            recorded["dispatch_project_id"] = str(project_id)
            recorded["dispatch_queue_client"] = queue_client

        async def queue_initial_sync(self, connection, *, triggered_by=None):
            recorded.setdefault("queued_sync_ids", []).append(connection.id)
            recorded["queued_sync_actor"] = triggered_by
            return True

    class _FakeRuntimeProvider:
        def get_catalog_service(self):
            return FakeCatalogManagementService(
                project_id=project_id,
                runtime_provider=runtime_provider,
            )

    async def fake_create_runtime_provider(*, project_id: str, headers):
        recorded["runtime_factory_project_id"] = project_id
        recorded["runtime_factory_headers"] = dict(headers)
        return _FakeRuntimeProvider()

    monkeypatch.setattr(
        "kontext.api.routers.catalog.LOCAL_HEADERS_RUNTIME_FACTORY.create_runtime_provider",
        fake_create_runtime_provider,
    )
    monkeypatch.setattr(
        "kontext.api.routers.catalog.CatalogSyncDispatchService",
        FakeCatalogSyncDispatchService,
    )

    auth = _mock_auth(project_id)
    app.dependency_overrides[CATALOG_READ_AUTH.dependency] = lambda: auth
    app.dependency_overrides[CATALOG_WRITE_AUTH.dependency] = lambda: auth

    request_body = CatalogConnectionRequest(
        provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Local SQLite",
        config=CatalogConnectionConfig(database_path="/tmp/demo.db"),
    ).model_dump(by_alias=True)

    try:
        with TestClient(app) as client:
            response = client.get(f"/catalog/providers?projectId={project_id}")
            assert response.status_code == 200
            assert response.json()[0]["providerKind"] == "iceberg_internal"
            assert recorded["project_id"] == project_id
            assert recorded["runtime_provider"] is runtime_provider
            assert recorded["runtime_factory_project_id"] == project_id

            response = client.get(f"/catalog/connections?projectId={project_id}")
            assert response.status_code == 200
            assert response.json()[0]["displayName"] == "Default"

            response = client.post(
                f"/catalog/connections?projectId={project_id}",
                json=request_body,
            )
            assert response.status_code == 201
            assert recorded["created"] == "Local SQLite"
            assert len(recorded["queued_sync_ids"]) == 1

            connection_id = str(uuid.uuid4())
            response = client.put(
                f"/catalog/connections/{connection_id}?projectId={project_id}",
                json=request_body,
            )
            assert response.status_code == 200
            assert recorded["updated"] == connection_id
            assert len(recorded["queued_sync_ids"]) == 2

            response = client.post(
                f"/catalog/connections/{connection_id}/validate?projectId={project_id}"
            )
            assert response.status_code == 200
            assert response.json()["status"] == "succeeded"
            assert recorded["validated"] == connection_id

            response = client.post(
                f"/catalog/connections/{connection_id}/sync?projectId={project_id}"
            )
            assert response.status_code == 200
            assert response.json()["status"] == "succeeded"

            response = client.get(
                f"/catalog/entities?projectId={project_id}&connectionId={connection_id}"
            )
            assert response.status_code == 200
            assert recorded["entity_connection_id"] == connection_id
            entity_id = response.json()[0]["id"]

            response = client.get(
                f"/catalog/namespaces?projectId={project_id}&connectionId={connection_id}"
            )
            assert response.status_code == 200
            assert recorded["namespace_connection_id"] == connection_id

            response = client.get(f"/catalog/entities/{entity_id}?projectId={project_id}")
            assert response.status_code == 200
            assert recorded["detail_entity_id"] == entity_id

            response = client.post(f"/catalog/entities/{entity_id}/refresh?projectId={project_id}")
            assert response.status_code == 200
            assert recorded["refreshed_entity_id"] == entity_id

            response = client.get(
                f"/catalog/search?projectId={project_id}&query=customers&connectionId={connection_id}"
            )
            assert response.status_code == 200
            assert recorded["search_query"] == "customers"

            response = client.delete(f"/catalog/connections/{connection_id}?projectId={project_id}")
            assert response.status_code == 204
            assert recorded["deleted"] == connection_id
    finally:
        app.dependency_overrides.clear()


def test_create_catalog_connection_returns_bad_request_on_invalid_provider_request(
    monkeypatch,
):
    project_id = str(uuid.uuid4())

    monkeypatch.setattr(
        "kontext.api.main.get_runtime_profile",
        lambda: _BenignRuntimeProfile(),
    )

    class FakeCatalogManagementService:
        def __init__(self, project_id: str, runtime_provider=None) -> None:
            pass

        async def create_connection(self, request, owner_id=None):
            raise ValueError("SQLite does not support auth type secret_ref.")

    class _FakeRuntimeProvider:
        def get_catalog_service(self):
            return FakeCatalogManagementService(project_id=project_id)

    async def fake_create_runtime_provider(*, project_id: str, headers):
        return _FakeRuntimeProvider()

    monkeypatch.setattr(
        "kontext.api.routers.catalog.LOCAL_HEADERS_RUNTIME_FACTORY.create_runtime_provider",
        fake_create_runtime_provider,
    )

    auth = _mock_auth(project_id)
    app.dependency_overrides[CATALOG_WRITE_AUTH.dependency] = lambda: auth

    request_body = CatalogConnectionRequest(
        provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Local SQLite",
        config=CatalogConnectionConfig(database_path="/tmp/demo.db"),
    ).model_dump(by_alias=True)

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/catalog/connections?projectId={project_id}",
                json=request_body,
            )
            assert response.status_code == 400
            assert response.json()["detail"] == ("SQLite does not support auth type secret_ref.")
    finally:
        app.dependency_overrides.clear()
