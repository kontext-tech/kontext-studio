"""Tests for CatalogIndexService."""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from kontext.catalog import LocalHashEmbedding
from kontext.catalog.indexing.catalog_index import CatalogIndexService
from kontext.schema import (
    CatalogColumn,
    CatalogConnection,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogEntityDetail,
    CatalogEntitySummary,
    CatalogEntityType,
    CatalogSourceKind,
    QueryEngineType,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for LanceDB."""
    temp_dir = tempfile.mkdtemp()

    with patch("kontext.catalog.indexing.storage_paths.get_project_vector_db_path") as mock_vdb:
        mock_vdb.return_value = str(Path(temp_dir) / "vector_db")
        yield temp_dir

    shutil.rmtree(temp_dir)


def _build_connection(project_id: str, connection_id: str) -> CatalogConnection:
    return CatalogConnection(
        id=connection_id,
        project_id=project_id,
        provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
        connection_kind=CatalogConnectionKind.INTERNAL,
        display_name="Default Lakehouse",
        enabled=True,
        config=CatalogConnectionConfig(),
        capabilities=CatalogConnectionCapabilities(),
    )


def _build_detail(
    *,
    connection_id: str,
    entity_id: str,
    namespace_name: str,
    entity_name: str,
    description: str,
    columns: list[tuple[str, str]],
) -> CatalogEntityDetail:
    return CatalogEntityDetail(
        entity=CatalogEntitySummary(
            id=entity_id,
            connection_id=connection_id,
            namespace_name=namespace_name,
            entity_name=entity_name,
            entity_type=CatalogEntityType.TABLE,
            description=description,
            column_count=len(columns),
        ),
        columns=[
            CatalogColumn(name=column_name, data_type=data_type)
            for column_name, data_type in columns
        ],
    )


def _patch_empty_source_lookups(service: CatalogIndexService, monkeypatch) -> None:
    async def fake_list_source_links_for_connection_async(_connection_id):
        return []

    async def fake_get_files_by_ids_async(_file_ids):
        return []

    monkeypatch.setattr(
        service._catalog_data_service,
        "list_source_links_for_connection_async",
        fake_list_source_links_for_connection_async,
    )
    monkeypatch.setattr(
        service._file_data_service,
        "get_files_by_ids_async",
        fake_get_files_by_ids_async,
    )


async def test_catalog_index_and_search(temp_workspace, monkeypatch):
    project_id = "00000000-0000-0000-0000-000000000001"
    connection_id = "00000000-0000-0000-0000-00000000000d"
    service = CatalogIndexService(
        project_id,
        catalog_connection_id=connection_id,
        embedding_provider=LocalHashEmbedding(),
    )
    connection = _build_connection(project_id, connection_id)
    details = [
        _build_detail(
            connection_id=connection_id,
            entity_id="00000000-0000-0000-0000-000000000101",
            namespace_name="raw",
            entity_name="customers",
            description="Customer profiles",
            columns=[("id", "UUID"), ("email", "VARCHAR")],
        ),
        _build_detail(
            connection_id=connection_id,
            entity_id="00000000-0000-0000-0000-000000000102",
            namespace_name="raw",
            entity_name="orders",
            description="Purchase orders",
            columns=[
                ("id", "UUID"),
                ("customer_id", "UUID"),
                ("total_amount", "DECIMAL"),
            ],
        ),
    ]
    _patch_empty_source_lookups(service, monkeypatch)

    await service.index_catalog_entities(
        connection=connection,
        entities=details,
        engine_type=QueryEngineType.DUCKDB,
        recreate=True,
    )

    results = await service.search(
        query="show me customer profile tables",
        engine_type=QueryEngineType.DUCKDB,
        limit=5,
        catalog_connection_id=connection_id,
    )

    assert len(results) > 0
    assert results[0].table_name == "customers"
    assert results[0].rank == 1
    assert results[0].score is not None and results[0].score > 0

    results = await service.search(
        query="where are the purchase orders?",
        engine_type=QueryEngineType.DUCKDB,
        limit=1,
        catalog_connection_id=connection_id,
    )

    assert len(results) == 1
    assert results[0].table_name == "orders"
    assert results[0].rank == 1


async def test_catalog_search_exact_entity_query_filters_weak_tail_matches(
    temp_workspace,
    monkeypatch,
):
    project_id = "00000000-0000-0000-0000-000000000021"
    connection_id = "00000000-0000-0000-0000-0000000000de"
    service = CatalogIndexService(
        project_id,
        catalog_connection_id=connection_id,
        embedding_provider=LocalHashEmbedding(),
    )
    connection = _build_connection(project_id, connection_id)
    details = [
        _build_detail(
            connection_id=connection_id,
            entity_id="00000000-0000-0000-0000-000000000201",
            namespace_name="raw",
            entity_name="transactions",
            description="Bank transactions",
            columns=[("transaction_id", "UUID"), ("amount", "DECIMAL")],
        ),
        _build_detail(
            connection_id=connection_id,
            entity_id="00000000-0000-0000-0000-000000000202",
            namespace_name="raw",
            entity_name="customers",
            description="Transactions reference for customer support",
            columns=[("customer_id", "UUID"), ("email", "VARCHAR")],
        ),
        _build_detail(
            connection_id=connection_id,
            entity_id="00000000-0000-0000-0000-000000000203",
            namespace_name="raw",
            entity_name="product_reference",
            description="Reference data for products",
            columns=[("product_code", "VARCHAR"), ("description", "VARCHAR")],
        ),
    ]
    _patch_empty_source_lookups(service, monkeypatch)

    await service.index_catalog_entities(
        connection=connection,
        entities=details,
        engine_type=QueryEngineType.DUCKDB,
        recreate=True,
    )

    results = await service.search(
        query="transactions",
        engine_type=QueryEngineType.DUCKDB,
        limit=10,
        catalog_connection_id=connection_id,
    )

    assert [item.table_name for item in results] == ["transactions"]
    assert results[0].rank == 1
    assert results[0].score is not None and results[0].score >= 80


async def test_catalog_search_collapses_column_hits_to_entities(
    temp_workspace,
    monkeypatch,
):
    project_id = "00000000-0000-0000-0000-000000000010"
    connection_id = "00000000-0000-0000-0000-0000000000aa"
    service = CatalogIndexService(
        project_id,
        embedding_provider=LocalHashEmbedding(),
    )
    connection = _build_connection(project_id, connection_id)
    detail = _build_detail(
        connection_id=connection_id,
        entity_id="00000000-0000-0000-0000-0000000000bb",
        namespace_name="raw",
        entity_name="customers",
        description="Customer profiles",
        columns=[("customer_id", "UUID"), ("email", "TEXT")],
    )
    _patch_empty_source_lookups(service, monkeypatch)

    await service.index_catalog_entities(
        connection=connection,
        entities=[detail],
        engine_type=QueryEngineType.DUCKDB,
        recreate=True,
    )

    results = await service.search(
        query="email column",
        engine_type=QueryEngineType.DUCKDB,
        limit=5,
        catalog_connection_id=connection_id,
    )

    assert len(results) == 1
    assert results[0].table_name == "customers"
    assert "email" in results[0].content.lower()
    assert results[0].rank == 1
    assert results[0].score is not None and results[0].score > 0


async def test_index_catalog_entities_returns_indexed_document_count(
    temp_workspace,
    monkeypatch,
):
    project_id = "00000000-0000-0000-0000-000000000031"
    connection_id = "00000000-0000-0000-0000-0000000000ef"
    service = CatalogIndexService(
        project_id,
        catalog_connection_id=connection_id,
        embedding_provider=LocalHashEmbedding(),
    )
    connection = _build_connection(project_id, connection_id)
    detail = _build_detail(
        connection_id=connection_id,
        entity_id="00000000-0000-0000-0000-000000000301",
        namespace_name="raw",
        entity_name="customers",
        description="Customer profiles",
        columns=[("customer_id", "UUID"), ("email", "VARCHAR")],
    )
    _patch_empty_source_lookups(service, monkeypatch)

    result = await service.index_catalog_entities(
        connection=connection,
        entities=[detail],
        engine_type=QueryEngineType.DUCKDB,
        recreate=True,
    )

    assert result == 3
