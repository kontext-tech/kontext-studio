"""Native live SQL execution engines for direct database pushdown."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.engine.reflection import Inspector

from kontext.common.catalog.connector_specs import (
    CatalogConnectorSpec,
    build_sqlalchemy_connection_url,
    filter_catalog_schema_names,
    get_catalog_connector_spec,
)
from kontext.common.protocols import IQuerySessionServiceProtocol
from kontext.common.pydantic import KontextBaseModel
from kontext.data import CatalogDataService
from kontext.schema import (
    CatalogConnection,
    ColumnModel,
    DataColumn,
    DataTable,
    SchemaInfo,
    TableDiscoveryModel,
    TableSchemaModel,
)


class LiveSqlSessionConfig(KontextBaseModel):
    """Configuration for direct live SQL engines."""

    project_id: str
    catalog_connection_id: str
    default_namespace: str | None = None
    default_entity_id: str | None = None
    session_id: str | None = None
    shadow: bool = False


class LiveSqlQueryEngine:
    """SQLAlchemy-backed query engine for native pushdown providers."""

    def __init__(
        self,
        config: LiveSqlSessionConfig,
        *,
        query_session_service: IQuerySessionServiceProtocol | None = None,
    ) -> None:
        self.config = config
        self._query_session_service = query_session_service
        self._catalog_data_service = CatalogDataService(config.project_id)
        self._engine: Engine | None = None
        self._connection: CatalogConnection | None = None
        self._secret_value: str | None = None
        self._spec: CatalogConnectorSpec | None = None
        self.logger = logging.getLogger(f"engine.live_sql.{config.catalog_connection_id}")

    async def connect(self) -> None:
        if self._engine is not None:
            return

        connection = await self._catalog_data_service.get_connection_async(
            self.config.catalog_connection_id
        )
        if connection is None:
            raise ValueError(f"Catalog connection {self.config.catalog_connection_id} not found")

        self._connection = connection
        self._spec = get_catalog_connector_spec(connection.provider_kind)
        self._secret_value = await self._catalog_data_service.get_connection_secret_async(
            connection.id or ""
        )
        self._engine = create_engine(
            build_sqlalchemy_connection_url(connection, self._secret_value),
            pool_pre_ping=True,
        )

    def _fetch_rows(
        self, sql: str, params: dict[str, Any], max_rows: int
    ) -> tuple[list[str], list[Any]]:
        """Execute *sql* and fetch at most ``max_rows + 1`` rows (blocking).

        Fetching one extra row lets the caller detect truncation without
        materializing the entire result set.
        """
        engine = self._require_engine()
        with engine.connect() as connection:
            result = connection.execute(text(sql), params)
            columns = [
                # `result` is a SQLAlchemy `Result`, not a mapping: iterating it
                # yields rows, so `result.keys()` (SIM118's "no-op" suggestion)
                # is required here to get column names.
                str(name)
                for name in result.keys()  # noqa: SIM118
            ]
            rows = result.fetchmany(max_rows + 1)
        return columns, list(rows)

    async def execute_query(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[RowMapping]:
        engine = self._require_engine()

        def _run() -> list[RowMapping]:
            with engine.connect() as connection:
                result = connection.execute(text(sql), params or {})
                return list(result.mappings().all())

        return await asyncio.to_thread(_run)

    async def fetch_data_table(
        self, sql: str, params: dict[str, Any] | None = None, max_rows: int = 1000
    ) -> DataTable:
        column_names, rows = await asyncio.to_thread(self._fetch_rows, sql, params or {}, max_rows)
        columns = [DataColumn(name=name, type="unknown", is_nullable=True) for name in column_names]
        has_more = len(rows) > max_rows
        if has_more:
            rows = rows[:max_rows]
            self.logger.info("Result truncated to %d of more rows for data table", max_rows)
        return DataTable(
            columns=columns,
            rows=[[self._to_json_value(value) for value in row] for row in rows],
            row_count=len(rows),
        )

    async def validate_sql(self, sql: str) -> tuple[bool, str | None]:
        engine = self._require_engine()

        def _run() -> tuple[bool, str | None]:
            connection = engine.connect()
            transaction = connection.begin()
            try:
                result = connection.execute(text(sql))
                if result.returns_rows:
                    result.fetchmany(1)
                transaction.rollback()
                return True, None
            except Exception as exc:
                if transaction.is_active:
                    transaction.rollback()
                return False, str(exc)
            finally:
                connection.close()

        return await asyncio.to_thread(_run)

    async def get_schema(self, schema_name: str | None = None) -> SchemaInfo | None:
        return await asyncio.to_thread(self._get_schema_sync, schema_name)

    def _get_schema_sync(self, schema_name: str | None = None) -> SchemaInfo | None:
        inspector = self._get_inspector()
        catalog_connection = self._require_connection()
        target_schema = schema_name or self._default_schema_name(inspector)
        if not target_schema:
            return None

        table_names = inspector.get_table_names(schema=target_schema)
        view_names = inspector.get_view_names(schema=target_schema)
        entity_names = sorted({*table_names, *view_names})
        catalog_name = catalog_connection.display_name

        return SchemaInfo(
            catalog_name=catalog_name,
            schema_name=target_schema,
            owner=target_schema,
            qualified_name=(f"{catalog_name}.{target_schema}" if catalog_name else target_schema),
            table_names=entity_names,
            table_count=len(entity_names),
        )

    async def discover_table(self, schema_name: str, table_name: str) -> TableDiscoveryModel | None:
        return await asyncio.to_thread(self._discover_table_sync, schema_name, table_name)

    def _discover_table_sync(self, schema_name: str, table_name: str) -> TableDiscoveryModel | None:
        inspector = self._get_inspector()
        catalog_connection = self._require_connection()
        catalog_spec = self._require_spec()
        try:
            columns = inspector.get_columns(table_name, schema=schema_name)
        except Exception:
            return None

        if not columns:
            return None

        return TableDiscoveryModel(
            engine_type=catalog_spec.query_engine_type,
            catalog_name=catalog_connection.display_name,
            schema_name=schema_name,
            table=TableSchemaModel(
                table_name=table_name,
                columns=[
                    ColumnModel(
                        name=str(column.get("name")),
                        physical_type=str(column.get("type"))
                        if column.get("type") is not None
                        else None,
                        nullable=bool(column.get("nullable", True)),
                        column_order=index,
                    )
                    for index, column in enumerate(columns)
                ],
            ),
        )

    async def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    def _require_engine(self) -> Engine:
        if self._engine is None:
            raise ValueError("Live SQL engine is not connected")
        self._require_connection()
        self._require_spec()
        return self._engine

    def _require_connection(self) -> CatalogConnection:
        if self._connection is None:
            raise ValueError("Live SQL engine is not connected")
        return self._connection

    def _require_spec(self) -> CatalogConnectorSpec:
        if self._spec is None:
            raise ValueError("Live SQL engine is not connected")
        return self._spec

    def _get_inspector(self) -> Inspector:
        return inspect(self._require_engine())

    def _default_schema_name(self, inspector: Inspector) -> str | None:
        if self.config.default_namespace:
            return self.config.default_namespace
        catalog_connection = self._require_connection()
        if catalog_connection.config.default_namespace:
            return catalog_connection.config.default_namespace
        schemas = self._list_schema_names(inspector)
        return schemas[0] if schemas else None

    def _list_schema_names(self, inspector: Inspector) -> list[str]:
        catalog_spec = self._require_spec()
        catalog_connection = self._require_connection()
        return filter_catalog_schema_names(
            catalog_spec,
            inspector.get_schema_names(),
            default_namespace=(
                self.config.default_namespace or catalog_connection.config.default_namespace
            ),
        )

    @staticmethod
    def _to_json_value(value: Any) -> Any:
        if value is None or isinstance(value, str | int | float | bool):
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)
