from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from kontext.common.constants import DataLakeConstants
from kontext.common.jobs.trigger_actor import system_actor as make_system_actor
from kontext.common.jobs.trigger_actor import user_actor
from kontext.common.utils.file_storage import (
    get_project_storage_path,
    get_project_vector_db_path,
)
from kontext.data import (
    EventDataService,
    ExecutionRunContextDataService,
    JobDataService,
    JobRunDataService,
)
from kontext.data.database import get_engine, get_session_factory, get_sync_db_session
from kontext.data.models import Project
from kontext.file.charts import ChartService
from kontext.file.helpers import InMemoryUploadFile, infer_file_type
from kontext.file.service import FileService
from kontext.jobs.runs import ExecutionRunService
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.runtime.local.config import get_default_local_file_types
from kontext.schema import (
    ChartDocument,
    DataRef,
    DataTable,
    EventType,
    ExecutionRunKind,
    FileFormatType,
    InlineData,
    NotebookDocument,
)
from kontext.storage import clear_storage_provider_cache, get_storage_provider


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


def _create_service(project_id: UUID) -> FileService:
    return FileService(
        project_id=project_id,
        storage_provider=get_storage_provider(force_new=True),
        queue_client=None,
    )


def _update_project_upload_configuration(
    project_id: UUID,
    *,
    max_file_bytes_size: int,
) -> None:
    with get_sync_db_session() as session:
        project = session.get(Project, project_id)
        assert project is not None
        configuration = dict(project.configuration or {})
        configuration.pop("allowedFileTypes", None)
        configuration.pop("maxFileBytesSize", None)
        configuration["allowed_file_types"] = [
            file_type.model_dump() for file_type in get_default_local_file_types()
        ]
        configuration["max_file_bytes_size"] = max_file_bytes_size
        project.configuration = configuration
        session.commit()


def _set_project_allowed_file_types(
    project_id: UUID,
    *,
    allowed_extensions: set[str],
    max_file_bytes_size: int = 1024 * 1024 * 50,
) -> None:
    with get_sync_db_session() as session:
        project = session.get(Project, project_id)
        assert project is not None
        configuration = dict(project.configuration or {})
        configuration["allowed_file_types"] = [
            file_type.model_dump()
            for file_type in get_default_local_file_types()
            if file_type.file_extension in allowed_extensions
        ]
        configuration["max_file_bytes_size"] = max_file_bytes_size
        project.configuration = configuration
        session.commit()


@pytest.mark.asyncio
async def test_upload_supported_file_records_event_and_creates_queued_run(
    local_project_id,
):
    service = _create_service(local_project_id)
    upload = InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv")

    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=upload,
    )

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.CREATEFILE.value)
    assert len(events) == 1

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is not None

    run_service = JobRunDataService(local_project_id)
    runs = await run_service.get_runs_for_job_async(job_id=UUID(str(job.id)))
    assert len(runs) == 1
    assert runs[0].status.value == "Queued"
    assert str(created.id) in (runs[0].parameters or "")


@pytest.mark.asyncio
async def test_lakehouse_ingest_run_infers_owner_from_user_trigger(local_project_id):
    service = _create_service(local_project_id)
    owner_id = uuid4()

    await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
        owner_id=owner_id,
    )

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is not None

    run_service = JobRunDataService(local_project_id)
    runs = await run_service.get_runs_for_job_async(job_id=UUID(str(job.id)))
    assert len(runs) == 1
    assert runs[0].owner_id == str(owner_id)
    assert runs[0].job_trigger is not None
    assert runs[0].job_trigger.triggered_by == user_actor(str(owner_id))


@pytest.mark.asyncio
async def test_bulk_upload_supported_files_create_queued_run(local_project_id):
    service = _create_service(local_project_id)
    uploads = [
        InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
        InMemoryUploadFile("customers.csv", b"id,name\n1,Ada\n", "text/csv"),
    ]

    created_files, updated_files, errors = await service.upload_multiple_files(
        project_id=local_project_id,
        files=uploads,
        allow_overwrite=False,
        infer_type_func=lambda filename, content_type: FileFormatType.CSV,
    )
    assert not updated_files
    assert not errors

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is not None

    run_service = JobRunDataService(local_project_id)
    runs = await run_service.get_runs_for_job_async(job_id=UUID(str(job.id)))
    assert len(runs) == 1
    for created_file in created_files:
        assert str(created_file.id) in (runs[0].parameters or "")


@pytest.mark.asyncio
async def test_upload_rejects_files_that_exceed_project_size_limit(local_project_id):
    _update_project_upload_configuration(local_project_id, max_file_bytes_size=4)
    service = _create_service(local_project_id)

    with pytest.raises(ValueError, match="File size exceeds the project limit"):
        await service.upload_single_file(
            project_id=local_project_id,
            upload_file=InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
        )


@pytest.mark.asyncio
async def test_chat_upload_validation_rejects_non_lakehouse_file_types(
    local_project_id,
):
    service = _create_service(local_project_id)

    validation_batch = await service.validate_upload_files(
        project_id=local_project_id,
        files=[InMemoryUploadFile("notes.txt", b"hello", "text/plain")],
        infer_type_func=infer_file_type,
        allowed_file_format_types=DataLakeConstants.get_supported_data_file_types(),
    )

    assert validation_batch.files == []
    assert len(validation_batch.failures) == 1
    assert "Only structured data files" in validation_batch.failures[0].error


@pytest.mark.asyncio
async def test_schema_update_records_event_without_queuing_follow_up_job(
    local_project_id,
):
    service = _create_service(local_project_id)
    upload = InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv")
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=upload,
    )

    await service.update_file_schema(
        file_id=created.id,
        project_id=local_project_id,
        schema_json='{"subSchemas":[]}',
        stats_json='{"subSchemas":[]}',
    )

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.UPDATEFILESCHEMA.value)
    assert len(events) == 1

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is not None

    run_service = JobRunDataService(local_project_id)
    runs = await run_service.get_runs_for_job_async(job_id=UUID(str(job.id)))
    assert len(runs) == 1
    assert str(created.id) in (runs[0].parameters or "")


@pytest.mark.asyncio
async def test_delete_supported_file_creates_cleanup_job(local_project_id):
    service = _create_service(local_project_id)
    upload = InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv")
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=upload,
    )

    await service.delete_file(
        file_id=created.id,
        project_id=local_project_id,
    )

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.DELETEFILE.value)
    assert len(events) == 1

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseCleanupJob")
    assert job is not None

    run_service = JobRunDataService(local_project_id)
    runs = await run_service.get_runs_for_job_async(job_id=UUID(str(job.id)))
    assert len(runs) == 1
    assert str(created.id) in (runs[0].parameters or "")


@pytest.mark.asyncio
async def test_upload_unsupported_file_does_not_create_profiling_run(local_project_id):
    service = _create_service(local_project_id)
    upload = InMemoryUploadFile("diagram.png", b"\x89PNG\r\n", "image/png")

    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=upload,
    )
    assert created.file_type == FileFormatType.IMAGE.value

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.CREATEFILE.value)
    assert events == []

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is None
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is None


@pytest.mark.asyncio
async def test_chat_upload_preparation_always_creates_a_workflow_root(
    local_project_id,
):
    service = _create_service(local_project_id)
    validation_batch = await service.validate_upload_files(
        project_id=local_project_id,
        files=[InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv")],
        infer_type_func=infer_file_type,
        allowed_file_format_types=[FileFormatType.CSV],
    )
    assert validation_batch.failures == []

    persisted_batch = await service.persist_uploaded_files(
        project_id=local_project_id,
        files=validation_batch.files,
    )
    run_id = await service.dispatch_post_upload_processing(
        persisted_batch=persisted_batch,
        force_workflow=True,
        workflow_key="chat_upload_preparation",
        workflow_name="Chat Upload Preparation",
        workflow_parameters={"internalCatalogConnectionId": str(uuid4())},
        system_actor=make_system_actor("ChatUploadPreparation"),
    )

    assert run_id is not None

    run_service = ExecutionRunService()
    workflow_run = await run_service.get_run_async(
        project_id=local_project_id,
        run_id=UUID(str(run_id)),
        include_job=True,
    )
    assert workflow_run is not None
    assert workflow_run.kind == ExecutionRunKind.WORKFLOW

    job_service = JobDataService(local_project_id)
    workflow_job = await job_service.get_job_by_type_async(
        "python.workflow.chat_upload_preparation.Root"
    )
    assert workflow_job is not None


@pytest.mark.asyncio
async def test_upload_document_file_creates_document_indexing_run_only(
    local_project_id,
):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("notes.txt", b"hello", "text/plain"),
    )

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.CREATEFILE.value)
    assert events == []

    job_service = JobDataService(local_project_id)
    lakehouse_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert lakehouse_job is None

    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is not None

    run_service = JobRunDataService(local_project_id)
    runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(runs) == 1
    assert runs[0].status.value == "Queued"
    assert str(created.id) in (runs[0].parameters or "")


@pytest.mark.asyncio
async def test_update_document_file_requeues_document_indexing(local_project_id):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("notes.txt", b"hello", "text/plain"),
    )

    await service.update_file_content(
        file_id=created.id,
        upload_file=InMemoryUploadFile("notes.txt", b"updated knowledge", "text/plain"),
    )

    job_service = JobDataService(local_project_id)
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is not None

    run_service = JobRunDataService(local_project_id)
    runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(runs) == 2
    for run in runs:
        assert str(created.id) in (run.parameters or "")


@pytest.mark.asyncio
async def test_update_document_file_to_data_queues_document_removal_and_ingest(
    local_project_id,
):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("notes.txt", b"hello", "text/plain"),
    )

    await service.update_file_content(
        file_id=created.id,
        upload_file=InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
    )

    job_service = JobDataService(local_project_id)
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is not None
    ingest_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert ingest_job is not None

    run_service = JobRunDataService(local_project_id)
    document_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(document_runs) == 2
    document_parameters = [run.parameters or "" for run in document_runs]
    assert any("file_id" in value and str(created.id) in value for value in document_parameters)
    assert any(
        "delete_file_id" in value and str(created.id) in value for value in document_parameters
    )

    ingest_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(ingest_job.id)))
    assert len(ingest_runs) == 1
    assert str(created.id) in (ingest_runs[0].parameters or "")


@pytest.mark.asyncio
async def test_multi_step_file_processing_creates_workflow_root(local_project_id):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("notes.txt", b"hello", "text/plain"),
    )

    await service.update_file_content(
        file_id=created.id,
        upload_file=InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
    )

    job_service = JobDataService(local_project_id)
    workflow_job = await job_service.get_job_by_type_async("python.workflow.file_processing.Root")
    assert workflow_job is not None

    run_service = JobRunDataService(local_project_id)
    workflow_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(workflow_job.id)))
    assert len(workflow_runs) == 1

    workflow_run_id = UUID(str(workflow_runs[0].id))
    execution_run = await ExecutionRunService().get_run_async(
        project_id=local_project_id,
        run_id=workflow_run_id,
    )
    assert execution_run is not None
    assert execution_run.kind == ExecutionRunKind.WORKFLOW
    assert execution_run.workflow_key == "file_processing"
    assert execution_run.is_workflow_root is True

    contexts = await ExecutionRunContextDataService(local_project_id).list_by_root_run_id_async(
        workflow_run_id
    )
    assert len(contexts) == 3

    child_step_keys = {
        execution_run.step_key
        for execution_run in [
            await ExecutionRunService().get_run_async(
                project_id=local_project_id,
                run_id=UUID(str(context.run_id)),
            )
            for context in contexts
            if UUID(str(context.run_id)) != workflow_run_id
        ]
        if execution_run is not None
    }
    assert child_step_keys == {
        f"document-delete-{created.id}",
        "lakehouse-ingest",
    }


@pytest.mark.asyncio
async def test_update_document_file_to_unsupported_queues_document_removal_only(
    local_project_id,
):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("notes.txt", b"hello", "text/plain"),
    )

    await service.update_file_content(
        file_id=created.id,
        upload_file=InMemoryUploadFile("diagram.png", b"\x89PNG\r\n", "image/png"),
    )

    job_service = JobDataService(local_project_id)
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is not None
    lakehouse_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert lakehouse_job is None
    cleanup_job = await job_service.get_job_by_type_async("python.jobs.LakehouseCleanupJob")
    assert cleanup_job is None

    run_service = JobRunDataService(local_project_id)
    document_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(document_runs) == 2
    document_parameters = [run.parameters or "" for run in document_runs]
    assert any("file_id" in value and str(created.id) in value for value in document_parameters)
    assert any(
        "delete_file_id" in value and str(created.id) in value for value in document_parameters
    )


@pytest.mark.asyncio
async def test_delete_document_file_queues_index_removal(local_project_id):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("notes.txt", b"hello", "text/plain"),
    )

    await service.delete_file(
        file_id=created.id,
        project_id=local_project_id,
    )

    job_service = JobDataService(local_project_id)
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is not None

    run_service = JobRunDataService(local_project_id)
    runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(runs) == 2
    parameters = [run.parameters or "" for run in runs]
    assert any(str(created.id) in value for value in parameters)
    assert any("delete_file_id" in value for value in parameters)


@pytest.mark.asyncio
async def test_update_data_file_to_document_queues_cleanup_and_document_indexing(
    local_project_id,
):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
    )

    await service.update_file_content(
        file_id=created.id,
        upload_file=InMemoryUploadFile("notes.txt", b"hello", "text/plain"),
    )

    job_service = JobDataService(local_project_id)
    ingest_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert ingest_job is not None
    cleanup_job = await job_service.get_job_by_type_async("python.jobs.LakehouseCleanupJob")
    assert cleanup_job is not None
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is not None

    run_service = JobRunDataService(local_project_id)
    ingest_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(ingest_job.id)))
    assert len(ingest_runs) == 1
    assert str(created.id) in (ingest_runs[0].parameters or "")

    cleanup_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(cleanup_job.id)))
    assert len(cleanup_runs) == 1
    assert str(created.id) in (cleanup_runs[0].parameters or "")

    document_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(document_runs) == 1
    assert str(created.id) in (document_runs[0].parameters or "")
    assert "file_id" in (document_runs[0].parameters or "")


@pytest.mark.asyncio
async def test_update_data_file_to_unsupported_queues_cleanup_only(local_project_id):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
    )

    await service.update_file_content(
        file_id=created.id,
        upload_file=InMemoryUploadFile("diagram.png", b"\x89PNG\r\n", "image/png"),
    )

    job_service = JobDataService(local_project_id)
    ingest_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert ingest_job is not None
    cleanup_job = await job_service.get_job_by_type_async("python.jobs.LakehouseCleanupJob")
    assert cleanup_job is not None
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is None

    run_service = JobRunDataService(local_project_id)
    ingest_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(ingest_job.id)))
    assert len(ingest_runs) == 1
    cleanup_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(cleanup_job.id)))
    assert len(cleanup_runs) == 1
    assert str(created.id) in (cleanup_runs[0].parameters or "")


@pytest.mark.asyncio
async def test_bulk_overwrite_document_to_data_queues_delete_and_ingest(
    local_project_id,
):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("resource", b"hello", "text/plain"),
    )

    created_files, updated_files, errors = await service.upload_multiple_files(
        project_id=local_project_id,
        files=[InMemoryUploadFile("resource", b"id,total\n1,10\n", "text/csv")],
        allow_overwrite=True,
        infer_type_func=infer_file_type,
    )

    assert created_files == []
    assert len(updated_files) == 1
    assert not errors

    job_service = JobDataService(local_project_id)
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    ingest_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert document_job is not None
    assert ingest_job is not None

    run_service = JobRunDataService(local_project_id)
    document_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(document_runs) == 2
    document_parameters = [run.parameters or "" for run in document_runs]
    assert any("file_id" in value and str(created.id) in value for value in document_parameters)
    assert any(
        "delete_file_id" in value and str(created.id) in value for value in document_parameters
    )

    ingest_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(ingest_job.id)))
    assert len(ingest_runs) == 1
    assert str(created.id) in (ingest_runs[0].parameters or "")


@pytest.mark.asyncio
async def test_bulk_overwrite_data_to_document_queues_cleanup_and_document_indexing(
    local_project_id,
):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("resource", b"id,total\n1,10\n", "text/csv"),
    )

    created_files, updated_files, errors = await service.upload_multiple_files(
        project_id=local_project_id,
        files=[InMemoryUploadFile("resource", b"knowledge", "text/plain")],
        allow_overwrite=True,
        infer_type_func=infer_file_type,
    )

    assert created_files == []
    assert len(updated_files) == 1
    assert not errors

    job_service = JobDataService(local_project_id)
    ingest_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    cleanup_job = await job_service.get_job_by_type_async("python.jobs.LakehouseCleanupJob")
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert ingest_job is not None
    assert cleanup_job is not None
    assert document_job is not None

    run_service = JobRunDataService(local_project_id)
    ingest_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(ingest_job.id)))
    assert len(ingest_runs) == 1

    cleanup_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(cleanup_job.id)))
    assert len(cleanup_runs) == 1
    assert str(created.id) in (cleanup_runs[0].parameters or "")

    document_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(document_runs) == 1
    assert str(created.id) in (document_runs[0].parameters or "")
    assert "file_id" in (document_runs[0].parameters or "")


@pytest.mark.asyncio
async def test_bulk_overwrite_document_to_unsupported_queues_delete_only(
    local_project_id,
):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("resource", b"hello", "text/plain"),
    )

    created_files, updated_files, errors = await service.upload_multiple_files(
        project_id=local_project_id,
        files=[InMemoryUploadFile("resource", b"\x89PNG\r\n", "image/png")],
        allow_overwrite=True,
        infer_type_func=infer_file_type,
    )

    assert created_files == []
    assert len(updated_files) == 1
    assert not errors

    job_service = JobDataService(local_project_id)
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    lakehouse_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    cleanup_job = await job_service.get_job_by_type_async("python.jobs.LakehouseCleanupJob")
    assert document_job is not None
    assert lakehouse_job is None
    assert cleanup_job is None

    run_service = JobRunDataService(local_project_id)
    document_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(document_job.id)))
    assert len(document_runs) == 2
    document_parameters = [run.parameters or "" for run in document_runs]
    assert any("file_id" in value and str(created.id) in value for value in document_parameters)
    assert any(
        "delete_file_id" in value and str(created.id) in value for value in document_parameters
    )


@pytest.mark.asyncio
async def test_bulk_overwrite_data_to_unsupported_queues_cleanup_only(
    local_project_id,
):
    service = _create_service(local_project_id)
    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("resource", b"id,total\n1,10\n", "text/csv"),
    )

    created_files, updated_files, errors = await service.upload_multiple_files(
        project_id=local_project_id,
        files=[InMemoryUploadFile("resource", b"\x89PNG\r\n", "image/png")],
        allow_overwrite=True,
        infer_type_func=infer_file_type,
    )

    assert created_files == []
    assert len(updated_files) == 1
    assert not errors

    job_service = JobDataService(local_project_id)
    ingest_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    cleanup_job = await job_service.get_job_by_type_async("python.jobs.LakehouseCleanupJob")
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert ingest_job is not None
    assert cleanup_job is not None
    assert document_job is None

    run_service = JobRunDataService(local_project_id)
    ingest_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(ingest_job.id)))
    assert len(ingest_runs) == 1

    cleanup_runs = await run_service.get_runs_for_job_async(job_id=UUID(str(cleanup_job.id)))
    assert len(cleanup_runs) == 1
    assert str(created.id) in (cleanup_runs[0].parameters or "")


@pytest.mark.asyncio
async def test_upload_datatable_artifact_does_not_create_ingest_run(local_project_id):
    service = _create_service(local_project_id)
    upload = InMemoryUploadFile(
        "query-result.dt",
        b'{"title":"query-result","table":{"columns":[],"rows":[],"rowCount":0}}',
        "application/json",
    )

    await service.upload_single_file(
        project_id=local_project_id,
        upload_file=upload,
    )

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.CREATEFILE.value)
    assert events == []

    job_service = JobDataService(local_project_id)
    job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert job is None
    document_job = await job_service.get_job_by_type_async("python.jobs.DocumentIndexingJob")
    assert document_job is None


@pytest.mark.asyncio
async def test_internal_inline_data_artifact_creation_works_without_dt_in_project_rules(
    local_project_id,
):
    _set_project_allowed_file_types(local_project_id, allowed_extensions={".csv"})
    service = _create_service(local_project_id)

    response = await service.create_inline_data_file(
        project_id=local_project_id,
        inline_data=InlineData(
            title="hourly-counts",
            table=DataTable(columns=[], rows=[[0, 10]], row_count=1),
        ),
    )

    assert response.file.name.endswith(".dt")
    assert response.file.file_type == FileFormatType.DATATABLE
    assert response.file.prefix == ".dts"
    assert response.file.path.startswith(".dts/")


@pytest.mark.asyncio
async def test_upload_datatable_artifact_still_works_without_dt_in_project_rules(
    local_project_id,
):
    _set_project_allowed_file_types(local_project_id, allowed_extensions={".csv"})
    service = _create_service(local_project_id)

    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile(
            "query-result.dt",
            b'{"title":"query-result","table":{"columns":[],"rows":[],"rowCount":0}}',
            "application/json",
        ),
    )

    assert created.name == "query-result.dt"
    assert created.file_type == FileFormatType.DATATABLE


@pytest.mark.asyncio
async def test_internal_chart_artifact_creation_works_without_chart_in_project_rules(
    local_project_id,
):
    _set_project_allowed_file_types(local_project_id, allowed_extensions={".csv"})
    service = _create_service(local_project_id)

    chart = ChartDocument(
        name="Hourly Counts",
        config=ChartService.create_bar_chart_config(
            title="Hourly Counts",
            x_field="hour",
            y_field="row_count",
        ),
        data_ref=DataRef(data_id=str(uuid4())),
    )

    response = await service.create_chart(
        project_id=local_project_id,
        chart=chart,
    )

    assert response.file.name.endswith(".chart")
    assert response.file.file_type == FileFormatType.CHART
    assert response.file.prefix == ".charts"
    assert response.file.path.startswith(".charts/")


@pytest.mark.asyncio
async def test_internal_notebook_artifact_creation_works_without_notebook_in_project_rules(
    local_project_id,
):
    _set_project_allowed_file_types(local_project_id, allowed_extensions={".csv"})
    service = _create_service(local_project_id)

    response = await service.create_notebook(
        project_id=local_project_id,
        notebook=NotebookDocument(
            title="Artifact Test Notebook",
            created=0,
            modified=0,
            blocks=[],
        ),
    )

    assert response.file.name.endswith(".kontext")
    assert response.file.file_type == FileFormatType.NOTEBOOK
    assert response.file.prefix == ".notebooks"
    assert response.file.path.startswith(".notebooks/")


@pytest.mark.asyncio
async def test_update_prefixed_artifact_preserves_prefix_and_storage_path(
    local_project_id,
):
    service = _create_service(local_project_id)

    response = await service.create_notebook(
        project_id=local_project_id,
        notebook=NotebookDocument(
            title="Artifact Test Notebook",
            created=0,
            modified=0,
            blocks=[],
        ),
        name="prefixed-notebook",
    )

    await service.update_file_content(
        file_id=UUID(response.file.id),
        upload_file=InMemoryUploadFile(
            "prefixed-notebook.kontext",
            b'{"title":"Artifact Test Notebook","created":0,"modified":0,"blocks":[]}',
            "application/json",
        ),
    )

    updated = await service.get_file_by_id(UUID(response.file.id))
    assert updated is not None
    assert updated.prefix == ".notebooks"
    assert updated.uri is not None
    assert f"{os.sep}.notebooks{os.sep}" in updated.uri


@pytest.mark.asyncio
async def test_system_managed_prefix_upload_is_rejected_without_side_effects(
    local_project_id,
):
    service = _create_service(local_project_id)

    with pytest.raises(ValueError, match="reserved for system-managed files"):
        await service.upload_single_file(
            project_id=local_project_id,
            upload_file=InMemoryUploadFile("warehouse.csv", b"id,total\n1,10\n", "text/csv"),
            prefix=".lakehouse",
        )

    event_service = EventDataService(local_project_id)
    events = await event_service.get_events_by_type_async(EventType.CREATEFILE.value)
    assert events == []

    job_service = JobDataService(local_project_id)
    lakehouse_job = await job_service.get_job_by_type_async("python.jobs.LakehouseIngestJob")
    assert lakehouse_job is None


@pytest.mark.asyncio
async def test_upload_single_file_respects_explicit_prefix(local_project_id):
    service = _create_service(local_project_id)

    created = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
        prefix="uploads/2026",
    )

    assert created.prefix == "uploads/2026"
    assert created.uri is not None
    assert f"{os.sep}uploads{os.sep}2026{os.sep}" in created.uri


@pytest.mark.asyncio
async def test_upload_multiple_files_respect_explicit_prefix(local_project_id):
    service = _create_service(local_project_id)

    created_files, updated_files, errors = await service.upload_multiple_files(
        project_id=local_project_id,
        files=[
            InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv"),
            InMemoryUploadFile("customers.csv", b"id,name\n1,Ada\n", "text/csv"),
        ],
        prefix="uploads/2026",
        allow_overwrite=False,
        infer_type_func=lambda filename, content_type: FileFormatType.CSV,
    )

    assert updated_files == []
    assert errors == []
    assert len(created_files) == 2
    assert {file.prefix for file in created_files} == {"uploads/2026"}


@pytest.mark.asyncio
async def test_list_files_with_root_prefix_returns_folder_navigation(local_project_id):
    service = _create_service(local_project_id)

    await service.create_notebook(
        project_id=local_project_id,
        notebook=NotebookDocument(
            title="Navigation Notebook",
            created=0,
            modified=0,
            blocks=[],
        ),
        name="navigation-notebook",
    )

    root_listing = await service.list_files(
        project_id=local_project_id,
        prefix="",
        page_size=50,
    )

    listed_paths = {item.path for item in root_listing.items}
    assert ".notebooks" in listed_paths
    assert ".knowledge" in listed_paths
    assert ".lakehouse" in listed_paths

    notebook_listing = await service.list_files(
        project_id=local_project_id,
        prefix=".notebooks",
        page_size=50,
    )
    assert [item.path for item in notebook_listing.items] == [
        ".notebooks/navigation-notebook.kontext"
    ]


@pytest.mark.asyncio
async def test_list_files_can_exclude_system_managed_root_prefixes(local_project_id):
    service = _create_service(local_project_id)

    await service.create_notebook(
        project_id=local_project_id,
        notebook=NotebookDocument(
            title="Navigation Notebook",
            created=0,
            modified=0,
            blocks=[],
        ),
        name="navigation-notebook",
    )

    root_listing = await service.list_files(
        project_id=local_project_id,
        prefix="",
        page_size=50,
        include_system_prefixes=False,
    )

    listed_paths = {item.path for item in root_listing.items}
    assert ".notebooks" in listed_paths
    assert ".knowledge" not in listed_paths
    assert ".lakehouse" not in listed_paths
    assert root_listing.total_count == 1


@pytest.mark.asyncio
async def test_list_files_with_system_prefixes_returns_virtual_entries(
    local_project_id,
):
    service = _create_service(local_project_id)

    lakehouse_root = Path(get_project_storage_path(str(local_project_id), "lakehouse"))
    lakehouse_root.mkdir(parents=True, exist_ok=True)
    (lakehouse_root / "metadata").mkdir(exist_ok=True)
    (lakehouse_root / "metadata" / "v1.metadata.json").write_text("{}", encoding="utf-8")

    vector_db_path = Path(get_project_vector_db_path(str(local_project_id)))
    vector_db_path.mkdir(parents=True, exist_ok=True)
    (vector_db_path / "manifest.json").write_text("{}", encoding="utf-8")

    lakehouse_listing = await service.list_files(
        project_id=local_project_id,
        prefix=".lakehouse",
        page_size=50,
    )
    assert [item.path for item in lakehouse_listing.items] == [".lakehouse/metadata"]

    lakehouse_metadata_listing = await service.list_files(
        project_id=local_project_id,
        prefix=".lakehouse/metadata",
        page_size=50,
    )
    assert [item.path for item in lakehouse_metadata_listing.items] == [
        ".lakehouse/metadata/v1.metadata.json"
    ]
    assert lakehouse_metadata_listing.items[0].uri is not None

    knowledge_root_listing = await service.list_files(
        project_id=local_project_id,
        prefix=".knowledge",
        page_size=50,
    )
    assert [item.path for item in knowledge_root_listing.items] == [
        ".knowledge/vector",
    ]

    knowledge_vector_listing = await service.list_files(
        project_id=local_project_id,
        prefix=".knowledge/vector",
        page_size=50,
    )
    assert [item.path for item in knowledge_vector_listing.items] == [".knowledge/vector/lancedb"]


@pytest.mark.asyncio
async def test_metadata_create_rejects_system_managed_prefix(local_project_id):
    service = _create_service(local_project_id)

    with pytest.raises(ValueError, match="reserved for system-managed files"):
        await service.create_file_metadata(
            project_id=local_project_id,
            name="warehouse.csv",
            prefix=".lakehouse",
            file_type=FileFormatType.CSV,
        )


@pytest.mark.asyncio
async def test_bulk_upload_rejects_system_managed_prefix(local_project_id):
    service = _create_service(local_project_id)

    validated = await service.validate_upload_files(
        project_id=local_project_id,
        files=[InMemoryUploadFile("warehouse.csv", b"id\n1\n", "text/csv")],
        infer_type_func=infer_file_type,
        prefix=".knowledge",
    )

    assert validated.files == []
    assert len(validated.failures) == 1
    assert "reserved for system-managed files" in validated.failures[0].error
