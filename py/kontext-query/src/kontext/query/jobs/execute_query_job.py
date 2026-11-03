"""
Execute Query Job

Executes a SQL query in an existing DuckDB query session.
This job handles real-time query execution with proper session management,
error handling, and result formatting. Supports only a single SQL statement.
Optionally stores results as a file.
"""

import asyncio
import logging
import time
from uuid import UUID

from pydantic import Field, field_validator

from kontext.auth import JobPermissions, QuerySessionPermissions
from kontext.common.constants import QueryConstants
from kontext.common.query.engine import QueryEngineRequest
from kontext.common.query.result_materialization import should_persist_result
from kontext.common.query.session_compatibility import requires_catalog_connection
from kontext.common.query.session_locks import session_execution_lock
from kontext.common.query.session_scope import hydrate_session_scope
from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.query.engine_factory import resolve_engine_for_session
from kontext.schema import JobCategory, QueryEngineType, QueryResponse

logger = logging.getLogger(__name__)


class ExecuteQueryParams(BaseJobParams):
    """Parameters for executing SQL queries in query sessions."""

    sql: str = Field(..., description="SQL query to execute")
    session_id: str | None = Field(
        default=None, description="Existing session ID to use (optional)"
    )
    catalog_connection_id: str | None = Field(
        default=None, description="Optional catalog connection ID for the query session"
    )
    default_namespace: str | None = Field(
        default=None, description="Optional default namespace for the query session"
    )
    default_entity_id: str | None = Field(
        default=None, description="Optional default entity ID for the query session"
    )
    engine_type: QueryEngineType = Field(
        default=QueryEngineType.DUCKDB,
        description="The query engine type (e.g. DuckDB, Snowflake)",
    )
    query_timeout_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Query execution timeout in seconds (default: 300)",
    )
    store_result_as_resource: bool = Field(
        default=False, description="Store results as a file (default: False)"
    )
    store_result_threshold_rows: int | None = Field(
        default=None,
        description=("Threshold row count to automatically store results as a file"),
    )
    store_result_name: str | None = Field(
        default=None,
        description="Optional name to use when storing query results as file",
    )
    existing_data_id: str | None = Field(
        default=None, description="Existing file ID to update (optional)"
    )

    @field_validator("catalog_connection_id", "default_entity_id", "session_id", "existing_data_id")
    @classmethod
    def validate_uuid_format(cls, v: str | None) -> str | None:
        """Validate that UUID fields contain valid UUID strings."""
        if v is None or v == "":
            return v
        try:
            UUID(v)
            return v
        except ValueError as e:
            raise ValueError(f"Invalid UUID format: {v}") from e


@job(
    job_type="python.jobs.ExecuteQueryJob",
    name="Execute Query",
    description="Executes a SQL query in a query session",
    category=JobCategory.DATAPROCESSING,
    params_model=ExecuteQueryParams,
    required_permissions=[
        JobPermissions.EXECUTE,
        QuerySessionPermissions.EXECUTE,
    ],
    display_parameter="sql",
    is_system_job=True,
    icon="database",
)
class ExecuteQueryJob(BasePythonJob[ExecuteQueryParams]):
    """
    Job for executing SQL queries in query sessions.

    This job:
    1. Resolves the query execution engine (DuckDB, Snowflake, etc.)
    2. Executes the provided SQL query
    3. Returns formatted results with proper error handling
    4. Manages session lifecycle and cleanup
    """

    async def execute_job(self, context: JobContext, parameters: ExecuteQueryParams) -> JobResult:
        """Execute the query in a DuckDB session."""
        try:
            project_id = context.project_id
            if not project_id:
                return JobResult.error_result("Project ID not available in job context")

            sql = parameters.sql
            session_id = parameters.session_id
            query_timeout_seconds = parameters.query_timeout_seconds
            catalog_connection_id = parameters.catalog_connection_id or None
            default_namespace = parameters.default_namespace or None
            default_entity_id = parameters.default_entity_id or None
            (
                catalog_connection_id,
                default_namespace,
                default_entity_id,
                hydrated_engine_type,
            ) = await hydrate_session_scope(
                query_session_service=context.get_query_session_service(),
                project_id=project_id,
                session_id=session_id,
                catalog_connection_id=catalog_connection_id,
                default_namespace=default_namespace,
                default_entity_id=default_entity_id,
                engine_type=parameters.engine_type,
            )
            engine_type = hydrated_engine_type

            if requires_catalog_connection(engine_type) and not catalog_connection_id:
                return JobResult.error_result(
                    "Session error: missing catalog_connection_id "
                    "for the current live SQL session scope"
                )

            scope_parts = []
            if catalog_connection_id:
                scope_parts.append(f"catalog {catalog_connection_id}")
            if default_namespace:
                scope_parts.append(f"namespace {default_namespace}")
            if default_entity_id:
                scope_parts.append(f"entity {default_entity_id}")
            scope_msg = f", {', '.join(scope_parts)}" if scope_parts else ""
            await context.log_debug(f"Executing query for project {project_id}{scope_msg}")

            engine = None
            try:
                runtime_provider = context.get_runtime_provider()

                # Serialize access to the (single-writer) session database.
                lock_key = session_id or f"__ephemeral__{project_id}"
                async with session_execution_lock(lock_key):
                    engine = await resolve_engine_for_session(
                        engine_type=engine_type,
                        runtime_provider=runtime_provider,
                        request=QueryEngineRequest(
                            project_id=str(project_id),
                            session_id=session_id,
                            catalog_connection_id=catalog_connection_id,
                            default_namespace=default_namespace,
                            default_entity_id=default_entity_id,
                        ),
                    )
                    await engine.connect()

                    sql_preview = sql[:100] + "..." if len(sql) > 100 else sql
                    await context.log_debug(f"Executing query on {engine_type}: {sql_preview}")

                    start_time = time.time()

                    try:
                        table = await asyncio.wait_for(
                            engine.fetch_data_table(sql, max_rows=QueryConstants.MAX_FETCH_ROWS),
                            timeout=query_timeout_seconds,
                        )
                        last_result = table
                    except TimeoutError:
                        error_msg = (
                            f"Query execution timed out after {query_timeout_seconds} seconds"
                        )
                        await context.log_error(error_msg)
                        return JobResult.error_result(error_msg)
                    except Exception as query_error:
                        error_msg = f"Query execution failed: {query_error!s}"
                        await context.log_error(error_msg)
                        return JobResult.error_result(error_msg)

                    total_execution_time_ms = int((time.time() - start_time) * 1000)

                    final_result_data = QueryResponse(
                        result=last_result,
                        total_execution_time_ms=total_execution_time_ms,
                        success=True,
                        error_message=None,
                        data_id=None,
                        sql=parameters.sql,
                    )

                    store_result_name = parameters.store_result_name
                    existing_data_id = parameters.existing_data_id

                    total_rows = (last_result.row_count or 0) if last_result else 0
                    persist_result = bool(last_result) and should_persist_result(
                        row_count=total_rows,
                        store_as_resource=parameters.store_result_as_resource,
                        threshold_rows=parameters.store_result_threshold_rows,
                    )

                    if persist_result and last_result:
                        file_service = context.get_file_service()
                        chat_session_id = await _resolve_chat_session_id(context)
                        file_id = await file_service.store_query_results_as_file(
                            project_id=project_id,
                            query_response=final_result_data,
                            session_id=session_id,
                            existing_file_id=existing_data_id,
                            name=store_result_name,
                            chat_session_id=chat_session_id,
                        )
                        if file_id:
                            final_result_data.data_id = file_id
                            if final_result_data.result:
                                res = final_result_data.result
                                if res.rows:
                                    res.rows = res.rows[: QueryConstants.PREVIEW_ROW_LIMIT]

                            await context.log_info(
                                f"Query results stored as file: {file_id}. "
                                f"Preview rows retained "
                                f"(max {QueryConstants.PREVIEW_ROW_LIMIT})."
                            )

                    return JobResult.success_result(
                        message="Query executed successfully",
                        data=final_result_data.model_dump(by_alias=True),
                    )
            except Exception as session_error:
                await context.log_error(f"Failed to create or access session: {session_error}")
                return JobResult.error_result(f"Session error: {session_error!s}")
            finally:
                if engine and hasattr(engine, "dispose"):
                    await engine.dispose()
        except Exception as e:
            await context.log_error(f"Unexpected error in ExecuteQueryJob: {e}")
            return JobResult.error_result(f"Job execution failed: {e}")


async def _resolve_chat_session_id(context: JobContext) -> str | None:
    """Resolve the chat session that owns this query run, if any.

    The chat session is recorded on the durable execution-run context when the
    run is queued, so the worker can recover provenance without it being a
    serialized job parameter (which crosses the queue/process boundary).
    Provenance is read through the provider port so the same job body runs
    against any runtime composition.
    """
    try:
        provenance_service = context.get_execution_run_context_service()
        provenance = await provenance_service.get_run_provenance(context.job_run_id)
        if provenance and provenance.chat_session_id:
            return provenance.chat_session_id
    except Exception as exc:  # pragma: no cover - best-effort provenance
        logger.warning("Failed to resolve chat session for run %s: %s", context.job_run_id, exc)
    return None
