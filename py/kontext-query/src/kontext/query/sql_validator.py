"""SQL validation helpers for query engines and project schemas."""

import logging

from kontext.common.protocols import QueryRuntimeProviderProtocol
from kontext.common.query.engine import QueryEngineRequest, QueryExecutionEngine
from kontext.schema import QueryEngineType, SchemaInfo

from .engine_factory import resolve_engine_for_session


async def validate_sql_for_project(
    project_id: str,
    sql: str,
    runtime_provider: QueryRuntimeProviderProtocol,
    engine_type: QueryEngineType = QueryEngineType.DUCKDB,
) -> tuple[bool, str | None]:
    """
    Validate SQL query against a project's catalog-backed schemas.

    Args:
        project_id: The project ID to load schemas for
        sql: SQL query to validate
        runtime_provider: Runtime provider for engine dependencies
        engine_type: Optional engine type to use for validation

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Use shadow mode for DuckDB (no cloud storage access required)
    is_shadow = engine_type is None or engine_type == QueryEngineType.DUCKDB

    try:
        async with SqlValidator(
            project_id=project_id,
            runtime_provider=runtime_provider,
            engine_type=engine_type or QueryEngineType.DUCKDB,
            shadow=is_shadow,
        ) as validator:
            return await validator.validate_sql(sql)

    except Exception as e:
        logging.error(f"Failed to validate SQL for project {project_id}: {e}")
        return False, f"Validation setup failed: {e}"


async def get_project_schema_info(
    project_id: str,
    runtime_provider: QueryRuntimeProviderProtocol,
    engine_type: QueryEngineType = QueryEngineType.DUCKDB,
) -> SchemaInfo | None:
    """
    Get schema information for a project

    Args:
        project_id: The project ID to get schemas for
        runtime_provider: Runtime provider for engine dependencies
        engine_type: Optional engine type to use

    Returns:
        SchemaInfo model with schema and table information, or None if failed
    """
    try:
        async with SqlValidator(
            project_id=project_id,
            runtime_provider=runtime_provider,
            engine_type=engine_type,
            shadow=True,  # Always use shadow mode for quick schema info
        ) as validator:
            return await validator.get_schema_info_async()
    except Exception as e:
        logging.error(f"Failed to get schema info for project {project_id} ({engine_type}): {e}")
        return None


class SqlValidator:
    """
    Reusable SQL validator for a specific project

    This class handles efficient validation of multiple SQL queries
    against a project using either shadow or live engines.
    """

    def __init__(
        self,
        project_id: str,
        runtime_provider: QueryRuntimeProviderProtocol,
        engine_type: QueryEngineType = QueryEngineType.DUCKDB,
        shadow: bool = True,
    ):
        self.project_id = project_id
        self.runtime_provider = runtime_provider
        self.engine_type = engine_type
        self.shadow = shadow
        self.engine: QueryExecutionEngine | None = None
        self.is_initialized = False

    async def initialize(self) -> None:
        """Initialize the execution engine"""
        if not self.is_initialized:
            self.engine = await resolve_engine_for_session(
                engine_type=self.engine_type,
                runtime_provider=self.runtime_provider,
                request=QueryEngineRequest(
                    project_id=self.project_id,
                    shadow=self.shadow,
                ),
            )
            # Connect will initialize the session (and shadow db if needed)
            await self.engine.connect()
            self.is_initialized = True

    async def validate_sql(self, sql: str) -> tuple[bool, str | None]:
        """
        Validate SQL query

        Args:
            sql: SQL query to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.is_initialized:
            await self.initialize()

        if self.engine:
            return await self.engine.validate_sql(sql)

        return False, "Validator not properly initialized"

    async def get_schema_info_async(self) -> SchemaInfo | None:
        """Get schema information asynchronously"""
        if not self.is_initialized:
            await self.initialize()

        if self.engine:
            # Protocol uses get_schema()
            return await self.engine.get_schema()
        return None

    async def dispose(self) -> None:
        """Close the validator and cleanup resources"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
        self.is_initialized = False

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.dispose()
