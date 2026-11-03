"""Shared catalog connector metadata and connection helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import quote, urlencode

from kontext.common.utils.path_policy import ensure_within_allowed_roots
from kontext.schema import (
    CatalogConnection,
    CatalogConnectionAuthType,
    CatalogConnectionKind,
    CatalogExecutionMode,
    CatalogSourceCategory,
    CatalogSourceKind,
    QueryEngineType,
)


@dataclass(frozen=True)
class CatalogConnectorSpec:
    """Normalized provider metadata shared across catalog/query services."""

    provider_kind: CatalogSourceKind
    display_name: str
    connection_kind: CatalogConnectionKind
    source_category: CatalogSourceCategory
    auth_types: tuple[CatalogConnectionAuthType, ...]
    execution_modes: tuple[CatalogExecutionMode, ...]
    default_config: Mapping[str, object]
    query_engine_type: QueryEngineType
    sqlalchemy_driver: str | None = None
    default_port: int | None = None
    validation_query: str = "SELECT 1"
    duckdb_extension: str | None = None
    duckdb_attach_type: str | None = None
    schema_exclusions: frozenset[str] = frozenset()
    default_namespace: str | None = None

    @property
    def supports_duckdb_federation(self) -> bool:
        return CatalogExecutionMode.DUCKDBFEDERATED in self.execution_modes

    @property
    def supports_native_pushdown(self) -> bool:
        return CatalogExecutionMode.NATIVEPUSHDOWN in self.execution_modes


_POSTGRES_SYSTEM_SCHEMAS = frozenset({"information_schema", "pg_catalog"})
_MYSQL_SYSTEM_SCHEMAS = frozenset({"information_schema", "mysql", "performance_schema", "sys"})
_SQLSERVER_SYSTEM_SCHEMAS = frozenset({"information_schema", "sys"})
_ORACLE_SYSTEM_SCHEMAS = frozenset(
    {
        "ANONYMOUS",
        "APPQOSSYS",
        "AUDSYS",
        "CTXSYS",
        "DBSNMP",
        "DIP",
        "GSMADMIN_INTERNAL",
        "LBACSYS",
        "MDSYS",
        "OJVMSYS",
        "OLAPSYS",
        "OUTLN",
        "SYS",
        "SYSTEM",
        "WMSYS",
        "XDB",
    }
)
_TERADATA_SYSTEM_SCHEMAS = frozenset({"dbc", "sysadmin", "sys_calendar"})


CATALOG_CONNECTOR_SPECS = MappingProxyType(
    {
        CatalogSourceKind.ICEBERGINTERNAL: CatalogConnectorSpec(
            provider_kind=CatalogSourceKind.ICEBERGINTERNAL,
            display_name="Internal Iceberg",
            connection_kind=CatalogConnectionKind.INTERNAL,
            source_category=CatalogSourceCategory.LAKEHOUSE,
            auth_types=(CatalogConnectionAuthType.NONE,),
            execution_modes=(
                CatalogExecutionMode.DUCKDBFEDERATED,
                CatalogExecutionMode.MATERIALIZED,
            ),
            default_config=MappingProxyType(
                {
                    "defaultNamespace": "bronze",
                }
            ),
            query_engine_type=QueryEngineType.DUCKDB,
            default_namespace="bronze",
        ),
        CatalogSourceKind.DUCKDBEXTERNAL: CatalogConnectorSpec(
            provider_kind=CatalogSourceKind.DUCKDBEXTERNAL,
            display_name="DuckDB",
            connection_kind=CatalogConnectionKind.EXTERNAL,
            source_category=CatalogSourceCategory.SQL,
            auth_types=(CatalogConnectionAuthType.NONE,),
            execution_modes=(CatalogExecutionMode.DUCKDBFEDERATED,),
            default_config=MappingProxyType({"databasePath": "", "defaultNamespace": "main"}),
            query_engine_type=QueryEngineType.DUCKDB,
            duckdb_attach_type="duckdb",
            default_namespace="main",
        ),
        CatalogSourceKind.MYSQLEXTERNAL: CatalogConnectorSpec(
            provider_kind=CatalogSourceKind.MYSQLEXTERNAL,
            display_name="MySQL",
            connection_kind=CatalogConnectionKind.EXTERNAL,
            source_category=CatalogSourceCategory.SQL,
            auth_types=(CatalogConnectionAuthType.SECRETREF,),
            execution_modes=(CatalogExecutionMode.DUCKDBFEDERATED,),
            default_config=MappingProxyType(
                {
                    "host": "localhost",
                    "port": 3306,
                    "databaseName": "mysql",
                    "username": "root",
                    "defaultNamespace": "default",
                }
            ),
            query_engine_type=QueryEngineType.DUCKDB,
            sqlalchemy_driver="mysql+pymysql",
            default_port=3306,
            duckdb_extension="mysql",
            duckdb_attach_type="mysql",
            schema_exclusions=_MYSQL_SYSTEM_SCHEMAS,
            default_namespace="default",
        ),
        CatalogSourceKind.ORACLEEXTERNAL: CatalogConnectorSpec(
            provider_kind=CatalogSourceKind.ORACLEEXTERNAL,
            display_name="Oracle",
            connection_kind=CatalogConnectionKind.EXTERNAL,
            source_category=CatalogSourceCategory.SQL,
            auth_types=(CatalogConnectionAuthType.SECRETREF,),
            execution_modes=(CatalogExecutionMode.NATIVEPUSHDOWN,),
            default_config=MappingProxyType(
                {
                    "host": "localhost",
                    "port": 1521,
                    "username": "system",
                    "serviceName": "FREEPDB1",
                    "defaultNamespace": "SYSTEM",
                }
            ),
            query_engine_type=QueryEngineType.ORACLE,
            sqlalchemy_driver="oracle+oracledb",
            default_port=1521,
            schema_exclusions=_ORACLE_SYSTEM_SCHEMAS,
            default_namespace="SYSTEM",
        ),
        CatalogSourceKind.POSTGRESQLEXTERNAL: CatalogConnectorSpec(
            provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL,
            display_name="PostgreSQL",
            connection_kind=CatalogConnectionKind.EXTERNAL,
            source_category=CatalogSourceCategory.SQL,
            auth_types=(CatalogConnectionAuthType.SECRETREF,),
            execution_modes=(CatalogExecutionMode.DUCKDBFEDERATED,),
            default_config=MappingProxyType(
                {
                    "host": "localhost",
                    "port": 5432,
                    "databaseName": "postgres",
                    "username": "postgres",
                    "defaultNamespace": "public",
                }
            ),
            query_engine_type=QueryEngineType.DUCKDB,
            sqlalchemy_driver="postgresql+psycopg",
            default_port=5432,
            duckdb_extension="postgres",
            duckdb_attach_type="postgres",
            schema_exclusions=_POSTGRES_SYSTEM_SCHEMAS,
            default_namespace="public",
        ),
        CatalogSourceKind.SQLSERVEREXTERNAL: CatalogConnectorSpec(
            provider_kind=CatalogSourceKind.SQLSERVEREXTERNAL,
            display_name="SQL Server",
            connection_kind=CatalogConnectionKind.EXTERNAL,
            source_category=CatalogSourceCategory.SQL,
            auth_types=(CatalogConnectionAuthType.SECRETREF,),
            execution_modes=(CatalogExecutionMode.NATIVEPUSHDOWN,),
            default_config=MappingProxyType(
                {
                    "host": "localhost",
                    "port": 1433,
                    "databaseName": "master",
                    "username": "sa",
                    "instanceName": "",
                    "defaultNamespace": "dbo",
                    "options": {
                        "driver": "ODBC Driver 18 for SQL Server",
                        "encrypt": "yes",
                        "trustServerCertificate": "yes",
                    },
                }
            ),
            query_engine_type=QueryEngineType.SQLSERVER,
            sqlalchemy_driver="mssql+pyodbc",
            default_port=1433,
            schema_exclusions=_SQLSERVER_SYSTEM_SCHEMAS,
            default_namespace="dbo",
        ),
        CatalogSourceKind.TERADATAEXTERNAL: CatalogConnectorSpec(
            provider_kind=CatalogSourceKind.TERADATAEXTERNAL,
            display_name="Teradata",
            connection_kind=CatalogConnectionKind.EXTERNAL,
            source_category=CatalogSourceCategory.SQL,
            auth_types=(CatalogConnectionAuthType.SECRETREF,),
            execution_modes=(CatalogExecutionMode.NATIVEPUSHDOWN,),
            default_config=MappingProxyType(
                {
                    "host": "localhost",
                    "username": "dbc",
                    "databaseName": "dbc",
                    "defaultNamespace": "dbc",
                    "options": {"logmech": "TD2"},
                }
            ),
            query_engine_type=QueryEngineType.TERADATA,
            sqlalchemy_driver="teradata+teradatasql",
            default_port=1025,
            schema_exclusions=_TERADATA_SYSTEM_SCHEMAS,
            default_namespace="dbc",
        ),
        CatalogSourceKind.SQLITEEXTERNAL: CatalogConnectorSpec(
            provider_kind=CatalogSourceKind.SQLITEEXTERNAL,
            display_name="SQLite",
            connection_kind=CatalogConnectionKind.EXTERNAL,
            source_category=CatalogSourceCategory.SQL,
            auth_types=(CatalogConnectionAuthType.NONE,),
            execution_modes=(CatalogExecutionMode.DUCKDBFEDERATED,),
            default_config=MappingProxyType({"databasePath": "", "defaultNamespace": "main"}),
            query_engine_type=QueryEngineType.DUCKDB,
            sqlalchemy_driver="sqlite",
            duckdb_extension="sqlite",
            duckdb_attach_type="sqlite",
            default_namespace="main",
        ),
    }
)


def list_catalog_connector_specs(
    *, include_internal: bool = True
) -> tuple[CatalogConnectorSpec, ...]:
    specs = tuple(CATALOG_CONNECTOR_SPECS.values())
    if include_internal:
        return specs
    return tuple(spec for spec in specs if spec.connection_kind == CatalogConnectionKind.EXTERNAL)


def get_catalog_connector_spec(
    provider_kind: CatalogSourceKind | str,
) -> CatalogConnectorSpec:
    normalized_kind = normalize_catalog_source_kind(provider_kind)
    return CATALOG_CONNECTOR_SPECS[normalized_kind]


def normalize_catalog_source_kind(
    provider_kind: CatalogSourceKind | str,
) -> CatalogSourceKind:
    if isinstance(provider_kind, CatalogSourceKind):
        return provider_kind
    return CatalogSourceKind(str(provider_kind))


def resolve_query_engine_type_for_connection(
    connection: CatalogConnection | None,
) -> QueryEngineType:
    if connection is None:
        return QueryEngineType.DUCKDB
    spec = get_catalog_connector_spec(connection.provider_kind)
    return spec.query_engine_type


def build_sqlalchemy_connection_url(
    connection: CatalogConnection, secret_value: str | None = None
) -> str:
    spec = get_catalog_connector_spec(connection.provider_kind)
    config = connection.config
    username = quote(config.username or "", safe="")
    password = quote(secret_value or "", safe="")

    if connection.provider_kind == CatalogSourceKind.POSTGRESQLEXTERNAL:
        _require_host_and_database(connection)
        return (
            f"{spec.sqlalchemy_driver}://{username}:{password}@{config.host}:"
            f"{config.port or spec.default_port}/{quote(config.database_name or '', safe='')}"
        )

    if connection.provider_kind == CatalogSourceKind.MYSQLEXTERNAL:
        _require_host_and_database(connection)
        return (
            f"{spec.sqlalchemy_driver}://{username}:{password}@{config.host}:"
            f"{config.port or spec.default_port}/{quote(config.database_name or '', safe='')}"
        )

    if connection.provider_kind == CatalogSourceKind.SQLSERVEREXTERNAL:
        _require_host_and_database(connection)
        options = dict(config.options or {})
        driver = str(options.pop("driver", "ODBC Driver 18 for SQL Server"))
        server = str(config.host)
        if config.instance_name:
            server = f"{server}\\{config.instance_name}"
        elif config.port:
            server = f"{server},{config.port}"
        odbc_pairs = [
            ("DRIVER", f"{{{driver}}}"),
            ("SERVER", server),
            ("DATABASE", str(config.database_name)),
        ]
        if config.username:
            odbc_pairs.append(("UID", config.username))
        if secret_value:
            odbc_pairs.append(("PWD", secret_value))
        for key, value in options.items():
            if value not in (None, ""):
                odbc_pairs.append((str(key), str(value)))
        odbc_str = ";".join(f"{key}={value}" for key, value in odbc_pairs)
        return f"{spec.sqlalchemy_driver}:///?odbc_connect={quote(odbc_str, safe='')}"

    if connection.provider_kind == CatalogSourceKind.ORACLEEXTERNAL:
        if not config.host:
            raise ValueError("Oracle catalog connections require host")
        service_name = config.service_name or config.database_name
        if not service_name:
            raise ValueError(
                "Oracle catalog connections require config.serviceName or databaseName"
            )
        base = (
            f"{spec.sqlalchemy_driver}://{username}:{password}@{config.host}:"
            f"{config.port or spec.default_port}/"
        )
        return f"{base}?{urlencode({'service_name': service_name})}"

    if connection.provider_kind == CatalogSourceKind.TERADATAEXTERNAL:
        _require_host_and_database(connection)
        query = dict(config.options or {})
        if config.port:
            query.setdefault("dbs_port", str(config.port))
        query_string = f"?{urlencode(query)}" if query else ""
        return (
            f"{spec.sqlalchemy_driver}://{username}:{password}@{config.host}/"
            f"{quote(config.database_name or '', safe='')}{query_string}"
        )

    if connection.provider_kind == CatalogSourceKind.SQLITEEXTERNAL:
        if not config.database_path:
            raise ValueError("SQLite catalog connections require config.databasePath")
        # SQLite is a local file. Confine it to the allowed roots so a crafted
        # connection can't point the server at an arbitrary file on the host.
        resolved = ensure_within_allowed_roots(config.database_path)
        return f"sqlite:///{resolved}"

    raise ValueError(f"SQLAlchemy connection URLs are not supported for {connection.provider_kind}")


def filter_catalog_schema_names(
    spec: CatalogConnectorSpec,
    schema_names: Iterable[str],
    *,
    default_namespace: str | None = None,
) -> list[str]:
    normalized_default = (default_namespace or spec.default_namespace or "").strip()
    seen: set[str] = set()
    filtered = [
        schema_name
        for schema_name in schema_names
        if schema_name
        and schema_name.lower() not in {item.lower() for item in spec.schema_exclusions}
    ]
    ordered: list[str] = []
    if normalized_default:
        for schema_name in filtered:
            if schema_name.lower() == normalized_default.lower():
                seen.add(schema_name.lower())
                ordered.append(schema_name)
                break
    for schema_name in filtered:
        key = schema_name.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(schema_name)
    return ordered


def get_catalog_location(
    connection: CatalogConnection,
    *,
    schema_name: str,
    entity_name: str,
) -> str:
    config = connection.config
    if connection.provider_kind in {
        CatalogSourceKind.SQLITEEXTERNAL,
        CatalogSourceKind.DUCKDBEXTERNAL,
    }:
        return f"{config.database_path}#{schema_name}.{entity_name}"
    return (
        f"{config.host}:{config.port or get_catalog_connector_spec(connection.provider_kind).default_port}/"
        f"{config.database_name or config.service_name or ''}#{schema_name}.{entity_name}"
    )


def _require_host_and_database(connection: CatalogConnection) -> None:
    if not connection.config.host or not connection.config.database_name:
        display_name = get_catalog_connector_spec(connection.provider_kind).display_name
        raise ValueError(f"{display_name} catalog connections require host and databaseName")
