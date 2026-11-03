"""Tests for the project-file backed document indexing job."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from kontext.catalog import DocumentIndexingOutcome
from kontext.project.jobs.document_indexing_job import (
    DocumentIndexingJob,
    DocumentIndexingParams,
)


class _FakeJobContext:
    def __init__(self, project_id: str, runtime_provider=None) -> None:
        self.project_id = project_id
        self._runtime_provider = runtime_provider
        self.info_logs: list[str] = []
        self.warning_logs: list[str] = []

    def get_runtime_provider(self):
        return self._runtime_provider

    async def log_info(self, message: str, data=None) -> None:
        self.info_logs.append(message)

    async def log_warning(self, message: str, data=None) -> None:
        self.warning_logs.append(message)


@pytest.mark.asyncio
async def test_document_indexing_job_rebuilds_from_project_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = "550e8400-e29b-41d4-a716-446655440000"
    file_id = UUID("550e8400-e29b-41d4-a716-446655440001")
    runtime_provider = object()
    fake_file = SimpleNamespace(
        id=file_id,
        name="notes.md",
        content_type="text/markdown",
        file_type="Markdown",
        uri="file://notes.md",
        date_created=datetime.now(UTC),
        date_modified=None,
        is_deleted=False,
    )

    fake_data_service = SimpleNamespace(
        get_non_deleted_files_batch_by_cursor_async=AsyncMock(side_effect=[[fake_file], []]),
    )
    fake_storage_provider = SimpleNamespace(
        download_file=AsyncMock(return_value=BytesIO(b"# Notes\nLakehouse guidance"))
    )
    fake_index_service = SimpleNamespace(
        clear_index=AsyncMock(),
        delete_project_file=AsyncMock(),
        is_project_file_indexable=lambda **_kwargs: True,
        index_project_file=AsyncMock(
            return_value=DocumentIndexingOutcome(
                source_id=f"file:{file_id}",
                chunks_indexed=2,
                parser_name="direct_utf8",
            )
        ),
    )

    monkeypatch.setattr(
        "kontext.data.FileDataService",
        lambda project_uuid: fake_data_service,
    )
    monkeypatch.setattr(
        "kontext.storage.factory.get_storage_provider",
        lambda: fake_storage_provider,
    )

    def _document_index_service_factory(
        *, project_id: str | None = None, runtime_provider=None, **_kwargs
    ):
        assert project_id == context.project_id
        assert runtime_provider is context.get_runtime_provider()
        return fake_index_service

    context = _FakeJobContext(project_id, runtime_provider=runtime_provider)
    monkeypatch.setattr(
        "kontext.catalog.DocumentIndexService",
        _document_index_service_factory,
    )
    job = DocumentIndexingJob()

    result = await job.execute_job(context, DocumentIndexingParams(recreate_index=True))

    assert result.success is True
    assert result.data["files_indexed"] == 1
    fake_index_service.clear_index.assert_awaited_once()
    fake_storage_provider.download_file.assert_awaited_once_with("file://notes.md")
    fake_index_service.index_project_file.assert_awaited_once()


@pytest.mark.asyncio
async def test_document_indexing_job_delete_mode_removes_file_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = "550e8400-e29b-41d4-a716-446655440000"
    runtime_provider = object()
    fake_index_service = SimpleNamespace(
        delete_project_file=AsyncMock(),
        is_project_file_indexable=lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        "kontext.data.FileDataService",
        lambda project_uuid: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "kontext.storage.factory.get_storage_provider",
        lambda: SimpleNamespace(),
    )

    def _document_index_service_factory(
        *, project_id: str | None = None, runtime_provider=None, **_kwargs
    ):
        assert project_id == context.project_id
        assert runtime_provider is context.get_runtime_provider()
        return fake_index_service

    context = _FakeJobContext(project_id, runtime_provider=runtime_provider)
    monkeypatch.setattr(
        "kontext.catalog.DocumentIndexService",
        _document_index_service_factory,
    )
    job = DocumentIndexingJob()

    result = await job.execute_job(
        context,
        DocumentIndexingParams(delete_file_id="file-123"),
    )

    assert result.success is True
    fake_index_service.delete_project_file.assert_awaited_once_with("file-123")


@pytest.mark.asyncio
async def test_document_indexing_job_skips_non_indexable_files_without_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = "550e8400-e29b-41d4-a716-446655440000"
    file_id = UUID("550e8400-e29b-41d4-a716-446655440002")
    runtime_provider = object()
    fake_file = SimpleNamespace(
        id=file_id,
        name="diagram.png",
        content_type="image/png",
        file_type="Image",
        uri="file://diagram.png",
        date_created=datetime.now(UTC),
        date_modified=None,
        is_deleted=False,
    )

    fake_data_service = SimpleNamespace(
        get_non_deleted_files_batch_by_cursor_async=AsyncMock(side_effect=[[fake_file], []]),
    )
    fake_storage_provider = SimpleNamespace(download_file=AsyncMock())
    fake_index_service = SimpleNamespace(
        clear_index=AsyncMock(),
        delete_project_file=AsyncMock(),
        is_project_file_indexable=lambda **_kwargs: False,
        index_project_file=AsyncMock(),
    )

    monkeypatch.setattr(
        "kontext.data.FileDataService",
        lambda project_uuid: fake_data_service,
    )
    monkeypatch.setattr(
        "kontext.storage.factory.get_storage_provider",
        lambda: fake_storage_provider,
    )

    def _document_index_service_factory(
        *, project_id: str | None = None, runtime_provider=None, **_kwargs
    ):
        assert project_id == context.project_id
        assert runtime_provider is context.get_runtime_provider()
        return fake_index_service

    context = _FakeJobContext(project_id, runtime_provider=runtime_provider)
    monkeypatch.setattr(
        "kontext.catalog.DocumentIndexService",
        _document_index_service_factory,
    )
    job = DocumentIndexingJob()

    result = await job.execute_job(context, DocumentIndexingParams())

    assert result.success is True
    assert result.data["files_indexed"] == 0
    assert result.data["files_skipped"] == 1
    fake_storage_provider.download_file.assert_not_called()
    fake_index_service.delete_project_file.assert_awaited_once_with(str(file_id))
    fake_index_service.index_project_file.assert_not_called()
