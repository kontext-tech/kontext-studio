"""Catalog provider contracts and implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

import duckdb
from sqlalchemy import create_engine, inspect, text

from kontext.common.catalog.connector_specs import (
    CatalogConnectorSpec,
    build_sqlalchemy_connection_url,
    filter_catalog_schema_names,
    get_catalog_location,
    list_catalog_connector_specs,
)
from kontext.common.utils.file_storage import get_project_storage_path
from kontext.common.utils.path_policy import ensure_within_allowed_roots
from kontext.data import CatalogDataService, CatalogEntitySnapshot
from kontext.schema import (
    CatalogColumn,
    CatalogConnection,
    CatalogConnectionAuthType,
    CatalogConnectionCapabilities,
    CatalogConnectionConfig,
    CatalogConnectionKind,
    CatalogConnectionRequest,
    CatalogConnectionValidationResult,
    CatalogEntityType,
    CatalogExecutionMode,
    CatalogProviderDefinition,
    CatalogSourceCategory,
    CatalogSourceKind,
    QueryEngineType,
)

from .lakehouse import LakehouseService


def _internal_capabilities() -> CatalogConnectionCapabilities:
    return CatalogConnectionCapabilities(
        supports_sync=True,
        supports_search=True,
        supports_query=True,
        supports_query_pushdown=False,
        supports_duckdb_federation=True,
        supports_materialization=True,
        supports_write=True,
    )


def _external_capabilities(
    *,
    supports_duckdb_federation: bool,
    supports_query_pushdown: bool,
) -> CatalogConnectionCapabilities:
    return CatalogConnectionCapabilities(
        supports_sync=True,
        supports_search=True,
        supports_query=True,
        supports_query_pushdown=supports_query_pushdown,
        supports_duckdb_federation=supports_duckdb_federation,
        supports_materialization=False,
        supports_write=False,
    )


def _unsupported_capabilities() -> CatalogConnectionCapabilities:
    return CatalogConnectionCapabilities(
        supports_sync=False,
        supports_search=False,
        supports_query=False,
        supports_query_pushdown=False,
        supports_duckdb_federation=False,
        supports_materialization=False,
        supports_write=False,
    )


ExternalProviderProfile = CatalogConnectorSpec


class CatalogProvider(ABC):
    """Provider contract for syncing catalog metadata."""

    provider_kind: CatalogSourceKind
    connection_kind: CatalogConnectionKind
    display_name: str
    source_category: CatalogSourceCategory
    auth_types: tuple[CatalogConnectionAuthType, ...]
    execution_modes: tuple[CatalogExecutionMode, ...]
    capabilities: CatalogConnectionCapabilities

    def definition(self) -> CatalogProviderDefinition:
        return CatalogProviderDefinition(
            provider_kind=self.provider_kind,
            connection_kind=self.connection_kind,
            display_name=self.display_name,
            source_category=self.source_category,
            auth_types=list(self.auth_types),
            execution_modes=list(self.execution_modes),
            capabilities=self.capabilities,
        )

    def default_request(self, *, project_id: str | None = None) -> CatalogConnectionRequest:
        raise NotImplementedError

    @abstractmethod
    async def validate(self, connection: CatalogConnection) -> CatalogConnectionValidationResult:
        """Validate a connection without mutating catalog snapshots."""

    @abstractmethod
    async def sync(self, connection: CatalogConnection) -> list[CatalogEntitySnapshot]:
        """Return a normalized metadata snapshot for a connection."""


class InternalIcebergCatalogProvider(CatalogProvider):
    """Default internal provider backed by the project Iceberg catalog."""

    provider_kind = CatalogSourceKind.ICEBERGINTERNAL
    connection_kind = CatalogConnectionKind.INTERNAL
    display_name = "Internal Iceberg"
    source_category = CatalogSourceCategory.LAKEHOUSE
    auth_types = (CatalogConnectionAuthType.NONE,)
    execution_modes = (
        CatalogExecutionMode.DUCKDBFEDERATED,
        CatalogExecutionMode.MATERIALIZED,
    )
    capabilities = _internal_capabilities()

    def __init__(self, project_id: str) -> None:
        self.project_id = str(project_id)
        self.lakehouse_service = LakehouseService(self.project_id)

    def default_request(self, *, project_id: str | None = None) -> CatalogConnectionRequest:
        resolved_project_id = project_id or self.project_id
        return CatalogConnectionRequest(
            provider_kind=self.provider_kind,
            connection_kind=self.connection_kind,
            display_name="Default Lakehouse",
            description="Internal project-managed catalog metadata.",
            enabled=True,
            source_category=self.source_category,
            auth_type=CatalogConnectionAuthType.NONE,
            execution_mode=CatalogExecutionMode.DUCKDBFEDERATED,
            config=CatalogConnectionConfig(
                warehouse_path=get_project_storage_path(resolved_project_id, "lakehouse"),
                default_namespace="bronze",
            ),
            capabilities=self.capabilities,
        )

    async def validate(self, connection: CatalogConnection) -> CatalogConnectionValidationResult:
        return CatalogConnectionValidationResult(
            connection_id=connection.id or "",
            status="succeeded",
            validated_at=datetime.now(UTC),
            message="Internal lakehouse connection is managed by the platform.",
        )

    async def sync(self, connection: CatalogConnection) -> list[CatalogEntitySnapshot]:
        return await self.lakehouse_service.list_connection_snapshots(connection)


class SqlAlchemyExternalCatalogProvider(CatalogProvider):
    """SQLAlchemy-based provider for external relational catalogs."""

    def __init__(self, project_id: str, profile: ExternalProviderProfile) -> None:
        self.project_id = str(project_id)
        self.provider_kind = profile.provider_kind
        self.connection_kind = CatalogConnectionKind.EXTERNAL
        self.display_name = profile.display_name
        self.source_category = profile.source_category
        self.auth_types = profile.auth_types
        self.execution_modes = profile.execution_modes
        self.capabilities = _external_capabilities(
            supports_duckdb_federation=profile.supports_duckdb_federation,
            supports_query_pushdown=profile.supports_native_pushdown,
        )
        self._profile = profile
        self._catalog_data_service = CatalogDataService(self.project_id)

    def default_request(self, *, project_id: str | None = None) -> CatalogConnectionRequest:
        return CatalogConnectionRequest(
            provider_kind=self.provider_kind,
            connection_kind=self.connection_kind,
            display_name=self.display_name,
            source_category=self.source_category,
            auth_type=self.auth_types[0] if self.auth_types else None,
            execution_mode=self.execution_modes[0] if self.execution_modes else None,
            config=CatalogConnectionConfig.model_validate(dict(self._profile.default_config)),
            capabilities=self.capabilities,
        )

    async def validate(self, connection: CatalogConnection) -> CatalogConnectionValidationResult:
        secret_value = await self._catalog_data_service.get_connection_secret_async(
            connection.id or ""
        )
        engine = create_engine(
            build_sqlalchemy_connection_url(connection, secret_value),
            pool_pre_ping=True,
        )
        try:
            with engine.connect() as db_conn:
                db_conn.execute(text(self._profile.validation_query))
            return CatalogConnectionValidationResult(
                connection_id=connection.id or "",
                status="succeeded",
                validated_at=datetime.now(UTC),
                message=(
                    f"{self.display_name} connection validated successfully via "
                    f"{self._profile.sqlalchemy_driver}."
                ),
            )
        except Exception as exc:
            return CatalogConnectionValidationResult(
                connection_id=connection.id or "",
                status="failed",
                validated_at=datetime.now(UTC),
                error_message=str(exc),
            )
        finally:
            engine.dispose()

    async def sync(self, connection: CatalogConnection) -> list[CatalogEntitySnapshot]:
        secret_value = await self._catalog_data_service.get_connection_secret_async(
            connection.id or ""
        )
        engine = create_engine(
            build_sqlalchemy_connection_url(connection, secret_value),
            pool_pre_ping=True,
        )
        try:
            inspector = inspect(engine)
            schemas = self._list_schemas(inspector, connection)
            snapshots: list[CatalogEntitySnapshot] = []
            for schema_name in schemas:
                for entity_name in inspector.get_table_names(schema=schema_name):
                    snapshots.append(
                        self._build_snapshot(
                            inspector,
                            connection=connection,
                            schema_name=schema_name,
                            entity_name=entity_name,
                            entity_type=CatalogEntityType.TABLE,
                        )
                    )
                for entity_name in inspector.get_view_names(schema=schema_name):
                    snapshots.append(
                        self._build_snapshot(
                            inspector,
                            connection=connection,
                            schema_name=schema_name,
                            entity_name=entity_name,
                            entity_type=CatalogEntityType.VIEW,
                        )
                    )
            return snapshots
        finally:
            engine.dispose()

    def _build_url(self, connection: CatalogConnection, secret_value: str | None) -> str:
        return build_sqlalchemy_connection_url(connection, secret_value)

    def _list_schemas(self, inspector, connection: CatalogConnection) -> list[str]:
        config = connection.config
        if self.provider_kind == CatalogSourceKind.SQLITEEXTERNAL:
            return [config.default_namespace or self._profile.default_namespace or "main"]
        return filter_catalog_schema_names(
            self._profile,
            inspector.get_schema_names(),
            default_namespace=config.default_namespace,
        )

    def _build_snapshot(
        self,
        inspector,
        *,
        connection: CatalogConnection,
        schema_name: str,
        entity_name: str,
        entity_type: CatalogEntityType,
    ) -> CatalogEntitySnapshot:
        raw_columns = inspector.get_columns(entity_name, schema=schema_name)
        columns = [
            CatalogColumn(
                name=str(column.get("name")),
                ordinal_position=index,
                data_type=str(column.get("type")) if column.get("type") else None,
                nullable=bool(column.get("nullable", True)),
                description=None,
                metadata={"default": column.get("default")},
            )
            for index, column in enumerate(raw_columns)
        ]
        return CatalogEntitySnapshot(
            namespace_name=schema_name or self._profile.default_namespace or "default",
            entity_name=entity_name,
            entity_type=entity_type,
            description=None,
            row_count=None,
            location=get_catalog_location(
                connection,
                schema_name=schema_name,
                entity_name=entity_name,
            ),
            metadata={},
            columns=columns,
        )


class DuckDbExternalCatalogProvider(CatalogProvider):
    """DuckDB-file provider for local/external DuckDB catalogs."""

    def __init__(self, project_id: str, profile: ExternalProviderProfile) -> None:
        self.project_id = str(project_id)
        self.provider_kind = profile.provider_kind
        self.connection_kind = CatalogConnectionKind.EXTERNAL
        self.display_name = profile.display_name
        self.source_category = profile.source_category
        self.auth_types = profile.auth_types
        self.execution_modes = profile.execution_modes
        self.capabilities = _external_capabilities(
            supports_duckdb_federation=True,
            supports_query_pushdown=False,
        )
        self._profile = profile

    def default_request(self, *, project_id: str | None = None) -> CatalogConnectionRequest:
        return CatalogConnectionRequest(
            provider_kind=self.provider_kind,
            connection_kind=self.connection_kind,
            display_name=self.display_name,
            source_category=self.source_category,
            auth_type=self.auth_types[0] if self.auth_types else None,
            execution_mode=self.execution_modes[0] if self.execution_modes else None,
            config=CatalogConnectionConfig.model_validate(dict(self._profile.default_config)),
            capabilities=self.capabilities,
        )

    async def validate(self, connection: CatalogConnection) -> CatalogConnectionValidationResult:
        try:
            if not connection.config.database_path:
                raise ValueError("DuckDB catalog connections require config.databasePath")
            db_path = ensure_within_allowed_roots(connection.config.database_path)
            db = duckdb.connect(str(db_path), read_only=True)
            try:
                db.execute("SELECT 1")
            finally:
                db.close()
            return CatalogConnectionValidationResult(
                connection_id=connection.id or "",
                status="succeeded",
                validated_at=datetime.now(UTC),
                message="DuckDB connection validated successfully.",
            )
        except Exception as exc:
            return CatalogConnectionValidationResult(
                connection_id=connection.id or "",
                status="failed",
                validated_at=datetime.now(UTC),
                error_message=str(exc),
            )

    async def sync(self, connection: CatalogConnection) -> list[CatalogEntitySnapshot]:
        if not connection.config.database_path:
            raise ValueError("DuckDB catalog connections require config.databasePath")
        db_path = ensure_within_allowed_roots(connection.config.database_path)
        db = duckdb.connect(str(db_path), read_only=True)
        try:
            schemas = self._list_schemas(db, connection)
            snapshots: list[CatalogEntitySnapshot] = []
            for schema_name in schemas:
                entities = db.execute(
                    """
                    SELECT table_name, table_type
                    FROM information_schema.tables
                    WHERE table_schema = ?
                    ORDER BY table_name
                    """,
                    [schema_name],
                ).fetchall()
                for entity_name, table_type in entities:
                    entity_type = (
                        CatalogEntityType.VIEW
                        if str(table_type).upper() == "VIEW"
                        else CatalogEntityType.TABLE
                    )
                    columns = db.execute(
                        """
                        SELECT column_name, ordinal_position, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = ? AND table_name = ?
                        ORDER BY ordinal_position
                        """,
                        [schema_name, entity_name],
                    ).fetchall()
                    snapshots.append(
                        CatalogEntitySnapshot(
                            namespace_name=schema_name,
                            entity_name=str(entity_name),
                            entity_type=entity_type,
                            description=None,
                            row_count=None,
                            location=get_catalog_location(
                                connection,
                                schema_name=schema_name,
                                entity_name=str(entity_name),
                            ),
                            metadata={},
                            columns=[
                                CatalogColumn(
                                    name=str(column_name),
                                    ordinal_position=int(ordinal_position)
                                    if ordinal_position is not None
                                    else index,
                                    data_type=str(data_type) if data_type else None,
                                    nullable=str(is_nullable).upper() == "YES",
                                    description=None,
                                    metadata={},
                                )
                                for index, (
                                    column_name,
                                    ordinal_position,
                                    data_type,
                                    is_nullable,
                                ) in enumerate(columns)
                            ],
                        )
                    )
            return snapshots
        finally:
            db.close()

    def _list_schemas(
        self, db: duckdb.DuckDBPyConnection, connection: CatalogConnection
    ) -> list[str]:
        rows = db.execute(
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog')
            ORDER BY schema_name
            """
        ).fetchall()
        return filter_catalog_schema_names(
            self._profile,
            [str(row[0]) for row in rows],
            default_namespace=connection.config.default_namespace,
        )


class UnsupportedExternalCatalogProvider(CatalogProvider):
    """Hidden registry entry for connectors not implemented in this runtime."""

    connection_kind = CatalogConnectionKind.EXTERNAL

    def __init__(self, project_id: str, profile: ExternalProviderProfile) -> None:
        self.project_id = str(project_id)
        self.provider_kind = profile.provider_kind
        self.display_name = profile.display_name
        self.source_category = profile.source_category
        self.auth_types = profile.auth_types
        self.execution_modes = profile.execution_modes
        self.capabilities = _unsupported_capabilities()
        self._profile = profile

    def default_request(self, *, project_id: str | None = None) -> CatalogConnectionRequest:
        return CatalogConnectionRequest(
            provider_kind=self.provider_kind,
            connection_kind=self.connection_kind,
            display_name=self.display_name,
            source_category=self.source_category,
            auth_type=self.auth_types[0] if self.auth_types else None,
            execution_mode=self.execution_modes[0] if self.execution_modes else None,
            config=CatalogConnectionConfig.model_validate(dict(self._profile.default_config)),
            capabilities=self.capabilities,
        )

    async def validate(self, connection: CatalogConnection) -> CatalogConnectionValidationResult:
        return CatalogConnectionValidationResult(
            connection_id=connection.id or "",
            status="failed",
            validated_at=datetime.now(UTC),
            error_message=f"{self.display_name} validation is not implemented in this runtime.",
        )

    async def sync(self, connection: CatalogConnection) -> list[CatalogEntitySnapshot]:
        raise NotImplementedError(f"{self.display_name} sync is not implemented in this runtime.")


SUPPORTED_EXTERNAL_PROFILES = tuple(
    spec
    for spec in list_catalog_connector_specs(include_internal=False)
    if spec.provider_kind
    not in {
        CatalogSourceKind.BIGQUERYEXTERNAL,
        CatalogSourceKind.HTTPAPIEXTERNAL,
        CatalogSourceKind.SNOWFLAKEEXTERNAL,
    }
)

UNSUPPORTED_EXTERNAL_PROFILES = tuple(
    CatalogConnectorSpec(
        provider_kind=provider_kind,
        display_name=display_name,
        connection_kind=CatalogConnectionKind.EXTERNAL,
        source_category=source_category,
        auth_types=auth_types,
        execution_modes=execution_modes,
        default_config=default_config,
        query_engine_type=query_engine_type,
    )
    for provider_kind, display_name, source_category, auth_types, execution_modes, default_config, query_engine_type in (
        (
            CatalogSourceKind.SNOWFLAKEEXTERNAL,
            "Snowflake",
            CatalogSourceCategory.SQL,
            (CatalogConnectionAuthType.SECRETREF,),
            (CatalogExecutionMode.NATIVEPUSHDOWN,),
            {
                "account": "",
                "warehouse": "",
                "databaseName": "",
                "role": "",
                "defaultNamespace": "PUBLIC",
            },
            QueryEngineType.SNOWFLAKE,
        ),
        (
            CatalogSourceKind.BIGQUERYEXTERNAL,
            "BigQuery",
            CatalogSourceCategory.SQL,
            (CatalogConnectionAuthType.SERVICEACCOUNT,),
            (CatalogExecutionMode.NATIVEPUSHDOWN,),
            {"project": "", "location": "us", "defaultNamespace": ""},
            QueryEngineType.DUCKDB,
        ),
        (
            CatalogSourceKind.HTTPAPIEXTERNAL,
            "HTTP API",
            CatalogSourceCategory.API,
            (
                CatalogConnectionAuthType.APIKEY,
                CatalogConnectionAuthType.OAUTHCLIENTCREDENTIALS,
            ),
            (CatalogExecutionMode.MATERIALIZED,),
            {"options": {"baseUrl": ""}},
            QueryEngineType.DUCKDB,
        ),
    )
)


class CatalogProviderRegistry:
    """Factory/registry for catalog providers."""

    def __init__(self, project_id: str) -> None:
        self.project_id = str(project_id)
        self._providers: dict[CatalogSourceKind, CatalogProvider] = {
            CatalogSourceKind.ICEBERGINTERNAL: InternalIcebergCatalogProvider(self.project_id),
        }
        for profile in SUPPORTED_EXTERNAL_PROFILES:
            if profile.provider_kind == CatalogSourceKind.DUCKDBEXTERNAL:
                provider: CatalogProvider = DuckDbExternalCatalogProvider(
                    self.project_id,
                    profile,
                )
            else:
                provider = SqlAlchemyExternalCatalogProvider(self.project_id, profile)
            self._providers[profile.provider_kind] = provider
        for profile in UNSUPPORTED_EXTERNAL_PROFILES:
            self._providers[profile.provider_kind] = UnsupportedExternalCatalogProvider(
                self.project_id,
                profile,
            )

    def get(self, provider_kind: CatalogSourceKind) -> CatalogProvider:
        return self._providers[provider_kind]

    def list_definitions(self) -> list[CatalogProviderDefinition]:
        return [
            provider.definition()
            for provider in self._providers.values()
            if provider.capabilities.supports_sync
        ]
