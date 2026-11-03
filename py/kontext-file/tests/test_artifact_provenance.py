from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import select

from kontext.data.database import get_engine, get_session_factory, get_sync_db_session
from kontext.data.models import Project
from kontext.file.charts import ChartService
from kontext.file.service import FileService
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.schema import (
    ChartDocument,
    ChartDocumentMetadata,
    DataTable,
    InlineData,
    QueryResponse,
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


@pytest.mark.asyncio
async def test_create_inline_data_file_records_provenance(local_project_id):
    service = _create_service(local_project_id)
    query_session_id = "550e8400-e29b-41d4-a716-446655440001"
    chat_session_id = "550e8400-e29b-41d4-a716-446655440002"

    response = await service.create_inline_data_file(
        project_id=local_project_id,
        inline_data=InlineData(
            title="counts",
            table=DataTable(columns=[], rows=[[0, 10]], row_count=1),
        ),
        query_session_id=query_session_id,
        chat_session_id=chat_session_id,
        sql="SELECT 1",
    )

    stored = await service.get_data_table_file(local_project_id, response.file.id)
    assert stored.metadata is not None
    assert stored.metadata.query_session_id == query_session_id
    assert stored.metadata.chat_session_id == chat_session_id
    assert stored.metadata.sql == "SELECT 1"
    assert stored.metadata.created_at is not None


@pytest.mark.asyncio
async def test_store_query_results_as_file_records_sql_and_sessions(local_project_id):
    service = _create_service(local_project_id)
    query_session_id = "550e8400-e29b-41d4-a716-446655440003"
    chat_session_id = "550e8400-e29b-41d4-a716-446655440004"

    response = QueryResponse(
        result=DataTable(columns=[], rows=[[1]], row_count=1),
        success=True,
        sql="SELECT count(*) FROM t",
    )

    file_id = await service.store_query_results_as_file(
        project_id=local_project_id,
        query_response=response,
        session_id=query_session_id,
        chat_session_id=chat_session_id,
    )
    assert file_id is not None

    stored = await service.get_data_table_file(local_project_id, file_id)
    assert stored.metadata is not None
    assert stored.metadata.sql == "SELECT count(*) FROM t"
    assert stored.metadata.query_session_id == query_session_id
    assert stored.metadata.chat_session_id == chat_session_id


@pytest.mark.asyncio
async def test_create_chart_records_provenance(local_project_id):
    service = _create_service(local_project_id)
    created_at = datetime(2024, 1, 1, tzinfo=UTC)
    chart = ChartDocument(
        name="Provenance Chart",
        metadata=ChartDocumentMetadata(
            description=None,
            created_at=created_at,
            modified_at=created_at,
        ),
        config=ChartService.create_box_chart_config(
            title="Provenance",
            x_field="category",
            y_field="metric",
        ),
    )

    response = await service.create_chart(
        project_id=local_project_id,
        chart=chart,
        query_session_id="550e8400-e29b-41d4-a716-446655440005",
        chat_session_id="550e8400-e29b-41d4-a716-446655440006",
    )

    content = await service.get_file_content(local_project_id, response.file.id)
    stored = ChartDocument.model_validate_json(content)
    assert stored.metadata is not None
    assert stored.metadata.query_session_id == "550e8400-e29b-41d4-a716-446655440005"
    assert stored.metadata.chat_session_id == "550e8400-e29b-41d4-a716-446655440006"
