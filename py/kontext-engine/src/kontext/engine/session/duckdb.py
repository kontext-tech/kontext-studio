"""
DuckDB Query Session Module for Kontext Data Lake

This module provides functionality to create and manage persistent DuckDB query sessions
that are initialized with catalog context. It loads normalized catalog entities,
uses local filesystem storage, and sets up Iceberg-backed views for
cross-namespace querying.

Schema Support:
- Each namespace gets its own schema named after the catalog namespace
- Multiple namespaces can be queried within the same session using qualified table names
- A default schema can be set for unqualified queries
- Cross-namespace joins are supported using schema-qualified table names
- Schema isolation ensures entity separation and prevents naming conflicts

Sessions can be persistent (stored in file share) or in-memory. Persistent sessions
are stored in a project-specific directory structure:
{file_storage_path}/{project_id}/sessions/{session_id}.db

Session naming convention:
- With default namespace: {project_id}_{default_namespace}_{session_id}
- Project-only: {project_id}_{session_id}

Architecture:
This module is designed to run in job worker processes where session initialization
is handled asynchronously. All external data access is performed via HTTP client
services to the API and Kontext host contract, eliminating direct database
access.
"""

import asyncio
import functools
import logging
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from kontext.common.constants import DatabaseEnvVars, QueryConstants
from kontext.common.protocols import (
    IQuerySessionServiceProtocol,
    QueryRuntimeProviderProtocol,
)
from kontext.common.pydantic import KontextBaseModel
from kontext.common.query.session_storage import get_session_database_path
from kontext.common.utils.path_policy import ensure_within_allowed_roots
from kontext.data import CatalogDataService
from kontext.engine.storage.duckdb_storage import DuckDBStorageManager
from kontext.schema import (
    CatalogConnection,
    CatalogEntityDetail,
    CatalogExecutionMode,
    CatalogSourceKind,
    ColumnModel,
    DataColumn,
    DataTable,
    QueryEngineType,
    QuerySessionModel,
    QuerySessionStatus,
    SchemaInfo,
    TableDiscoveryModel,
    TableSchemaModel,
)
from kontext.storage import get_storage_config

from .catalog_loader import CatalogLoader
from .duckdb_utils import (
    configure_duckdb_engine,
    get_duckdb_config,
)
from .schema_manager import SchemaManager


def get_duckdb_extensions_path() -> str | None:
    """
    Get the path to the DuckDB extensions directory.

    Uses the KONTEXT_EXTENSIONS_DIR environment variable set by function_app.py.

    Returns:
        Path to the extensions directory, or None if not found
    """
    extensions_path = os.environ.get(DatabaseEnvVars.EXTENSIONS_DIR)
    if extensions_path and os.path.exists(extensions_path):
        return os.path.abspath(extensions_path)

    return None


_PLAN_OPERATOR_PATTERN = re.compile(r"[│|]\s*([A-Z][A-Z_0-9]{2,})\s*[│|]")
# DuckDB >= 2.0 renders operator names as title-case headings between box
# corners (``╭─ Create Table ─╮``, ``╭─ Batch Insert ──────╮``). Only the
# heading rows carry ``╭─``; attribute rows and legacy 1.x plans do not.
_PLAN_TITLE_PATTERN = re.compile(r"╭─\s*([A-Za-z0-9 _]+?)\s*─")


def _to_json_value(value: Any) -> Any:
    """Coerce a DuckDB result value into a JSON-serializable value."""
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _explain_plan_operators(connection: duckdb.DuckDBPyConnection, sql: str) -> set[str]:
    """Return the physical-plan operators DuckDB binds/plans *sql* to.

    ``EXPLAIN`` binds and plans a statement without executing it, so this is a
    side-effect-free way to inspect a statement before running it.

    Both plan renderings are handled: DuckDB <= 1.x prints ALL_CAPS operator
    tokens inside table borders (``CREATE_TABLE``, ``BATCH_COPY_TO_FILE``),
    while DuckDB >= 2.0 prints title-case headings (``Create Table``,
    ``Batch Insert``) that are normalized into the same token space.
    """
    row = connection.execute(f"EXPLAIN {sql}").fetchone()
    plan = str(row[-1]) if row else ""
    operators = set(_PLAN_OPERATOR_PATTERN.findall(plan))
    operators |= {
        title.strip().upper().replace(" ", "_") for title in _PLAN_TITLE_PATTERN.findall(plan)
    }
    return operators


def _matched_write_operators(operators: set[str]) -> set[str]:
    """Return which write operators occur in *operators* (word-boundary aware).

    Plan tokens are often prefixed variants of a write operator: DuckDB 1.x
    emits ``BATCH_INSERT`` for an INSERT and ``CREATE_TABLE_AS`` for a
    CREATE-TABLE-AS-SELECT, and exact set intersection misses both. Matching
    on underscore-delimited boundaries keeps reads like ``SEQ_SCAN`` from
    matching while catching every prefixed write operator.
    """
    matched: set[str] = set()
    for operator in operators:
        bounded = f"_{operator}_"
        for write_operator in QueryConstants.DUCKDB_WRITE_PLAN_OPERATORS:
            if f"_{write_operator}_" in bounded:
                matched.add(write_operator)
    return matched


class SessionConfig(KontextBaseModel):
    """Configuration for DuckDB query session"""

    project_id: str
    catalog_connection_id: str | None = None
    default_namespace: str | None = None
    default_entity_id: str | None = None
    user_id: str | None = (
        None  # User who created/owns this session (can be null for system operations)
    )
    session_id: str | None = None  # Optional - will be generated if not provided
    persistent: bool = True  # Whether to use persistent storage or in-memory
    session_name: str | None = None  # Optional explicit session name
    shadow: bool = False  # Validation only mode (no data files)
    #: Catalog revision the caller expects this session to materialize. When it
    #: differs from the stored revision, the engine reconciles catalog views
    #: (drops stale ones) before re-creating them.
    catalog_revision: str | None = None

    def model_post_init(self, __context):
        if not self.session_id:
            self.session_id = str(uuid.uuid4())

        # Shadow sessions must be in-memory
        if self.shadow:
            self.persistent = False

    @property
    def effective_session_name(self) -> str:
        # If no session name is provided, default to a truncated 8-char session ID.
        # This keeps paths short and predictable.
        if self.session_name:
            return self.session_name

        # session_id is guaranteed to be set in model_post_init,
        # but we use a fallback for type safety
        sid = str(self.session_id) if self.session_id else "unknown"
        return f"Session {sid[:8]}"


class DuckDBQueryEngine:
    """
    DuckDB Query Engine for Kontext Data Lake

    Uses the API client services for all external data access.
    Designed to run in job worker processes with async session initialization.
    """

    def __init__(
        self,
        config: SessionConfig,
        *,
        runtime_provider: QueryRuntimeProviderProtocol | None = None,
        query_session_service: IQuerySessionServiceProtocol | None = None,
    ):
        """
        Initialize DuckDB query engine with service dependencies.

        Args:
            config: Session configuration
            runtime_provider: Runtime provider for required dependencies
            query_session_service: Optional query session service override
        """
        self.config = config

        if runtime_provider is not None:
            try:
                if query_session_service is None:
                    query_session_service = runtime_provider.get_query_session_service()
            except NotImplementedError as exc:
                raise RuntimeError("Query session service is not supported by provider") from exc
            if query_session_service is None:
                raise RuntimeError("Query session service is not available")
        else:
            if query_session_service is None:
                raise RuntimeError(
                    "DuckDBQueryEngine requires a runtime_provider or explicit "
                    "query_session_service."
                )

        self._query_session_service = query_session_service
        self._runtime_provider = runtime_provider

        self.logger = logging.getLogger(f"engine.duckdb.{config.effective_session_name}")
        # Serializes access to the single-writer DuckDB connection. The lock is
        # created lazily so the engine can be constructed outside an event loop.
        self._execution_lock: asyncio.Lock | None = None
        # Blocking calls currently running in executor threads (see
        # ``_run_blocking``). Disposal drains them briefly before closing the
        # connection, because a query abandoned by a timeout keeps using the
        # connection from its orphaned thread.
        self._inflight_blocking: set[asyncio.Future[Any]] = set()
        self.connection: duckdb.DuckDBPyConnection | None = None
        self.active_connection: CatalogConnection | None = None
        self.catalog_entities: dict[str, list[CatalogEntityDetail]] = {}
        self.schema_mapping: dict[str, str] = {}  # schema_name -> namespace_name
        self.created_at: datetime | None = None
        self.is_initialized = False
        self.database_path: str | None = None
        self.current_schema = None  # Track current active schema
        self.total_objects_loaded = 0
        self.catalog_revision: str | None = config.catalog_revision

        # Initialize storage configuration and secret manager
        self._storage_config = get_storage_config()
        self._storage_manager = DuckDBStorageManager(self._storage_config)
        self._secret_name: str | None = None  # Will be set when secret is created

        self.catalog_loader = CatalogLoader(
            project_id=self.config.project_id,
            logger=self.logger,
        )
        self._catalog_data_service = CatalogDataService(self.config.project_id)
        self.schema_manager = None  # Will be set after connection is created

    async def _run_blocking(self, fn, *args, **kwargs):
        """Run a *blocking* DuckDB call off the event loop.

        DuckDB is synchronous; running it inline would stall the server event
        loop. ``asyncio.to_thread`` keeps the loop responsive.

        The executor future is tracked so :meth:`dispose` can wait for calls
        that outlive their awaitable (a cancelled waiter cannot stop the
        thread once the call is in flight).
        """
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))
        self._inflight_blocking.add(future)
        future.add_done_callback(self._inflight_blocking.discard)
        return await future

    async def interrupt(self) -> None:
        """Best-effort stop for an in-flight query.

        ``DuckDBPyConnection.interrupt`` is documented as safe to call from
        another thread while a query runs, which is exactly the state after a
        timeout cancellation: the query still runs in its executor thread and
        must be made to finish before the connection is closed.
        """
        connection = self.connection
        if connection is None:
            return
        try:
            connection.interrupt()
        except Exception as exc:  # pragma: no cover - duckdb-internal failure
            self.logger.debug("Interrupting in-flight DuckDB query failed: %s", exc)

    async def dispose(self) -> None:
        """Release the engine connection without deleting the persisted session.

        Waits briefly for in-flight blocking calls to unwind (typically right
        after an :meth:`interrupt`) so the connection is never closed while an
        executor thread is still using it.
        """
        pending = {future for future in self._inflight_blocking if not future.done()}
        if pending:
            try:
                async with asyncio.timeout(5.0):
                    await asyncio.gather(*pending, return_exceptions=True)
            except TimeoutError:
                self.logger.warning(
                    "Disposing DuckDB session with %d in-flight call(s) still running; "
                    "closing the connection anyway.",
                    len(pending),
                )
        self._inflight_blocking.clear()
        self.close_session()

    def _get_execution_lock(self) -> asyncio.Lock:
        if self._execution_lock is None:
            self._execution_lock = asyncio.Lock()
        return self._execution_lock

    def _get_database_path(self) -> str | None:
        """
        Get the database file path for persistent sessions

        For persistent sessions, the database file is stored in:
        {file_storage_path}/{project_id}/sessions/{session_id}.db

        Returns:
            Path to the database file or None for in-memory sessions
        """
        if not self.config.session_id:
            return None

        return get_session_database_path(
            self.config.project_id, self.config.session_id, self.config.persistent
        )

    async def create_session(self, skip_registration: bool = False) -> None:
        """
        Create and initialize the DuckDB query session

        Args:
            skip_registration: If True, skip registering the session in the
                             database. Use this when the session already exists
                             and you only want to initialize the DuckDB connection.

        Steps:
        1. Register the session in the database (unless skip_registration=True)
        2. Load catalog metadata from the project metastore
        3. Create DuckDB connection with session name
        4. Set up local storage access
        5. Create Iceberg-backed views for catalog entities
        """
        try:
            session_type = "shadow" if self.config.shadow else "live"
            session_action = "Re-initializing" if skip_registration else "Creating"
            self.logger.info(
                f"{session_action} {session_type} DuckDB session: "
                f"{self.config.effective_session_name}"
            )
            self.created_at = datetime.now(UTC)

            # Set the database path upfront (used by both registration and connection)
            self.database_path = self._get_database_path()
            self.logger.info("Using database path: %s", self.database_path or "in-memory")

            # Step 1: Register the session in the database (unless skipped or shadow)
            if not skip_registration and not self.config.shadow:
                await self._register_session()
                # Update database path in case session ID changed during registration
                if self.config.persistent:
                    self.database_path = self._get_database_path()
                    self.logger.info("Database path updated to: %s", self.database_path)

            # Step 1b: For a reused session, recall the catalog revision it was
            # built against so step 3 can reconcile stale views when needed.
            await self._load_recorded_catalog_revision()

            # Step 2: Load project catalog scope
            await self._load_project_catalog()

            # Step 3: Create DuckDB connection (blocking; off the event loop)
            await self._run_blocking(self._create_duckdb_connection)

            # Step 4: Set up cloud storage access (skip for shadow)
            if not self.config.shadow:
                await self._setup_storage_access()

            # Step 5: Create external tables (or empty for shadow)
            await self._create_external_tables()

            # Step 6: Record the catalog revision this session materialized.
            # Best-effort: a failure here only means reuse falls back to the
            # deletion-flag invalidation path, never a broken session.
            if not self.config.shadow:
                await self._stamp_catalog_revision()

            self.is_initialized = True
            action_completed = "re-initialized" if skip_registration else "initialized"
            # Use logger interpolation to avoid long literal f-strings
            self.logger.info(
                "Session %s %s successfully with %d schemas and %d total objects",
                self.config.effective_session_name,
                action_completed,
                len(self.schema_mapping),
                self.total_objects_loaded,
            )

        except Exception as e:
            self.logger.error(f"Failed to create session {self.config.effective_session_name}: {e}")
            if self.connection:
                self.connection.close()
            raise

    async def _register_session(self) -> None:
        """Register the query session via the API"""
        try:
            # Create session via API
            session_id, _ = await self._query_session_service.create_query_session(
                project_id=self.config.project_id,
                catalog_connection_id=self.config.catalog_connection_id,
                default_namespace=self.config.default_namespace,
                default_entity_id=self.config.default_entity_id,
                session_name=self.config.session_name
                or f"Session {str(self.config.session_id)[:8]}",
                persistent=self.config.persistent,
            )

            # Update the session ID to match the returned session ID
            self.config.session_id = session_id
            self.logger.info(f"Session registered with ID: {session_id}")

        except Exception as e:
            self.logger.error(f"Failed to register session: {e}")
            raise

    async def _load_project_catalog(self) -> None:
        """Load normalized catalog metadata for Iceberg-backed session bootstrap."""
        self.logger.info("Loading project catalog for project %s", self.config.project_id)
        if not self.config.catalog_connection_id:
            catalog_service = (
                self._runtime_provider.get_catalog_service()
                if self._runtime_provider is not None
                else None
            )
            if catalog_service is None:
                raise RuntimeError(
                    "A catalog service is required to resolve the internal lakehouse "
                    "connection. Provide a runtime_provider that exposes get_catalog_service()."
                )
            connection = await catalog_service.ensure_default_internal_connection()
            self.config.catalog_connection_id = str(connection.id) if connection.id else None
            if not self.config.default_namespace:
                self.config.default_namespace = connection.config.default_namespace or "bronze"

        result = await self.catalog_loader.load_project_catalog(
            catalog_connection_id=self.config.catalog_connection_id,
            default_namespace=self.config.default_namespace,
        )
        self.active_connection = result.connection
        self.catalog_entities = result.entities_by_namespace
        self.schema_mapping = {
            namespace_name: namespace_name for namespace_name in result.entities_by_namespace
        }
        if (
            self.config.default_namespace
            and self.config.default_namespace not in self.schema_mapping
        ):
            self.schema_mapping[self.config.default_namespace] = self.config.default_namespace

        self.total_objects_loaded = result.total_entities
        self.current_schema = self.config.default_namespace

        if self.config.default_entity_id:
            for namespace_name, entities in self.catalog_entities.items():
                if any(
                    str(entity.entity.id) == str(self.config.default_entity_id)
                    for entity in entities
                ):
                    self.current_schema = namespace_name
                    break

        if not self.current_schema and self.schema_mapping:
            self.current_schema = next(iter(self.schema_mapping.keys()))

        if self.current_schema:
            self.logger.info("Set default schema to: %s", self.current_schema)
        else:
            self.logger.info("No default schema set - using global namespace")

    async def _load_recorded_catalog_revision(self) -> None:
        """Recall the catalog revision a reused session was materialized with.

        When ``skip_registration`` is set the engine is re-initializing an
        existing persisted session; the revision it was built against lives on
        the session row, so read it back before reconciling views.
        """
        if self.config.shadow or not self.config.session_id:
            return
        try:
            session = await self._query_session_service.get_query_session(
                str(self.config.session_id), self.config.project_id
            )
        except Exception as exc:
            self.logger.debug("Failed to load recorded catalog revision: %s", exc)
            return
        if session is not None and getattr(session, "catalog_revision", None):
            self.catalog_revision = session.catalog_revision

    async def _stamp_catalog_revision(self) -> None:
        """Persist the catalog revision this session materialized.

        Best-effort: a missing revision only degrades reuse to rebuilding the
        session, so callers treat failure as non-fatal.
        """
        if not self.config.session_id or self.config.shadow:
            return
        revision = self.active_connection.catalog_revision if self.active_connection else None
        if not revision:
            return
        try:
            await self._query_session_service.set_catalog_revision(
                str(self.config.session_id), revision
            )
        except Exception as exc:
            self.logger.debug("Failed to persist catalog revision: %s", exc)

    def _get_qualified_table_name(self, table_name: str, schema_name: str | None = None) -> str:
        """
        Generate fully qualified table name with schema

        Args:
            table_name: The base table name
            schema_name: Optional specific schema name, uses current schema if None

        Returns:
            Qualified table name with schema if available
        """
        schema = schema_name or self.current_schema
        if schema:
            return f'"{schema}"."{table_name}"'
        else:
            return f'"{table_name}"'

    def _install_storage_extension(self) -> None:
        """Install and verify storage extension for DuckDB based on provider"""
        if not self.connection:
            raise ValueError("DuckDB connection not initialized")

        # Use the unified storage module for extension setup
        extensions_path = get_duckdb_extensions_path()
        self._storage_manager.setup_extension(self.connection, extensions_path)

    def _install_iceberg_extension(self) -> None:
        """Install and load DuckDB Iceberg support when available."""
        if not self.connection:
            raise ValueError("DuckDB connection not initialized")
        try:
            self.connection.execute("INSTALL iceberg")
            self.connection.execute("LOAD iceberg")
            self.logger.info("DuckDB Iceberg extension loaded")
        except Exception as exc:
            self.logger.warning("Failed to load DuckDB Iceberg extension: %s", exc)

    def _create_duckdb_connection(self) -> None:
        """Create DuckDB connection with optional persistence based on configuration"""
        # Get standard DuckDB configuration (extension_directory, home_directory)
        duckdb_config = get_duckdb_config()

        # Database path should already be set in create_session()
        if self.database_path:
            # Persistent session using file share storage
            if Path(self.database_path).exists():
                self.logger.info(f"Reopening existing persistent session at {self.database_path}")
            else:
                self.logger.info(f"Creating new persistent session at {self.database_path}")
            self.connection = duckdb.connect(self.database_path, config=duckdb_config)
        else:
            # In-memory session
            self.connection = duckdb.connect(":memory:", config=duckdb_config)
            self.logger.info("Created in-memory DuckDB session")

        # Apply common configuration (threads, etc.)
        configure_duckdb_engine(self.connection)

        # Install storage extension (none for local filesystem)
        self._install_storage_extension()
        self._install_iceberg_extension()

        # Reconcile a stale catalog materialization: when the catalog revision
        # recorded when the session was built no longer matches the current
        # catalog, drop the persisted user schemas so entities removed or
        # changed upstream cannot linger as stale views. Views are recreated
        # immediately afterwards from the freshly loaded catalog.
        expected_revision = (
            self.active_connection.catalog_revision if self.active_connection else None
        )
        if expected_revision and expected_revision != self.catalog_revision:
            self.logger.info(
                "Catalog revision changed (%s -> %s); reconciling DuckDB views",
                self.catalog_revision,
                expected_revision,
            )
            self._drop_user_schemas()
        if expected_revision:
            self.catalog_revision = expected_revision

        # Initialize shared schema manager
        self.schema_manager = SchemaManager(self.connection, self.logger)

        # Create schemas using shared utility
        self.schema_manager.create_schemas(self.schema_mapping)

        # Set default schema using shared utility
        self.schema_manager.set_default_schema(self.current_schema)

        suffix = " - persistent" if self.database_path else " - in-memory"
        # Use interpolation to keep line lengths short
        self.logger.info(
            "DuckDB connection created for session %s%s",
            self.config.effective_session_name,
            suffix,
        )

    async def _setup_storage_access(self) -> None:
        """
        Set up local storage access in DuckDB.

        Uses the unified storage module; local filesystem storage requires no
        provider-specific secrets.
        """
        if not self.connection:
            raise ValueError("DuckDB connection not initialized")

        # Create project-scoped secret using the unified storage module
        self._secret_name = self._storage_manager.create_secret(
            self.connection, self.config.project_id
        )

        if self._secret_name:
            self.logger.info(
                "Storage secret '%s' created for provider '%s'",
                self._secret_name,
                self._storage_config.provider.value,
            )
        else:
            self.logger.info(
                "No storage secret required for provider '%s'",
                self._storage_config.provider.value,
            )

    async def _create_external_tables(self) -> None:
        """Create Iceberg-backed views for all catalog entities across schemas."""
        if not self.connection:
            raise ValueError("DuckDB connection not initialized")
        if self._should_use_duckdb_federation():
            await self._attach_federated_catalog()
            await self._create_federated_views()
            return
        await self._create_catalog_views()

    def _should_use_duckdb_federation(self) -> bool:
        if self.active_connection is None:
            return False
        provider_kind = self.active_connection.provider_kind
        execution_mode = self.active_connection.execution_mode
        if execution_mode and execution_mode != CatalogExecutionMode.DUCKDBFEDERATED:
            return False
        return provider_kind in {
            CatalogSourceKind.DUCKDBEXTERNAL,
            CatalogSourceKind.MYSQLEXTERNAL,
            CatalogSourceKind.POSTGRESQLEXTERNAL,
            CatalogSourceKind.SQLITEEXTERNAL,
        }

    def _get_federated_alias(self) -> str:
        connection_id = (
            str(self.active_connection.id).replace("-", "_")
            if self.active_connection and self.active_connection.id
            else "external_catalog"
        )
        return f"ext_{connection_id}"

    def _install_database_extension(self, extension_name: str) -> None:
        if not self.connection:
            raise ValueError("DuckDB connection not initialized")
        self.connection.execute(f"INSTALL {extension_name}")
        self.connection.execute(f"LOAD {extension_name}")

    def _escape_sql_string(self, value: str) -> str:
        return value.replace("'", "''")

    def _quote_identifier(self, value: str) -> str:
        return f'"{value.replace(chr(34), chr(34) * 2)}"'

    def _federated_secret_name(self) -> str:
        connection_id = (
            str(self.active_connection.id).replace("-", "_")
            if self.active_connection and self.active_connection.id
            else "external_catalog"
        )
        return f"kontext_ext_{connection_id}"

    async def _detach_federated_catalog(self) -> None:
        """Detach the federated catalog and drop its secret if attached.

        Attachments are session-scoped in DuckDB, but the same engine object can
        re-initialize (e.g. a validation pass), so attach is made idempotent.
        """
        if not self.connection:
            return
        alias = self._get_federated_alias()
        try:
            attached = {
                str(row[0])
                for row in self.connection.execute(
                    "SELECT database_name FROM duckdb_databases()"
                ).fetchall()
            }
        except Exception:
            attached = set()
        if alias in attached:
            try:
                self.connection.execute(f"DROP DATABASE IF EXISTS {self._quote_identifier(alias)}")
            except Exception as exc:
                self.logger.debug("Failed to detach federated catalog %s: %s", alias, exc)
        try:
            self.connection.execute(
                f"DROP SECRET IF EXISTS {self._quote_identifier(self._federated_secret_name())}"
            )
        except Exception as exc:
            self.logger.debug("Failed to drop federated secret: %s", exc)

    async def _attach_federated_catalog(self) -> None:
        if not self.connection or not self.active_connection:
            raise ValueError("DuckDB connection not initialized")
        provider_kind = self.active_connection.provider_kind
        alias = self._quote_identifier(self._get_federated_alias())
        secret_value = await self._catalog_data_service.get_connection_secret_async(
            self.active_connection.id or ""
        )

        # Make re-initialization idempotent before (re)attaching.
        await self._detach_federated_catalog()

        if provider_kind == CatalogSourceKind.DUCKDBEXTERNAL:
            if not self.active_connection.config.database_path:
                raise ValueError("DuckDB federated connections require config.databasePath")
            db_file = ensure_within_allowed_roots(self.active_connection.config.database_path)
            db_path = self._escape_sql_string(str(db_file))
            sql = f"ATTACH '{db_path}' AS {alias} (READ_ONLY)"
        elif provider_kind == CatalogSourceKind.SQLITEEXTERNAL:
            self._install_database_extension("sqlite")
            if not self.active_connection.config.database_path:
                raise ValueError("SQLite federated connections require config.databasePath")
            db_file = ensure_within_allowed_roots(self.active_connection.config.database_path)
            db_path = self._escape_sql_string(str(db_file))
            sql = f"ATTACH '{db_path}' AS {alias} (TYPE sqlite)"
        elif provider_kind == CatalogSourceKind.POSTGRESQLEXTERNAL:
            self._install_database_extension("postgres")
            config = self.active_connection.config
            if not config.host or not config.database_name:
                raise ValueError("PostgreSQL federated connections require host and databaseName")
            secret_name = self._quote_identifier(self._federated_secret_name())
            secret_parts = [
                "TYPE postgres",
                f"HOST '{self._escape_sql_string(config.host)}'",
                f"PORT {int(config.port or 5432)}",
                f"DATABASE '{self._escape_sql_string(config.database_name)}'",
            ]
            if config.username:
                secret_parts.append(f"USER '{self._escape_sql_string(config.username)}'")
            if secret_value:
                secret_parts.append(f"PASSWORD '{self._escape_sql_string(secret_value)}'")
            await self._run_blocking(
                self.connection.execute,
                f"CREATE OR REPLACE SECRET {secret_name} ({', '.join(secret_parts)})",
            )
            sql = f"ATTACH '' AS {alias} (TYPE postgres, SECRET {secret_name})"
        elif provider_kind == CatalogSourceKind.MYSQLEXTERNAL:
            self._install_database_extension("mysql")
            config = self.active_connection.config
            if not config.host or not config.database_name:
                raise ValueError("MySQL federated connections require host and databaseName")
            secret_name = self._quote_identifier(self._federated_secret_name())
            secret_parts = [
                "TYPE mysql",
                f"HOST '{self._escape_sql_string(config.host)}'",
                f"PORT {int(config.port or 3306)}",
                f"DATABASE '{self._escape_sql_string(config.database_name)}'",
            ]
            if config.username:
                secret_parts.append(f"USER '{self._escape_sql_string(config.username)}'")
            if secret_value:
                secret_parts.append(f"PASSWORD '{self._escape_sql_string(secret_value)}'")
            await self._run_blocking(
                self.connection.execute,
                f"CREATE OR REPLACE SECRET {secret_name} ({', '.join(secret_parts)})",
            )
            sql = f"ATTACH '' AS {alias} (TYPE mysql, SECRET {secret_name})"
        else:
            raise ValueError(f"Unsupported DuckDB federation provider: {provider_kind}")

        self.logger.info("Attaching federated catalog using provider %s", provider_kind)
        async with self._get_execution_lock():
            await self._run_blocking(self.connection.execute, sql)

    def _drop_user_schemas(self) -> None:
        """Drop every non-system schema so stale views are removed on rebuild.

        DuckDB persists views in the session database; without this, a table
        removed from the catalog would keep a stale ``iceberg_scan`` view
        pointing at purged metadata. System schemas are preserved.
        """
        if not self.connection:
            return
        system_schemas = {"information_schema", "pg_catalog", "main", "temp", "system"}
        try:
            schemas = [
                str(row[0])
                for row in self.connection.execute(
                    "SELECT schema_name FROM duckdb_schemas()"
                ).fetchall()
            ]
        except Exception as exc:
            self.logger.warning("Failed to list DuckDB schemas for reconciliation: %s", exc)
            return
        for schema in schemas:
            if schema in system_schemas or schema.startswith("pg_"):
                continue
            try:
                self.connection.execute(
                    f"DROP SCHEMA IF EXISTS {self._quote_identifier(schema)} CASCADE"
                )
            except Exception as exc:
                self.logger.warning("Failed to drop stale schema %s: %s", schema, exc)

    async def _create_federated_views(self) -> None:
        if not self.connection or not self.active_connection:
            raise ValueError("DuckDB connection not initialized")

        alias = self._quote_identifier(self._get_federated_alias())
        successful_views = 0
        failed_views = 0
        for namespace_name, entities in self.catalog_entities.items():
            for detail in entities:
                if self.config.default_entity_id and str(detail.entity.id) != str(
                    self.config.default_entity_id
                ):
                    continue
                schema_name = self._quote_identifier(namespace_name)
                entity_name = self._quote_identifier(detail.entity.entity_name)
                sql = (
                    f"CREATE OR REPLACE VIEW {schema_name}.{entity_name} AS "
                    f"SELECT * FROM {alias}.{schema_name}.{entity_name}"
                )
                try:
                    async with self._get_execution_lock():
                        await self._run_blocking(self.connection.execute, sql)
                    successful_views += 1
                except Exception as exc:
                    failed_views += 1
                    self.logger.error(
                        "Failed to register federated view %s.%s: %s",
                        namespace_name,
                        detail.entity.entity_name,
                        exc,
                    )
        self.logger.info(
            "Federated view creation completed: %d successful, %d failed",
            successful_views,
            failed_views,
        )

    async def _create_catalog_views(self) -> None:
        """Create schema-scoped Iceberg views from normalized catalog metadata."""
        if not self.connection:
            raise ValueError("DuckDB connection not initialized")

        successful_views = 0
        failed_views = 0
        for namespace_name, entities in self.catalog_entities.items():
            self.logger.info(
                "Processing %d Iceberg entities in schema '%s'",
                len(entities),
                namespace_name,
            )
            for detail in entities:
                if self.config.default_entity_id and str(detail.entity.id) != str(
                    self.config.default_entity_id
                ):
                    continue

                metadata_location = str(
                    (detail.entity.metadata or {}).get("metadataLocation") or ""
                )
                if not metadata_location:
                    failed_views += 1
                    self.logger.warning(
                        "Skipping catalog entity %s.%s because metadataLocation is missing",
                        namespace_name,
                        detail.entity.entity_name,
                    )
                    continue

                escaped_metadata_location = metadata_location.replace("'", "''")
                escaped_schema_name = namespace_name.replace('"', '""')
                escaped_entity_name = detail.entity.entity_name.replace('"', '""')
                sql = (
                    f'CREATE OR REPLACE VIEW "{escaped_schema_name}"."{escaped_entity_name}" AS '
                    f"SELECT * FROM iceberg_scan('{escaped_metadata_location}')"
                )
                try:
                    async with self._get_execution_lock():
                        await self._run_blocking(self.connection.execute, sql)
                    successful_views += 1
                except Exception as exc:
                    failed_views += 1
                    self.logger.error(
                        "Failed to register Iceberg view %s.%s: %s",
                        namespace_name,
                        detail.entity.entity_name,
                        exc,
                    )

        self.logger.info(
            "Catalog view creation completed: %d successful, %d failed",
            successful_views,
            failed_views,
        )

    def session_exists(self) -> bool:
        """Check if the session database file exists (for persistent sessions)"""
        return bool(
            self.config.persistent and self.database_path and os.path.exists(self.database_path)
        )

    def get_session_file_size(self) -> int | None:
        """Get the size of the session database file in bytes"""
        if self.database_path and os.path.exists(self.database_path):
            try:
                return os.path.getsize(self.database_path)
            except OSError:
                return None
        return None

    async def execute_query(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> duckdb.DuckDBPyRelation:
        """
        Execute a SQL query against the session

        Args:
            sql: SQL query to execute
            params: Optional query parameters

        Returns:
            duckdb.DuckDBPyRelation:
                Query result as a DuckDB relation with type information

        Raises:
            ValueError: If session is not initialized
            Exception: If query execution fails
        """
        if not self.is_initialized or not self.connection:
            raise ValueError("Session is not initialized")

        try:
            self.logger.info(f"Executing query: {sql[:100]}...")
            if self.current_schema:
                self.logger.debug(f"Using default schema: {self.current_schema}")
            # Use sql() method to get a relation object with full type information.
            # Serialize access: DuckDB connections are not safe for concurrent
            # use, and the call is blocking so it must run off the event loop.
            async with self._get_execution_lock():
                relation = await self._run_blocking(self.connection.sql, sql, params=params)
            self.logger.info(
                f"Query executed successfully, returned relation with "
                f"{len(relation.columns)} columns"
            )
            return relation

        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            raise

    async def connect(self) -> None:
        """Initialize the DuckDB connection (implementing QueryExecutionEngine)."""
        # Use re-initialization if session_id is already set
        await self.create_session(skip_registration=bool(self.config.session_id))

    async def validate_sql(self, sql: str) -> tuple[bool, str | None]:
        """
        Validate SQL without executing it (implementing QueryExecutionEngine).

        Uses ``EXPLAIN`` to bind and plan the statement, which surfaces syntax,
        binder, and catalog errors without running the query. Statements whose
        plan contains a write/mutation operator are rejected so validation can
        never alter session or external state.
        """
        if not self.is_initialized or not self.connection:
            raise ValueError("Session is not initialized")

        try:
            async with self._get_execution_lock():
                operators = await self._run_blocking(_explain_plan_operators, self.connection, sql)
        except Exception as e:
            return False, str(e)

        blocked = _matched_write_operators(operators)
        if blocked:
            blocked = ", ".join(sorted(blocked))
            return False, f"Validation only permits read-only statements (found: {blocked})."
        return True, None

    async def get_schema(self, schema_name: str | None = None) -> SchemaInfo | None:
        """Get schema information (implementing QueryExecutionEngine)."""
        if schema_name:
            if not self.schema_manager:
                raise ValueError("Session is not initialized")
            return self.schema_manager.get_schema_info(schema_name)
        return self.get_schema_info()

    async def discover_table(self, schema_name: str, table_name: str) -> TableDiscoveryModel | None:
        """Discover granular table metadata."""
        if not self.is_initialized or not self.connection:
            return None

        # Check existence and get columns
        try:
            query = (
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_schema = ? "
                "AND table_name = ? "
                "ORDER BY ordinal_position"
            )
            connection = self.connection
            async with self._get_execution_lock():
                cols_res = await self._run_blocking(
                    lambda: connection.execute(query, [schema_name, table_name]).fetchall()
                )

            if not cols_res:
                return None

            columns = []
            for c_name, c_type, c_null in cols_res:
                columns.append(
                    ColumnModel(
                        name=str(c_name),
                        physical_type=str(c_type),
                        nullable=(c_null == "YES"),
                    )
                )

            table_schema = TableSchemaModel(table_name=table_name, columns=columns)

            return TableDiscoveryModel(
                engine_type=QueryEngineType.DUCKDB,
                catalog_name="default",
                schema_name=schema_name,
                table=table_schema,
            )
        except Exception as e:
            self.logger.warning(f"Failed to discover table {schema_name}.{table_name}: {e}")
            return None

    async def fetch_data_table(
        self, sql: str, params: dict[str, Any] | None = None, max_rows: int = 1000
    ) -> DataTable:
        """
        Execute a SQL query and return the result as a standardized DataTable.

        The fetch is bounded *in the query plan* via ``LIMIT max_rows + 1`` so
        large result sets are never fully materialized in memory.
        """
        if not self.is_initialized or not self.connection:
            raise ValueError("Session is not initialized")

        # Fetch one extra row to detect truncation without scanning everything.
        async with self._get_execution_lock():
            relation = await self._run_blocking(self.connection.sql, sql, params=params)
            try:
                column_names = relation.columns
                column_types = relation.types

                if not column_names:
                    # For non-SELECT statements (DDL, DML) that don't return columns
                    return DataTable(columns=[], rows=[], row_count=0)

                columns = [
                    DataColumn(name=str(name), type=str(duckdb_type), is_nullable=True)
                    for name, duckdb_type in zip(column_names, column_types, strict=True)
                ]

                bounded = relation.limit(max_rows + 1)
                try:
                    rows = await self._run_blocking(bounded.fetchall)
                finally:
                    close = getattr(bounded, "close", None)
                    if callable(close):
                        close()
            finally:
                close = getattr(relation, "close", None)
                if callable(close):
                    close()

        has_more = len(rows) > max_rows
        if has_more:
            rows = rows[:max_rows]
            self.logger.info("Result truncated to %d of more rows for data table", max_rows)

        json_serializable_rows = [[_to_json_value(value) for value in row] for row in rows]

        return DataTable(
            columns=columns,
            rows=json_serializable_rows,
            row_count=len(json_serializable_rows),
        )

    def get_schema_info(self) -> SchemaInfo | None:
        """
        Get information about the current schema and available tables

        Returns:
            SchemaInfo model containing schema information including name and table list
        """
        if not self.is_initialized or not self.connection or not self.schema_manager:
            raise ValueError("Session is not initialized")

        # Use shared utility for schema info
        return self.schema_manager.get_schema_info(self.current_schema)

    def list_schemas(self) -> list[SchemaInfo]:
        """
        List all available schemas in the database with catalog context

        Returns:
            List of SchemaInfo models with catalog and schema names
        """
        if not self.is_initialized or not self.connection or not self.schema_manager:
            raise ValueError("Session is not initialized")

        # Use shared utility for listing schemas
        return self.schema_manager.list_all_schemas()

    def get_schema_names(self) -> list[str]:
        """
        Get just the schema names (for backward compatibility)

        Returns:
            List of unique schema names across all catalogs
        """
        schemas = self.list_schemas()
        return list({schema.schema_name for schema in schemas if schema.schema_name is not None})

    async def close_session_async(self) -> bool:
        """
        Close the session asynchronously (deletes from database and closes connection)

        Returns:
            True if successful, False otherwise
        """
        if not self.config.session_id:
            self.logger.warning("Session ID is not set, cannot close session")
            return False

        try:
            self.logger.info(f"Closing session {self.config.session_id}")

            # Close the session via API
            success = await self._query_session_service.close_query_session(
                self.config.session_id, self.config.project_id
            )

            # Locally close the DuckDB connection
            self.close_session()

            return success

        except Exception as e:
            self.logger.error(f"Failed to close session: {e}")
            return False

    async def update_session_timeout(self, timeout_minutes: int) -> QuerySessionModel | None:
        """
        Update the session's timeout (convenience method)

        Args:
            timeout_minutes: New timeout in minutes

        Returns:
            Updated QuerySessionModel if successful, None otherwise
        """
        return await self.update_session(timeout_minutes=timeout_minutes)

    async def update_session(
        self,
        timeout_minutes: int | None = None,
        database_path: str | None = None,
        session_name: str | None = None,
        status: QuerySessionStatus | None = None,
        metadata: str | None = None,
    ) -> QuerySessionModel | None:
        """
        Update the session's properties via API

        Args:
            timeout_minutes: Optional new timeout in minutes (unused currently)
            database_path: Optional new path to the DuckDB database file
            session_name: Optional new session name
            status: Optional new status
            metadata: Optional new session metadata

        Returns:
            Updated QuerySessionModel if successful, None otherwise
        """
        if not self.config.session_id:
            self.logger.warning("Session ID is not set, cannot update session")
            return None

        try:
            # Update via API
            response = await self._query_session_service.update_query_session(
                session_id=self.config.session_id,
                project_id=self.config.project_id,
                session_name=session_name,
                status=status,
                metadata=metadata,
            )

            # Update local config if the update was successful
            if response and database_path is not None:
                self.database_path = database_path

            return response

        except Exception as e:
            self.logger.error(f"Failed to update session: {e}")
            return None

    def close_session(self) -> None:
        """Close the DuckDB session and cleanup resources"""
        if self.connection:
            # Drop the storage secret if one was created
            if self._secret_name:
                self._storage_manager.drop_secret(self.connection, self._secret_name)

            self.connection.close()
            self.connection = None
            self.is_initialized = False

        schema_info = f" - schema: {self.current_schema}" if self.current_schema else ""
        self.logger.info(f"Session {self.config.effective_session_name}{schema_info} closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure session is closed"""
        self.close_session()

    def to_query_session_model(self) -> QuerySessionModel:
        """
        Convert the DuckDB session to a QuerySessionModel for API responses
        """
        return QuerySessionModel(
            id=self.config.session_id,
            session_name=self.config.effective_session_name,
            project_id=self.config.project_id,
            catalog_connection_id=self.config.catalog_connection_id,
            default_namespace=self.config.default_namespace,
            default_entity_id=self.config.default_entity_id,
            owner_id=self.config.user_id,
            status=QuerySessionStatus.ACTIVE,
            engine_type=QueryEngineType.DUCKDB,
            created_at=self.created_at,
            last_accessed_at=self.created_at,
            is_persistent=self.config.persistent,
            database_size_bytes=self.get_session_file_size(),
        )
