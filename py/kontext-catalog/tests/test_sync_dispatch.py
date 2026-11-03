from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import uuid4

import pytest

from kontext.catalog.sync_dispatch import CatalogSyncDispatchService
from kontext.common.jobs.trigger_actor import user_actor
from kontext.common.messaging import IQueueClient, QueueMessage
from kontext.schema import (
    CatalogConnection,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogSourceKind,
)


class _FakeQueueClient(IQueueClient):
    async def send_message(self, message: str) -> str:
        _ = message
        return "message-id"

    async def delete_message(self, message_id: str, receipt_handle: str) -> None:
        _ = (message_id, receipt_handle)

    async def update_message(
        self, message_id: str, receipt_handle: str, visibility_timeout: int
    ) -> str:
        _ = (message_id, receipt_handle, visibility_timeout)
        return "pop-receipt"

    async def close(self) -> None:
        return None

    async def receive_messages(
        self, max_messages: int, visibility_timeout: int
    ) -> AsyncIterator[QueueMessage]:
        _ = (max_messages, visibility_timeout)
        if False:
            yield QueueMessage(
                message_id="",
                body="",
                receipt_handle="",
            )


@pytest.mark.asyncio
async def test_queue_initial_sync_creates_job_run_and_marks_connection_queued(
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
    service = CatalogSyncDispatchService(project_id=project_id, queue_client=_FakeQueueClient())
    recorded: dict[str, object] = {}
    call_order: list[str] = []

    async def fake_ensure_job_exists_async(self, **kwargs):
        recorded["job_type"] = kwargs["job_type"]
        return SimpleNamespace(id=uuid4(), name=kwargs["name"], timeout=300)

    async def fake_dispatch(**kwargs):
        call_order.append("dispatch")
        recorded["parameters"] = kwargs["parameters"]
        recorded["triggered_by"] = kwargs["triggered_by"]
        return SimpleNamespace(id=str(uuid4())), True

    async def fake_update_sync_status_async(connection_id, **kwargs):
        call_order.append(f"status:{kwargs['status']}")
        recorded["queued_connection_id"] = connection_id
        recorded["queued_status"] = kwargs["status"]
        return SimpleNamespace(status=kwargs["status"])

    monkeypatch.setattr(
        "kontext.catalog.sync_dispatch.JobService.ensure_job_exists_async",
        fake_ensure_job_exists_async,
    )
    monkeypatch.setattr(
        "kontext.catalog.sync_dispatch.create_queued_job_run_and_maybe_dispatch",
        fake_dispatch,
    )
    monkeypatch.setattr(
        service._catalog_data_service,
        "update_sync_status_async",
        fake_update_sync_status_async,
    )

    queued = await service.queue_initial_sync(connection, triggered_by=user_actor("test"))

    assert queued is True
    assert recorded["job_type"] == "python.jobs.ExternalCatalogInitialSyncJob"
    assert recorded["parameters"] == {"connection_id": connection.id}
    assert recorded["queued_connection_id"] == connection.id
    assert recorded["queued_status"] == "queued"
    assert call_order == ["status:queued", "dispatch"]
