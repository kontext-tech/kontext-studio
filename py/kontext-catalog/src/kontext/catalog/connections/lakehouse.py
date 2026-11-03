"""Internal Iceberg lakehouse services.

Uploaded source files stay in regular file storage. Managed Iceberg tables write
their own data and metadata into the project lakehouse warehouse.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from uuid import UUID

import duckdb
from openpyxl import load_workbook
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.io.pyarrow import _pyarrow_to_schema_without_ids
from pyiceberg.schema import assign_fresh_schema_ids
from pyiceberg.table.name_mapping import create_mapping_from_schema

from kontext.common.utils.file_storage import get_project_storage_path
from kontext.common.utils.path_policy import ensure_within_allowed_roots
from kontext.data import CatalogDataService, CatalogEntitySnapshot, FileDataService
from kontext.data.database import get_project_database_url
from kontext.schema import (
    CatalogColumn,
    CatalogConnection,
    CatalogEntityType,
    FileFormatType,
)
from kontext.storage import get_storage_provider
from kontext.storage.providers.base import BaseStorageProvider

logger = logging.getLogger(__name__)


class LakehouseService:
    """Manages internal Iceberg lakehouse state for a project."""

    def __init__(
        self,
        project_id: str,
        *,
        storage_provider: BaseStorageProvider | None = None,
    ) -> None:
        self.project_id = str(project_id)
        self._storage_provider: BaseStorageProvider = storage_provider or get_storage_provider()
        self._catalog_data_service = CatalogDataService(self.project_id)
        self._file_data_service = FileDataService(self.project_id)

    async def ensure_internal_connection(self) -> CatalogConnection:
        """Return the project's internal Iceberg connection, creating it if needed.

        Delegates to :class:`CatalogManagementService` so the internal
        connection has a single, canonical factory (the provider's
        ``default_request``) rather than divergent hand-built capability payloads.
        """
        from .management import CatalogManagementService

        return await CatalogManagementService(self.project_id).ensure_default_internal_connection()

    async def ingest_file(
        self,
        file_id: UUID | str,
        *,
        namespace_name: str | None = None,
    ) -> list[CatalogEntitySnapshot]:
        """Materialize a managed Iceberg table from an uploaded source file."""
        connection = await self.ensure_internal_connection()
        file_record = await self._file_data_service.get_file_by_id_async(UUID(str(file_id)))
        if file_record is None:
            raise ValueError(f"File {file_id} not found")
        if not file_record.uri:
            raise ValueError(f"File {file_id} has no storage URI")

        file_type = FileFormatType(file_record.file_type)
        effective_namespace = namespace_name or connection.config.default_namespace or "bronze"
        with tempfile.TemporaryDirectory(prefix="kontext-lakehouse-") as temp_dir:
            temp_path = Path(temp_dir) / Path(file_record.name).name
            stream = await self._storage_provider.download_file(file_record.uri)
            temp_path.write_bytes(stream.getvalue())
            table_specs = self._table_specs_for_file(temp_path, file_type)

            catalog = self._get_catalog(connection)
            self._ensure_namespace(catalog, effective_namespace)

            snapshots: list[CatalogEntitySnapshot] = []
            for table_name, sub_table_name in table_specs:
                # DuckDB reads, PyIceberg writes, and schema conversion are all
                # blocking; run them off the event loop so the server stays
                # responsive during (potentially large) ingests.
                arrow_table = await asyncio.to_thread(
                    self._read_source_to_arrow,
                    temp_path=temp_path,
                    file_type=file_type,
                    sub_table_name=sub_table_name,
                )
                table = await asyncio.to_thread(
                    self._write_arrow_table,
                    catalog=catalog,
                    namespace_name=effective_namespace,
                    table_name=table_name,
                    arrow_table=arrow_table,
                    source_file_id=str(file_record.id),
                    source_uri=file_record.uri,
                )
                snapshots.append(
                    self._snapshot_from_table(
                        table=table,
                        namespace_name=effective_namespace,
                        table_name=table_name,
                        source_file_id=str(file_record.id),
                        source_uri=file_record.uri,
                    )
                )
        return snapshots

    async def delete_file_entities(self, file_id: UUID | str) -> list[str]:
        connection = await self.ensure_internal_connection()
        source_links = await self._catalog_data_service.list_source_links_async(
            source_type="file",
            source_id=file_id,
        )
        if not source_links:
            return []

        entity_ids = {
            str(link.entity_id)
            for link in source_links
            if link.entity_id is not None and str(link.connection_id) == str(connection.id)
        }
        if not entity_ids:
            return []

        catalog = self._get_catalog(connection)
        deleted_entities: list[str] = []
        for entity_id in entity_ids:
            detail = await self._catalog_data_service.get_entity_detail_async(entity_id)
            if detail is None:
                continue
            namespace_name = detail.entity.namespace_name
            table_identifier = self._table_identifier(namespace_name, detail.entity.entity_name)
            if catalog.table_exists(table_identifier):
                self._purge_managed_table(catalog, table_identifier)
            deleted_entities.append(entity_id)
        return deleted_entities

    async def list_connection_snapshots(
        self, connection: CatalogConnection | None = None
    ) -> list[CatalogEntitySnapshot]:
        resolved_connection = connection or await self.ensure_internal_connection()
        catalog = self._get_catalog(resolved_connection)
        snapshots: list[CatalogEntitySnapshot] = []
        for namespace in catalog.list_namespaces(self._project_namespace_root()):
            if not namespace or namespace[0] != self._project_namespace_root()[0]:
                continue
            namespace_name = namespace[-1]
            for identifier in catalog.list_tables(namespace):
                table_name = identifier[-1]
                table = catalog.load_table(identifier)
                snapshots.append(
                    self._snapshot_from_table(
                        table=table,
                        namespace_name=namespace_name,
                        table_name=table_name,
                        source_file_id=None,
                        source_uri=table.location(),
                    )
                )
        return snapshots

    def _get_catalog(self, connection: CatalogConnection) -> Catalog:
        warehouse_path = connection.config.warehouse_path or get_project_storage_path(
            self.project_id, "lakehouse"
        )
        warehouse_uri = self._normalize_warehouse_uri(warehouse_path)
        return load_catalog(
            f"kontext_{self.project_id.replace('-', '_')}",
            type="sql",
            uri=get_project_database_url(),
            warehouse=warehouse_uri,
        )

    def _ensure_namespace(self, catalog: Catalog, namespace_name: str) -> None:
        catalog.create_namespace_if_not_exists(self._iceberg_namespace(namespace_name))

    def _project_namespace_root(self) -> tuple[str]:
        return (f"project_{self.project_id.replace('-', '_')}",)

    def _iceberg_namespace(self, namespace_name: str) -> tuple[str, str]:
        return (self._project_namespace_root()[0], namespace_name)

    def _table_identifier(self, namespace_name: str, table_name: str) -> tuple[str, str, str]:
        return (*self._iceberg_namespace(namespace_name), table_name)

    def _normalize_warehouse_uri(self, warehouse_path: str) -> str:
        if "://" in warehouse_path:
            return warehouse_path
        # A local warehouse is a directory on the host: keep it inside the
        # allowed roots before handing it to DuckDB/Iceberg.
        return ensure_within_allowed_roots(warehouse_path).as_uri()

    def _table_specs_for_file(
        self, file_path: Path, file_type: FileFormatType
    ) -> list[tuple[str, str | None]]:
        base_name = self._sanitize_identifier(file_path.stem)
        if file_type == FileFormatType.EXCEL:
            workbook = load_workbook(filename=file_path, read_only=True)
            try:
                return [
                    (
                        f"{base_name}_{self._sanitize_identifier(sheet_name)}",
                        sheet_name,
                    )
                    for sheet_name in workbook.sheetnames
                ]
            finally:
                workbook.close()
        return [(base_name, None)]

    def _sanitize_identifier(self, value: str) -> str:
        sanitized = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)
        if sanitized and sanitized[0].isdigit():
            sanitized = f"t_{sanitized}"
        return sanitized or "table"

    def _read_source_to_arrow(
        self,
        *,
        temp_path: Path,
        file_type: FileFormatType,
        sub_table_name: str | None,
    ):
        connection = duckdb.connect()
        try:
            if file_type == FileFormatType.EXCEL:
                self._ensure_duckdb_extension(connection, "excel")

            query = self._read_query_for_file_type(
                temp_path=temp_path,
                file_type=file_type,
                sub_table_name=sub_table_name,
            )
            return connection.sql(query).to_arrow_table()
        finally:
            connection.close()

    @staticmethod
    def _ensure_duckdb_extension(connection: duckdb.DuckDBPyConnection, extension: str) -> None:
        """Make sure *extension* is loaded on *connection*.

        ``INSTALL`` downloads the extension from the DuckDB extension
        repository, so it must not run on every read: it couples unrelated
        code paths to network availability and can stall for seconds on a call
        that has nothing to do with the extension. It is only attempted when
        the extension is not already installed locally, and a failure there is
        tolerated because extensions are cached in the extension directory and
        ``LOAD`` can still succeed for a pre-bundled extension.
        """
        try:
            installed = connection.execute(
                "SELECT installed FROM duckdb_extensions() WHERE extension_name = ?",
                [extension],
            ).fetchone()
        except duckdb.Error:
            installed = None

        if installed and installed[0]:
            connection.execute(f"LOAD {extension}")
            return

        try:
            connection.execute(f"INSTALL {extension}")
        except duckdb.Error:
            logger.warning(
                "Could not install DuckDB extension %s; attempting LOAD with the "
                "local extension directory",
                extension,
                exc_info=True,
            )
        connection.execute(f"LOAD {extension}")

    def _read_query_for_file_type(
        self,
        *,
        temp_path: Path,
        file_type: FileFormatType,
        sub_table_name: str | None,
    ) -> str:
        escaped_path = str(temp_path).replace("'", "''")
        if file_type == FileFormatType.CSV:
            return f"SELECT * FROM read_csv_auto('{escaped_path}')"
        if file_type == FileFormatType.TSV:
            return f"SELECT * FROM read_csv_auto('{escaped_path}', delim='\\t')"
        if file_type == FileFormatType.PARQUET:
            return f"SELECT * FROM read_parquet('{escaped_path}')"
        if file_type == FileFormatType.JSON:
            return f"SELECT * FROM read_json('{escaped_path}')"
        if file_type == FileFormatType.JSONL:
            return f"SELECT * FROM read_json('{escaped_path}', format='newline_delimited')"
        if file_type == FileFormatType.EXCEL:
            if sub_table_name:
                escaped_sheet = sub_table_name.replace("'", "''")
                return f"SELECT * FROM read_xlsx('{escaped_path}', sheet='{escaped_sheet}')"
            return f"SELECT * FROM read_xlsx('{escaped_path}')"
        raise ValueError(f"Unsupported file type for lakehouse ingest: {file_type}")

    def _write_arrow_table(
        self,
        *,
        catalog: Catalog,
        namespace_name: str,
        table_name: str,
        arrow_table,
        source_file_id: str,
        source_uri: str,
    ):
        identifier = self._table_identifier(namespace_name, table_name)
        iceberg_schema = assign_fresh_schema_ids(_pyarrow_to_schema_without_ids(arrow_table.schema))
        table_properties = {
            "format-version": "2",
            "schema.name-mapping.default": create_mapping_from_schema(
                iceberg_schema
            ).model_dump_json(),
        }
        snapshot_properties = {
            "kontext.project_id": self.project_id,
            "kontext.source_file_id": source_file_id,
            "kontext.source_uri": source_uri,
        }
        if catalog.table_exists(identifier):
            table = catalog.load_table(identifier)
            try:
                table.transaction().set_properties(table_properties).commit_transaction()
                table.overwrite(arrow_table, snapshot_properties=snapshot_properties)
            except Exception:
                logger.warning(
                    "Falling back to drop/create for %s due to overwrite failure",
                    ".".join(identifier),
                    exc_info=True,
                )
                self._purge_managed_table(catalog, identifier)
                table = catalog.create_table(
                    identifier,
                    schema=iceberg_schema,
                    properties=table_properties,
                )
                table.append(arrow_table, snapshot_properties=snapshot_properties)
            return table.refresh()

        table = catalog.create_table(
            identifier,
            schema=iceberg_schema,
            properties=table_properties,
        )
        table.append(arrow_table, snapshot_properties=snapshot_properties)
        return table.refresh()

    def _purge_managed_table(self, catalog: Catalog, identifier: tuple[str, str, str]) -> None:
        logger.info("Purging managed Iceberg table %s", ".".join(identifier))
        catalog.purge_table(identifier)

    def _snapshot_from_table(
        self,
        *,
        table,
        namespace_name: str,
        table_name: str,
        source_file_id: str | None,
        source_uri: str | None,
    ) -> CatalogEntitySnapshot:
        current_snapshot = table.current_snapshot()
        summary = getattr(current_snapshot, "summary", None) if current_snapshot else None
        summary_values = summary or {}
        source_file_id_value = source_file_id or summary_values.get("kontext.source_file_id")
        source_uri_value = summary_values.get("kontext.source_uri") or source_uri
        columns = [
            CatalogColumn(
                name=field.name,
                ordinal_position=index,
                data_type=str(field.field_type),
                nullable=not field.required,
                description=field.doc,
            )
            for index, field in enumerate(table.schema().fields)
        ]
        metadata_location = (
            table.metadata_location
            if not callable(table.metadata_location)
            else table.metadata_location()
        )
        return CatalogEntitySnapshot(
            namespace_name=namespace_name,
            entity_name=table_name,
            entity_type=CatalogEntityType.TABLE,
            description=f"Iceberg table {namespace_name}.{table_name}",
            row_count=int(summary_values.get("total-records", 0)) if summary else None,
            location=table.location(),
            metadata={
                "icebergNamespace": list(self._iceberg_namespace(namespace_name)),
                "icebergIdentifier": list(self._table_identifier(namespace_name, table_name)),
                "metadataLocation": metadata_location,
                "sourceUri": source_uri_value,
            },
            columns=columns,
            source_type="file" if source_file_id_value else None,
            source_id=source_file_id_value,
        )
