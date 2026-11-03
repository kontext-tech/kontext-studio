from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from kontext.data import EventDataService, JobDataService
from kontext.data.database import get_engine, get_session_factory, get_sync_db_session
from kontext.data.models import Project
from kontext.execution.events import EventService
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.schema import EventType, FileFormatType, SimpleFileEventData
from kontext.storage import clear_storage_provider_cache


def _clear_runtime_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    clear_storage_provider_cache()


@pytest.fixture()
def local_project_id(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_url = f"sqlite:///{tmp_path / 'kontext.db'}"
    monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(tmp_path / "storage"))

    with (
        patch(
            "kontext.runtime.local.config.get_local_database_url",
            return_value=db_url,
        ),
        patch(
            "kontext.runtime.local.auth.get_local_jwt_secret",
            return_value="test-local-secret",
        ),
    ):
        _clear_runtime_caches()
        try:
            initialize_local_mode()
            with get_sync_db_session() as session:
                project_id = session.execute(
                    select(Project.id).where(Project.project_code == "local")
                ).scalar_one()
            yield project_id
        finally:
            _clear_runtime_caches()


@pytest.mark.asyncio
async def test_event_service_creates_queued_run_without_queue(
    local_project_id, caplog: pytest.LogCaptureFixture
):
    service = EventService(project_id=local_project_id, queue_client=None)
    file_data = SimpleFileEventData(
        id="11111111-1111-4111-8111-111111111111",
        name="orders.csv",
        file_type=FileFormatType.CSV,
    )

    with caplog.at_level(logging.INFO):
        await service.record_file_created(file_data)

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is None

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.CREATEFILE.value)
    assert len(events) == 1
    assert "Recorded event" in caplog.text


@pytest.mark.asyncio
async def test_event_service_dispatches_when_queue_client_is_configured(
    local_project_id, caplog: pytest.LogCaptureFixture
):
    queue_client = AsyncMock()
    queue_client.send_message.return_value = "message-1"
    service = EventService(project_id=local_project_id, queue_client=queue_client)
    file_data = SimpleFileEventData(
        id="22222222-2222-4222-8222-222222222222",
        name="orders.csv",
        file_type=FileFormatType.CSV,
    )

    with caplog.at_level(logging.INFO):
        await service.record_file_created(file_data)

    queue_client.send_message.assert_not_awaited()

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is None
    assert "Recorded event" in caplog.text


@pytest.mark.asyncio
async def test_event_service_records_datatable_artifacts_without_ingest_jobs(
    local_project_id, caplog: pytest.LogCaptureFixture
):
    service = EventService(project_id=local_project_id, queue_client=None)
    file_data = SimpleFileEventData(
        id="33333333-3333-4333-8333-333333333333",
        name="query-result.dt",
        file_type=FileFormatType.DATATABLE,
    )

    with caplog.at_level(logging.INFO):
        await service.record_file_created(file_data)

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.CREATEFILE.value)
    assert len(events) == 1

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is None
