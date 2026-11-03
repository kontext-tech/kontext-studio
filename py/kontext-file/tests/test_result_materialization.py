"""Integration tests for the unified result materialization path.

The single writer shared by the query job and the AI toolkit:
* small results are embedded in full in the ``.dt`` descriptor (no sidecar);
* large results keep a bounded preview in the descriptor plus a
  content-addressed Arrow row store for the full rows.
"""

from __future__ import annotations

import json
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import select

from kontext.common.constants import QueryConstants
from kontext.data.database import get_engine, get_session_factory, get_sync_db_session
from kontext.data.models import Project
from kontext.file.helpers import InMemoryUploadFile
from kontext.file.service import FileService
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.schema import (
    ArtifactOrigin,
    ArtifactProvenance,
    DataColumn,
    DataTable,
    InlineData,
    QueryResponse,
    TriggerActorModel,
    TriggerActorType,
)
from kontext.storage import clear_storage_provider_cache, get_storage_provider

# Above the inline-embed threshold, so materialization writes an Arrow sidecar.
_LARGE = QueryConstants.DOCUMENT_EMBEDDING_THRESHOLD + 10
_SMALL = 5


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


def _service(project_id: UUID) -> FileService:
    return FileService(
        project_id=project_id,
        storage_provider=get_storage_provider(force_new=True),
        queue_client=None,
    )


def _result(row_count: int) -> QueryResponse:
    return QueryResponse(
        result=DataTable(
            columns=[
                DataColumn(name="type", type="VARCHAR"),
                DataColumn(name="transaction_count", type="BIGINT"),
            ],
            rows=[[f"type-{index}", index] for index in range(row_count)],
            row_count=row_count,
        ),
        total_execution_time_ms=3,
        success=True,
        sql="SELECT type, COUNT(*) FROM bronze.transactions GROUP BY 1",
    )


async def _describe(service: FileService, project_id: UUID, file_id: str | None) -> dict:
    assert file_id is not None
    return json.loads(await service.get_file_content(project_id, file_id))


def _rows(table: DataTable | None) -> list[list[object]]:
    assert table is not None
    return table.rows or []


@pytest.mark.asyncio
async def test_large_result_stores_bounded_preview_and_arrow(local_project_id):
    service = _service(local_project_id)
    chat_session_id = "550e8400-e29b-41d4-a716-446655440002"

    file_id = await service.materialize_query_result(
        local_project_id,
        _result(_LARGE),
        title="Transaction counts by type and status",
        chat_session_id=chat_session_id,
    )

    descriptor = await _describe(service, local_project_id, file_id)
    assert descriptor["title"] == "Transaction counts by type and status"
    metadata = descriptor["metadata"]
    assert metadata["chatSessionId"] == chat_session_id
    assert metadata["sql"].startswith("SELECT type")
    assert metadata["rowCount"] == _LARGE
    assert metadata["dataPath"].endswith(".parquet")

    # Descriptor is bounded: far fewer rows than the full result.
    assert 0 < len(descriptor["table"]["rows"]) < _LARGE

    # Full rows remain retrievable through the file, paging the descriptor.
    assert file_id is not None
    head = await service.get_inline_data_rows(local_project_id, file_id, offset=0, limit=3)
    assert _rows(head.table) == [["type-0", 0], ["type-1", 1], ["type-2", 2]]
    assert head.table is not None and head.table.row_count == _LARGE
    # Provenance must survive the paged read (the viewer's Metadata tab relies
    # on it). Regression guard for the rows endpoint dropping metadata.
    assert head.metadata is not None
    assert head.metadata.chat_session_id == chat_session_id
    assert head.metadata.data_path == metadata["dataPath"]

    tail = await service.get_inline_data_rows(
        local_project_id, file_id, offset=_LARGE - 2, limit=None
    )
    assert _rows(tail.table) == [
        [f"type-{_LARGE - 2}", _LARGE - 2],
        [f"type-{_LARGE - 1}", _LARGE - 1],
    ]


@pytest.mark.asyncio
async def test_small_result_embeds_in_full_without_arrow(local_project_id):
    service = _service(local_project_id)

    file_id = await service.materialize_query_result(
        local_project_id, _result(_SMALL), title="Small"
    )

    descriptor = await _describe(service, local_project_id, file_id)
    assert descriptor["metadata"]["rowCount"] == _SMALL
    assert "dataPath" not in descriptor["metadata"]
    assert len(descriptor["table"]["rows"]) == _SMALL

    # Small results are still sliceable through the same public reader.
    assert file_id is not None
    window = await service.get_inline_data_rows(local_project_id, file_id, offset=1, limit=2)
    assert _rows(window.table) == [["type-1", 1], ["type-2", 2]]
    assert window.table is not None and window.table.row_count == _SMALL


@pytest.mark.asyncio
async def test_large_result_is_content_addressed(local_project_id):
    service = _service(local_project_id)

    first = await service.materialize_query_result(local_project_id, _result(_LARGE), title="A")
    second = await service.materialize_query_result(local_project_id, _result(_LARGE), title="B")

    first_meta = (await _describe(service, local_project_id, first))["metadata"]
    second_meta = (await _describe(service, local_project_id, second))["metadata"]
    assert first_meta["dataPath"] == second_meta["dataPath"]


@pytest.mark.asyncio
async def test_large_duplicate_title_creates_distinct_files(local_project_id):
    """Two different large results sharing a title must both persist (unique suffix)."""
    service = _service(local_project_id)

    # Same title, but different row counts -> different content/paths.
    first = await service.materialize_query_result(
        local_project_id, _result(_LARGE), title="Counts"
    )
    second = await service.materialize_query_result(
        local_project_id, _result(_LARGE + 1), title="Counts"
    )

    assert first != second
    first_meta = (await _describe(service, local_project_id, first))["metadata"]
    second_meta = (await _describe(service, local_project_id, second))["metadata"]
    assert first_meta["dataPath"] != second_meta["dataPath"]
    assert first_meta["rowCount"] == _LARGE
    assert second_meta["rowCount"] == _LARGE + 1


@pytest.mark.asyncio
async def test_materialize_reuses_existing_file(local_project_id):
    service = _service(local_project_id)
    original = await service.materialize_query_result(
        local_project_id, _result(_LARGE), title="Original"
    )

    updated = await service.materialize_query_result(
        local_project_id,
        _result(_LARGE + 1),
        existing_file_id=original,
        title="Original",
    )

    assert updated == original
    descriptor = await _describe(service, local_project_id, original)
    assert descriptor["metadata"]["rowCount"] == _LARGE + 1


@pytest.mark.asyncio
async def test_materialize_stamps_record_provenance(local_project_id):
    """The durable ``.dt`` record mirrors its document provenance.

    File listings render origin badges from the record, so the record must be
    stamped through the same materialization path that stamps the document.
    """
    service = _service(local_project_id)
    provenance = ArtifactProvenance(
        origin=ArtifactOrigin.AGENTPYTHON,
        created_by=TriggerActorModel(type=TriggerActorType.AGENT, id="python_tool"),
        chat_session_id="550e8400-e29b-41d4-a716-446655440002",
    )

    file_id = await service.materialize_inline_data(
        local_project_id,
        InlineData(
            title="Saved Result",
            table=DataTable(columns=[DataColumn(name="x", type="int")], rows=[[1]], row_count=1),
        ),
        provenance=provenance,
    )

    assert file_id is not None
    model = await service.get_file_details(local_project_id, file_id)
    assert model.provenance is not None
    assert model.provenance.origin == ArtifactOrigin.AGENTPYTHON
    assert model.provenance.created_by is not None
    assert model.provenance.created_by.id == "python_tool"


@pytest.mark.asyncio
async def test_upload_single_file_stamps_upload_provenance(local_project_id):
    """User uploads stamp origin=upload with the requesting actor on the record."""
    service = _service(local_project_id)

    result = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("orders.csv", b"a,b\n1,2\n"),
        prefix="",
        provenance=ArtifactProvenance(
            origin=ArtifactOrigin.UPLOAD,
            created_by=TriggerActorModel(type=TriggerActorType.USER, id="user-1"),
        ),
    )

    model = await service.get_file_details(local_project_id, result.id)
    assert model.provenance is not None
    assert model.provenance.origin == ArtifactOrigin.UPLOAD
    assert model.provenance.created_by is not None
    assert model.provenance.created_by.type == TriggerActorType.USER

    # A record written before provenance stamping stays un-provenanced.
    legacy = await service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile("legacy.csv", b"x\n1\n"),
        prefix="",
    )
    legacy_model = await service.get_file_details(local_project_id, legacy.id)
    assert legacy_model.provenance is None


@pytest.mark.asyncio
async def test_create_chart_stamps_record_provenance(local_project_id):
    """Chart file records derive their stamp from the document metadata."""
    from datetime import UTC, datetime

    from kontext.schema import ChartConfig, ChartDocument, ChartDocumentMetadata

    service = _service(local_project_id)
    now = datetime.now(UTC)
    chart = ChartDocument(
        name="Revenue",
        config=ChartConfig.model_validate(
            {
                "chartType": "line",
                "title": "Revenue",
                "xField": "month",
                "yField": "amount",
                "height": 300,
            }
        ),
        metadata=ChartDocumentMetadata(
            created_at=now,
            modified_at=now,
            version="1.0.0",
            origin=ArtifactOrigin.CHARTCOMPOSE,
            created_by_type=TriggerActorType.AGENT,
            created_by_id="chart_tool",
            identity_key="a" * 64,
        ),
    )

    response = await service.create_chart(local_project_id, chart, name="Revenue")

    provenance = response.file.provenance
    assert provenance is not None
    assert provenance.origin == ArtifactOrigin.CHARTCOMPOSE
    assert provenance.created_by is not None
    assert provenance.created_by.id == "chart_tool"
    assert provenance.identity_key == "a" * 64


@pytest.mark.asyncio
async def test_materialize_parquet_inline_data_builds_preview_and_row_store(
    local_project_id,
):
    """Parquet bytes materialize without a full decode: preview + row store only."""
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    service = _service(local_project_id)
    provenance = ArtifactProvenance(
        origin=ArtifactOrigin.AGENTPYTHON,
        created_by=TriggerActorModel(type=TriggerActorType.AGENT, id="python_tool"),
    )
    buffer = io.BytesIO()
    pq.write_table(
        pa.table({"value": list(range(200)), "label": [f"row-{i}" for i in range(200)]}),
        buffer,
    )

    file_id = await service.materialize_parquet_inline_data(
        local_project_id,
        buffer.getvalue(),
        name="Saved Frame",
        provenance=provenance,
    )

    assert file_id is not None
    descriptor = await _describe(service, local_project_id, file_id)
    metadata = descriptor["metadata"]
    assert metadata["dataPath"]
    assert metadata["rowCount"] == 200
    assert metadata["origin"] == "agent_python"
    assert metadata["createdByType"] == "Agent"
    assert metadata["createdById"] == "python_tool"

    table = descriptor["table"]
    # The descriptor embeds a bounded preview, not all 200 rows.
    assert table["rowCount"] == 200
    assert len(table["rows"]) < 200
    assert [column["name"] for column in table["columns"]] == ["value", "label"]

    # The full rows remain readable through the stored row store.
    full = await service.get_inline_data_rows(local_project_id, file_id, offset=0, limit=500)
    assert full.table is not None
    assert full.table.rows is not None
    assert len(full.table.rows) == 200
    assert full.table.rows[0] == [0, "row-0"]

    model = await service.get_file_details(local_project_id, file_id)
    assert model.provenance is not None
    assert model.provenance.origin == ArtifactOrigin.AGENTPYTHON
