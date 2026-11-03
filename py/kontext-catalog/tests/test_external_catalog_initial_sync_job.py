from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from kontext.catalog.jobs.external_catalog_initial_sync_job import (
    ExternalCatalogInitialSyncJob,
    ExternalCatalogInitialSyncParams,
)
from kontext.schema import (
    CatalogConnection,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogConnectionValidationResult,
    CatalogSourceKind,
    CatalogSyncStatus,
)


class _FakeContext:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.progress_updates: list[tuple[int, str]] = []

    def get_runtime_provider(self):
        return object()

    async def log_info(self, *_args, **_kwargs):
        return None

    async def update_progress(self, percent: int, message: str):
        self.progress_updates.append((percent, message))


@pytest.mark.asyncio
async def test_external_catalog_initial_sync_job_stops_on_validation_failure(
    monkeypatch,
):
    project_id = "00000000-0000-0000-0000-000000000001"
    connection = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        project_id=project_id,
        provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Warehouse",
        config=CatalogConnectionConfig(
            host="localhost",
            database_name="postgres",
        ),
        capabilities=CatalogConnectionCapabilities(),
    )
    recorded: dict[str, Any] = {"sync_called": False}

    class FakeCatalogManagementService:
        def __init__(self, project_id: str, runtime_provider=None):
            _ = runtime_provider
            self.data_service = SimpleNamespace(
                get_connection_async=self.get_connection_async,
                update_sync_status_async=self.update_sync_status_async,
            )

        async def get_connection_async(self, connection_id: str):
            return connection if connection_id == connection.id else None

        async def update_sync_status_async(self, connection_id: str, **kwargs):
            recorded.setdefault("status_updates", []).append((connection_id, kwargs))
            return SimpleNamespace(status=kwargs["status"])

        async def validate_connection(self, connection_id: str):
            return CatalogConnectionValidationResult(
                connection_id=connection_id,
                status="failed",
                validated_at=datetime.now(UTC),
                error_message="bad credentials",
            )

        async def sync_connection(self, connection_id: str):
            _ = connection_id
            recorded["sync_called"] = True
            return CatalogSyncStatus(connection_id=connection.id or "", status="failed")

    monkeypatch.setattr(
        "kontext.catalog.jobs.external_catalog_initial_sync_job.CatalogManagementService",
        FakeCatalogManagementService,
    )

    result = await ExternalCatalogInitialSyncJob().execute_job(
        _FakeContext(project_id),
        ExternalCatalogInitialSyncParams(connection_id=connection.id or ""),
    )

    assert result.success is False
    assert recorded["sync_called"] is False
    assert recorded["status_updates"][-1][1]["status"] == "failed"


@pytest.mark.asyncio
async def test_external_catalog_initial_sync_job_syncs_and_invalidates_sessions(
    monkeypatch,
):
    project_id = "00000000-0000-0000-0000-000000000001"
    connection = CatalogConnection(
        id="00000000-0000-0000-0000-00000000000a",
        project_id=project_id,
        provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        display_name="Warehouse",
        config=CatalogConnectionConfig(
            host="localhost",
            database_name="postgres",
        ),
        capabilities=CatalogConnectionCapabilities(),
    )
    recorded: dict[str, Any] = {}

    class FakeCatalogManagementService:
        def __init__(self, project_id: str, runtime_provider=None):
            _ = runtime_provider
            self.data_service = SimpleNamespace(
                get_connection_async=self.get_connection_async,
                update_sync_status_async=self.update_sync_status_async,
            )

        async def get_connection_async(self, connection_id: str):
            return connection if connection_id == connection.id else None

        async def update_sync_status_async(self, connection_id: str, **kwargs):
            recorded.setdefault("status_updates", []).append((connection_id, kwargs))
            return SimpleNamespace(status=kwargs["status"])

        async def validate_connection(self, connection_id: str):
            return CatalogConnectionValidationResult(
                connection_id=connection_id,
                status="succeeded",
                validated_at=datetime.now(UTC),
                message="ok",
            )

        async def sync_connection(self, connection_id: str):
            recorded["sync_connection_id"] = connection_id
            return CatalogSyncStatus(
                connection_id=connection.id or "",
                status="succeeded",
                entity_count=3,
            )

    monkeypatch.setattr(
        "kontext.catalog.jobs.external_catalog_initial_sync_job.CatalogManagementService",
        FakeCatalogManagementService,
    )

    result = await ExternalCatalogInitialSyncJob().execute_job(
        _FakeContext(project_id),
        ExternalCatalogInitialSyncParams(connection_id=connection.id or ""),
    )

    assert result.success is True
    assert recorded["sync_connection_id"] == connection.id
