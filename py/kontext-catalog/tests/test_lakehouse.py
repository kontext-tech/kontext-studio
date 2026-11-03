from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest import mock
from unittest.mock import patch
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pyarrow as pa
import pytest
from openpyxl import Workbook
from pyiceberg.catalog import Catalog
from sqlalchemy import select

from kontext.catalog import CatalogManagementService, LakehouseService
from kontext.common.utils.path_policy import PathAccessDeniedError
from kontext.data.database import get_engine, get_session_factory, get_sync_db_session
from kontext.data.models import Project
from kontext.file.helpers import InMemoryUploadFile
from kontext.file.service import FileService
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.runtime.providers.local import LocalRuntimeProvider
from kontext.schema import (
    CatalogConnection,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogEntityDetail,
    CatalogEntitySummary,
    CatalogEntityType,
    CatalogSourceKind,
    FileFormatType,
)
from kontext.storage import clear_storage_provider_cache, get_storage_provider


def _clear_runtime_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    clear_storage_provider_cache()


def _path_from_uri(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return Path(parsed.path).resolve()
    return Path(uri).resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


@pytest.fixture()
def local_project_id(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_url = f"sqlite:///{tmp_path / 'kontext.db'}"
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(storage_root))
    monkeypatch.setenv("FILE_STORAGE_PATH", str(storage_root))

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


def _create_file_service(project_id: UUID) -> FileService:
    return FileService(
        project_id=project_id,
        storage_provider=get_storage_provider(force_new=True),
        queue_client=None,
    )


@pytest.mark.asyncio
async def test_delete_file_entities_uses_purge_table(monkeypatch):
    project_id = str(uuid4())
    connection_id = str(uuid4())
    entity_id = str(uuid4())
    service = LakehouseService(project_id)
    connection = CatalogConnection(
        id=connection_id,
        project_id=project_id,
        provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
        connection_kind=CatalogConnectionKind.INTERNAL,
        display_name="Default",
        config=CatalogConnectionConfig(),
        capabilities=CatalogConnectionCapabilities(),
    )
    detail = CatalogEntityDetail(
        entity=CatalogEntitySummary(
            id=entity_id,
            connection_id=connection_id,
            namespace_name="bronze",
            entity_name="orders",
            entity_type=CatalogEntityType.TABLE,
            column_count=2,
        ),
        columns=[],
    )

    purged_identifiers: list[tuple[str, str, str]] = []

    class FakeCatalog:
        def table_exists(self, identifier):
            return True

        def purge_table(self, identifier):
            purged_identifiers.append(identifier)

        def drop_table(self, identifier):
            raise AssertionError("drop_table should not be used for managed cleanup")

    async def fake_ensure_internal_connection():
        return connection

    async def fake_list_source_links_async(*, source_type: str, source_id: str):
        assert source_type == "file"
        assert source_id
        return [SimpleNamespace(entity_id=entity_id, connection_id=connection_id)]

    async def fake_get_entity_detail_async(received_entity_id: str):
        assert received_entity_id == entity_id
        return detail

    monkeypatch.setattr(service, "ensure_internal_connection", fake_ensure_internal_connection)
    monkeypatch.setattr(
        service._catalog_data_service,
        "list_source_links_async",
        fake_list_source_links_async,
    )
    monkeypatch.setattr(
        service._catalog_data_service,
        "get_entity_detail_async",
        fake_get_entity_detail_async,
    )
    monkeypatch.setattr(service, "_get_catalog", lambda _: cast(Catalog, FakeCatalog()))

    deleted_entities = await service.delete_file_entities(str(uuid4()))

    assert deleted_entities == [entity_id]
    assert purged_identifiers == [service._table_identifier("bronze", "orders")]


def test_write_arrow_table_purges_existing_table_before_recreate():
    project_id = str(uuid4())
    service = LakehouseService(project_id)
    arrow_table = pa.table({"id": [1], "total": [10]})
    source_file_id = str(uuid4())
    source_uri = "file:///tmp/orders.csv"
    identifier = service._table_identifier("bronze", "orders")

    purged_identifiers: list[tuple[str, str, str]] = []
    created_identifiers: list[tuple[str, str, str]] = []
    appended_snapshot_properties: list[dict[str, str]] = []

    class FakeTransaction:
        def set_properties(self, properties):
            return self

        def commit_transaction(self):
            return None

    class ExistingTable:
        def transaction(self):
            return FakeTransaction()

        def overwrite(self, _arrow_table, snapshot_properties=None):
            raise RuntimeError("overwrite failed")

    class CreatedTable:
        def append(self, _arrow_table, snapshot_properties=None):
            appended_snapshot_properties.append(snapshot_properties or {})

        def refresh(self):
            return self

    class FakeCatalog:
        def table_exists(self, _identifier):
            return True

        def load_table(self, _identifier):
            return ExistingTable()

        def purge_table(self, received_identifier):
            purged_identifiers.append(received_identifier)

        def drop_table(self, received_identifier):
            raise AssertionError(
                f"drop_table should not be used for managed cleanup: {received_identifier}"
            )

        def create_table(self, received_identifier, schema, properties):
            assert schema is not None
            assert properties["format-version"] == "2"
            created_identifiers.append(received_identifier)
            return CreatedTable()

    result = service._write_arrow_table(
        catalog=cast(Catalog, FakeCatalog()),
        namespace_name="bronze",
        table_name="orders",
        arrow_table=arrow_table,
        source_file_id=source_file_id,
        source_uri=source_uri,
    )

    assert result is not None
    assert purged_identifiers == [identifier]
    assert created_identifiers == [identifier]
    assert appended_snapshot_properties == [
        {
            "kontext.project_id": project_id,
            "kontext.source_file_id": source_file_id,
            "kontext.source_uri": source_uri,
        }
    ]


@pytest.mark.asyncio
async def test_ingest_file_keeps_metadata_in_lakehouse_and_purges_table_files(
    local_project_id,
):
    file_service = _create_file_service(local_project_id)
    upload = InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv")
    created = await file_service.upload_single_file(
        project_id=local_project_id,
        upload_file=upload,
    )

    catalog_service = CatalogManagementService(str(local_project_id))
    entity_details = await catalog_service.ingest_file(str(created.id))

    assert entity_details
    detail = entity_details[0]
    metadata_location = str((detail.entity.metadata or {}).get("metadataLocation") or "")
    source_uri = str((detail.entity.metadata or {}).get("sourceUri") or "")
    table_location = str(detail.entity.location or "")

    assert metadata_location
    assert source_uri
    assert table_location

    connection = await catalog_service.ensure_default_internal_connection()
    warehouse_root = _path_from_uri(connection.config.warehouse_path or "")
    source_root = (
        Path(os.environ["KONTEXT_LOCAL_STORAGE_PATH"]).resolve()
        / "projects"
        / str(local_project_id)
        / "resources"
    )

    metadata_path = _path_from_uri(metadata_location)
    table_root = _path_from_uri(table_location)
    source_path = _path_from_uri(source_uri)

    assert metadata_path.exists()
    assert source_path.exists()
    assert _is_relative_to(table_root, warehouse_root)
    assert _is_relative_to(metadata_path, table_root)
    assert _is_relative_to(metadata_path, warehouse_root)
    assert _is_relative_to(source_path, source_root)
    assert not _is_relative_to(metadata_path, source_root)

    deleted_entity_ids = await catalog_service.remove_file_entities(str(created.id))

    assert detail.entity.id in deleted_entity_ids
    remaining_entities = await catalog_service.list_entities(connection_id=connection.id or None)
    assert not any(entity.id == detail.entity.id for entity in remaining_entities)
    assert not metadata_path.exists()

    remaining_table_files = (
        [path for path in table_root.rglob("*") if path.is_file()] if table_root.exists() else []
    )
    assert not remaining_table_files


@pytest.mark.asyncio
async def test_ingested_bronze_table_is_queryable_via_duckdb(local_project_id):
    file_service = _create_file_service(local_project_id)
    upload = InMemoryUploadFile("orders.csv", b"id,total\n1,10\n", "text/csv")
    created = await file_service.upload_single_file(
        project_id=local_project_id,
        upload_file=upload,
    )

    catalog_service = CatalogManagementService(str(local_project_id))
    entity_details = await catalog_service.ingest_file(str(created.id))

    assert entity_details
    detail = entity_details[0]

    runtime_provider = LocalRuntimeProvider(project_id=str(local_project_id))
    query_session_service = runtime_provider.get_query_session_service()

    assert query_session_service is not None

    response = await query_session_service.execute_sql_with_session_management(
        project_id=str(local_project_id),
        sql_query=f'SELECT * FROM "bronze"."{detail.entity.entity_name}" LIMIT 10',
        catalog_connection_id=detail.entity.connection_id,
        default_namespace="bronze",
        store_result_as_resource=False,
        store_result_threshold_rows=None,
    )

    assert response.success is True
    assert response.data_id is None
    assert response.result is not None
    assert [column.name for column in response.result.columns or []] == ["id", "total"]
    assert response.result.row_count == 1
    assert response.result.rows == [[1, 10]]


@pytest.mark.asyncio
async def test_ingest_excel_file_creates_snapshot_per_real_worksheet(local_project_id):
    workbook = Workbook()
    products_sheet = workbook.active
    assert products_sheet is not None
    products_sheet.title = "Products"
    products_sheet.append(["product_id", "name"])
    products_sheet.append([1, "Laptop"])

    orders_sheet = workbook.create_sheet("Orders")
    orders_sheet.append(["order_id", "product_id"])
    orders_sheet.append([100, 1])

    items_sheet = workbook.create_sheet("Order Items")
    items_sheet.append(["item_id", "order_id"])
    items_sheet.append([1000, 100])

    excel_buffer = BytesIO()
    workbook.save(excel_buffer)
    workbook.close()

    file_service = _create_file_service(local_project_id)
    created = await file_service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile(
            "sales_orders.xlsx",
            excel_buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    )

    snapshots = await LakehouseService(str(local_project_id)).ingest_file(str(created.id))

    assert len(snapshots) == 3
    entity_names = {snapshot.entity_name for snapshot in snapshots}
    assert entity_names == {
        "sales_orders_Products",
        "sales_orders_Orders",
        "sales_orders_Order_Items",
    }

    for snapshot in snapshots:
        metadata = snapshot.metadata or {}
        assert metadata.get("sourceUri")
        assert snapshot.namespace_name == "bronze"


@pytest.mark.asyncio
async def test_sync_connection_reuses_single_namespace_for_multi_sheet_excel(
    local_project_id,
):
    workbook = Workbook()
    products_sheet = workbook.active
    assert products_sheet is not None
    products_sheet.title = "Products"
    products_sheet.append(["product_id", "name"])
    products_sheet.append([1, "Laptop"])

    orders_sheet = workbook.create_sheet("Orders")
    orders_sheet.append(["order_id", "product_id"])
    orders_sheet.append([100, 1])

    items_sheet = workbook.create_sheet("Order Items")
    items_sheet.append(["item_id", "order_id"])
    items_sheet.append([1000, 100])

    excel_buffer = BytesIO()
    workbook.save(excel_buffer)
    workbook.close()

    file_service = _create_file_service(local_project_id)
    created = await file_service.upload_single_file(
        project_id=local_project_id,
        upload_file=InMemoryUploadFile(
            "sales_orders.xlsx",
            excel_buffer.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
    )

    lakehouse_service = LakehouseService(str(local_project_id))
    await lakehouse_service.ingest_file(str(created.id))

    catalog_service = CatalogManagementService(str(local_project_id))
    connection = await catalog_service.ensure_default_internal_connection()
    sync_status = await catalog_service.sync_connection(connection.id or "")

    assert sync_status.status == "succeeded"
    assert sync_status.entity_count == 3

    entities = await catalog_service.list_entities(connection_id=connection.id or None)
    assert len(entities) == 3
    assert all(entity.namespace_name == "bronze" for entity in entities)


def _make_excel_file(tmp_path: Path) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Sheet1"
    sheet.append(["id", "total"])
    sheet.append([1, 10])
    path = tmp_path / "orders.xlsx"
    workbook.save(path)
    workbook.close()
    return path


def test_read_source_to_arrow_skips_install_when_excel_already_installed(tmp_path, monkeypatch):
    """Excel reads must not hit the network once the extension is cached.

    ``INSTALL`` downloads from the DuckDB extension repository. Calling it on
    every Excel read coupled unrelated ingest paths to network egress and made
    the local-mode job tests flaky on a cold extension cache.
    """
    import duckdb

    workbook_path = _make_excel_file(tmp_path)

    # Warm the extension cache so the "already installed" branch is exercised.
    warmup = duckdb.connect()
    warmup.execute("INSTALL excel")
    warmup.close()

    issued: list[str] = []
    real_execute = duckdb.DuckDBPyConnection.execute

    def _record(self, sql, *args, **kwargs):
        if isinstance(sql, str):
            issued.append(sql.strip())
        return real_execute(self, sql, *args, **kwargs)

    monkeypatch.setattr(duckdb.DuckDBPyConnection, "execute", _record)
    table = LakehouseService._read_source_to_arrow(
        LakehouseService("test-project"),
        temp_path=workbook_path,
        file_type=FileFormatType.EXCEL,
        sub_table_name="Sheet1",
    )
    monkeypatch.undo()

    assert table.num_rows == 1
    assert not any(statement.startswith("INSTALL") for statement in issued), issued
    assert any(statement.startswith("LOAD excel") for statement in issued), issued


def test_read_source_to_arrow_skips_install_for_non_excel_formats(tmp_path, monkeypatch):
    """Non-Excel reads must never touch the Excel extension or the network."""
    import duckdb

    csv_path = tmp_path / "orders.csv"
    csv_path.write_text("id,total\n1,10\n")

    issued: list[str] = []
    real_execute = duckdb.DuckDBPyConnection.execute

    def _record(self, sql, *args, **kwargs):
        if isinstance(sql, str):
            issued.append(sql.strip())
        return real_execute(self, sql, *args, **kwargs)

    monkeypatch.setattr(duckdb.DuckDBPyConnection, "execute", _record)
    table = LakehouseService._read_source_to_arrow(
        LakehouseService("test-project"),
        temp_path=csv_path,
        file_type=FileFormatType.CSV,
        sub_table_name=None,
    )
    monkeypatch.undo()

    assert table.num_rows == 1
    assert not any("excel" in statement.lower() for statement in issued), issued


def test_ensure_duckdb_extension_tolerates_install_failure_without_network():
    """A failed ``INSTALL`` is logged, not fatal, so LOAD is still attempted."""
    import duckdb

    issued: list[str] = []
    install_failures: list[str] = []

    class _FakeConnection:
        """Minimal stand-in that fails INSTALL but always allows LOAD."""

        def execute(self, sql, *args, **kwargs):
            statement = next(
                (value for value in (sql, *args) if isinstance(value, str)),
                "",
            ).strip()
            if not statement.startswith(("INSTALL", "LOAD")):
                # The duckdb_extensions() lookup: report "not installed".
                cursor = mock.MagicMock()
                cursor.fetchone.return_value = (False,)
                return cursor
            issued.append(statement)
            if statement.startswith("INSTALL") and statement not in install_failures:
                install_failures.append(statement)
                raise duckdb.Error("simulated network failure")
            return None

    with patch(
        "kontext.catalog.connections.lakehouse.logger.warning",
    ) as warning:
        LakehouseService._ensure_duckdb_extension(
            cast("duckdb.DuckDBPyConnection", _FakeConnection()), "excel"
        )

    assert any(statement.startswith("INSTALL excel") for statement in issued)
    assert issued[-1].startswith("LOAD excel")
    warning.assert_called_once()


def test_local_warehouse_path_is_confined_to_allowed_roots(local_project_id, tmp_path) -> None:
    service = LakehouseService(str(local_project_id))

    inside = tmp_path / "storage" / "warehouse"
    assert service._normalize_warehouse_uri(str(inside)).startswith("file://")

    with pytest.raises(PathAccessDeniedError):
        service._normalize_warehouse_uri(str(tmp_path / "outside-warehouse"))
