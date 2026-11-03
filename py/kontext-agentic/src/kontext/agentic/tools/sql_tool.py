"""SQL tools for executing and validating SQL queries in Kontext."""

import csv
import re
from io import StringIO
from typing import Any

from kontext.agent import RuntimeToolContext, SharedSessionStore, get_session_state
from kontext.agent.tools import reads_artifact, tool_meta
from kontext.common.artifacts.sequencing import MonotonicActionSequencer
from kontext.common.constants import QueryConstants
from kontext.common.jobs.trigger_actor import agent_actor, chat_session_actor
from kontext.common.protocols import AIToolkitServiceProviderProtocol
from kontext.common.query.engine import QueryEngineRequest
from kontext.schema import (
    ArtifactAction,
    ArtifactOrigin,
    ArtifactProvenance,
    ArtifactType,
    CodeLanguage,
    DataColumn,
    DataRef,
    DataTable,
    DataTableOpenAction,
    DataTableOpenActionPayload,
    InlineData,
    ProjectModel,
    QueryEngineType,
    SqlExecutionBatchResult,
    SqlExecutionResult,
    SqlValidationBatchResult,
    SqlValidationResult,
    UpdateChatSessionRequest,
)

from ..utils.guid_validation import validate_guids
from .kontext_toolkit import KontextToolkit, ToolkitScope

# Upper bound for a single batch call so one tool call cannot fan out unbounded
# work (and unbounded result payloads) in a run.
MAX_BATCH_STATEMENTS = 20

# Sampling caps for the peek-only `sample_records` tools: inline CSV rows for
# quick table/view profiling with no artifacts, no handles, and no UI actions.
SAMPLE_ROW_CAP = 25
DEFAULT_SAMPLE_ROWS = 20
SAMPLE_CELL_CHARS = 200
SAMPLE_BUDGET_CHARS = 4_000
SAMPLE_BATCH_BUDGET_CHARS = 16_000
_SAMPLE_BATCH_SKIP_BUDGET = SAMPLE_BUDGET_CHARS // 4


def _truncate_cell(value: Any) -> str:
    """Render one sample cell for CSV; NULL -> empty, long text -> truncated."""
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    if len(text) > SAMPLE_CELL_CHARS:
        return f"{text[:SAMPLE_CELL_CHARS]}…"
    return text


class SqlTools(KontextToolkit):
    """Toolkit for SQL execution and validation within project scope."""

    def __init__(
        self,
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: str | None = None,
        scope: ToolkitScope | None = None,
        default_sample_limit: int | None = None,
    ):
        """
        Initialize SQL tools with service factories.

        Args:
            project: Project model with full context
            session_id: Optional query session ID to reuse
            chat_session_id: Optional chat session ID for linking query sessions
            engine_type: Optional engine type
            default_sample_limit: Default row limit for `sample_records`
        """
        tools = [
            self.execute_sql,
            self.execute_sql_batch,
            self.validate_sql,
            self.validate_sql_batch,
            self.show_data_table,
            self.query_result_slice,
            self.sample_records,
            self.sample_records_batch,
        ]

        super().__init__(
            name="SQLTools",
            project=project,
            runtime_provider=runtime_provider,
            session_id=session_id,
            chat_session_id=chat_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
            scope=scope,
            tools=tools,
        )
        self.query_session_service = self.get_query_session_service()
        self.default_sample_limit = default_sample_limit

        if self.query_session_service is None:
            self.logger.warning("Query session service is not available.")

    @tool_meta(SqlExecutionResult, display_name="Query Data", emit_tool_call=True)
    async def execute_sql(
        self,
        sql: str,
        title: str | None = None,
        store_result_threshold_rows: int | None = QueryConstants.EXECUTION_PERSIST_THRESHOLD,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Execute SQL query to inspect data.

        Materialization is policy-driven: a result larger than
        ``store_result_threshold_rows`` is persisted automatically and returned
        as a durable ``data_table_id``. Smaller results stream back inline; a durable
        handle is created lazily if a downstream tool needs one, so the model no
        longer has to decide whether to reuse a result.

        :param sql: SQL query string.
        :param title: Result title.
        :param store_result_threshold_rows: Auto-persist result if rows exceed this limit.
        :param run_context: runtime context.
        """
        try:
            self.logger.info(f"Executing SQL query for project {self.project_id}")

            effective_session_id = await self._resolve_query_session()

            # Use sticky context (engine and catalog) from toolkit state — read
            # AFTER hydration, which may repair the sticky scope from the chat
            catalog_connection_id = self.catalog_connection_id
            default_namespace = self.default_namespace
            default_entity_id = self.default_entity_id
            engine_type = self.engine_type

            # Determine triggered_by - prefer ChatSession if available, then Agent
            triggered_by = (
                chat_session_actor(self.chat_session_id)
                if self.chat_session_id
                else agent_actor("sql_tool")
            )
            parent_run_id = self._get_current_execution_run_id(run_context)

            # Execute query using the session
            # Note: owner_id is NOT passed; the backend handles this via auth credentials

            response = (
                await self._require_query_session_service().execute_sql_with_session_management(
                    project_id=self.project_id,
                    sql_query=sql,
                    session_id=effective_session_id,
                    catalog_connection_id=catalog_connection_id,
                    default_namespace=default_namespace,
                    default_entity_id=default_entity_id,
                    store_result_threshold_rows=store_result_threshold_rows,
                    triggered_by=triggered_by,
                    chat_session_id=self.chat_session_id,
                    parent_run_id=parent_run_id,
                    store_result_as_resource=False,
                    store_result_name=title,
                    engine_type=engine_type,
                )
            )

            # Process response
            if not response.success:
                error_msg = response.error_message or "Unknown error"
                self.logger.error(
                    f"SQL execution failed for project {self.project_id}: {error_msg}"
                )

                error_result = SqlExecutionResult(
                    success=False,
                    message=f"SQL execution failed: {error_msg}",
                    execution_time_ms=int(response.total_execution_time_ms or 0),
                )
                return self._wrap_result(error_result)

            if not response.result:
                result_obj = SqlExecutionResult(
                    success=True,
                    message=f"Query executed successfully in {int(response.total_execution_time_ms or 0)}ms",
                    execution_time_ms=int(response.total_execution_time_ms or 0),
                )

                return self._wrap_result(result_obj)

            # Get the single result
            result = response.result
            data_table_id = response.data_id

            # Extract and convert data
            data_table = None
            dt_columns: list[DataColumn] = []

            if result:
                # Extract structured columns
                if result.columns:
                    dt_columns = [
                        DataColumn(name=col.name, type=col.type) for col in result.columns
                    ]

                # Populate data if rows exist
                if result.rows:
                    # Create DataTable for new InlineData field
                    data_table = DataTable(
                        columns=dt_columns, rows=result.rows, row_count=len(result.rows)
                    )

            row_count = int(result.row_count or 0) if result else 0
            # Use total execution time from the response, not individual result
            execution_time_ms = int(response.total_execution_time_ms or 0)

            self.logger.info(
                f"Query executed successfully: {row_count} rows, {execution_time_ms}ms"
            )

            # Handoff Protocol:
            # 1. Always return a reusable data_ref when rows are available.
            #    Backend-persisted results are preferred.
            # 2. If the backend only returned a preview, promote it once and
            #    reuse the same identity-scoped artifact on later turns.
            # 3. Always provide a compact preview when rows are available.

            data_ref = None
            preview_ds = None
            actions = []
            action_sequencer = MonotonicActionSequencer()
            identity_key = (
                self.build_data_identity_key(sql) if data_table and row_count > 0 else None
            )
            provenance = ArtifactProvenance(
                origin=ArtifactOrigin.SQLQUERY,
                created_by=agent_actor("sql_tool"),
                identity_key=identity_key,
                chat_session_id=str(self.chat_session_id) if self.chat_session_id else None,
            )

            # Generate preview if we have data (limit rows for context window)
            if data_table and data_table.rows:
                preview_rows = data_table.rows[
                    : QueryConstants.PREVIEW_ROW_LIMIT
                ]  # Limit records for model preview
                preview_dt = DataTable(
                    columns=data_table.columns, rows=preview_rows, row_count=row_count
                )
                preview_ds = InlineData(title=title or "Preview", table=preview_dt)

            if data_table_id:
                # Real persistent file
                data_ref = DataRef(data_id=data_table_id, code=sql, language=CodeLanguage.SQL)
                # Link artifact to session if available
                await self.link_artifact_to_session(
                    artifact_id=data_table_id,
                    artifact_type=ArtifactType.DATATABLE,
                    title=title or f"SQL Result ({data_table_id[:8]})",
                    meta={"sql": sql},
                    run_context=run_context,
                    register_shared_descriptor=True,
                    sql=sql,
                    identity_key=identity_key,
                    row_count=row_count,
                    column_names=[column.name for column in dt_columns],
                    provenance=provenance,
                )

                # Add open action for the frontend
                actions.append(
                    ArtifactAction(
                        root=DataTableOpenAction(
                            sequence=action_sequencer.next(),
                            payload=DataTableOpenActionPayload(
                                data_id=data_table_id, title=title or "Data Table"
                            ),
                        )
                    )
                )
            elif data_table and row_count > 0:
                existing_descriptor = (
                    self.find_data_artifact_by_identity(
                        identity_key,
                        run_context=run_context,
                    )
                    if identity_key
                    else None
                )

                if existing_descriptor is not None:
                    effective_id = existing_descriptor.artifact_id
                    await self.link_artifact_to_session(
                        artifact_id=effective_id,
                        artifact_type=ArtifactType.DATATABLE,
                        title=title
                        or existing_descriptor.title
                        or f"SQL Result ({effective_id[:8]})",
                        meta={"sql": sql},
                        run_context=run_context,
                        register_shared_descriptor=True,
                        sql=sql,
                        identity_key=identity_key,
                        row_count=row_count,
                        column_names=[column.name for column in dt_columns],
                        provenance=provenance,
                    )
                else:
                    ds_obj = InlineData(
                        title=title or f"Transient result {sql[:30]}...",
                        table=data_table,
                    )
                    temp_id = self.register_transient_artifact(
                        payload=ds_obj,
                        artifact_type=ArtifactType.DATATABLE,
                        title=ds_obj.title,
                        metadata={
                            "column_names": [column.name for column in dt_columns],
                            "identity_key": identity_key,
                            "row_count": row_count,
                            "sql": sql,
                        },
                    )
                    effective_id = await self.ensure_persistent_artifact(
                        artifact_id=temp_id,
                        artifact_type=ArtifactType.DATATABLE,
                        payload=ds_obj,
                        run_context=run_context,
                        promote_artifact=self._promote_inline_data_file,
                        title=ds_obj.title,
                        meta={"sql": sql},
                        register_shared_descriptor=True,
                        sql=sql,
                        identity_key=identity_key,
                        row_count=row_count,
                        column_names=[column.name for column in dt_columns],
                        provenance=provenance,
                    )

                data_ref = DataRef(data_id=effective_id, code=sql, language=CodeLanguage.SQL)
                actions.append(
                    ArtifactAction(
                        root=DataTableOpenAction(
                            sequence=action_sequencer.next(),
                            payload=DataTableOpenActionPayload(
                                data_id=effective_id, title=title or "Data Table"
                            ),
                        )
                    )
                )

            message_parts = [
                f"Query executed successfully in {execution_time_ms}ms returning {row_count} rows."
            ]
            if data_ref:
                message_parts.append("Durable `data_table_id` is available for downstream reuse.")

            result_obj = SqlExecutionResult(
                success=True,
                message=" ".join(message_parts),
                execution_time_ms=execution_time_ms,
                data_ref=data_ref,
                preview=preview_ds,
                actions=actions if actions else None,
                provenance=provenance,
            )

            return self._wrap_result(result_obj)

        except Exception as e:
            self.logger.error(f"SQL execution failed for project {self.project_id}: {e}")

            return self._create_result(
                success=False,
                result_class=SqlExecutionResult,
                message="SQL execution failed",
                error=str(e),
                execution_time_ms=0,
            )

    @tool_meta(SqlExecutionBatchResult, display_name="Query Data (Batch)", emit_tool_call=True)
    async def execute_sql_batch(
        self,
        statements: list[str],
        title: str | None = None,
        store_result_threshold_rows: int | None = QueryConstants.EXECUTION_PERSIST_THRESHOLD,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Execute several read-only SQL statements in one call.

        Prefer this over repeated ``execute_sql`` calls when you already know the
        set of exploratory queries to run. Statements execute in order and each
        result keeps its own ``data_ref``/``preview``, so downstream tools can
        still reuse any returned ``data_table_id``.

        :param statements: Read-only SQL statements to execute in order.
        :param title: Optional title prefix applied to each result.
        :param store_result_threshold_rows: Auto-persist a result if rows exceed this limit.
        :param run_context: runtime context.
        """
        input_error = self._batch_input_error(statements, action="execute")
        if input_error:
            return self._wrap_result(SqlExecutionBatchResult(success=False, message=input_error))

        results: list[SqlExecutionResult] = []
        for index, statement in enumerate(statements):
            raw = await self.execute_sql(
                sql=statement,
                title=f"{title} ({index + 1})" if title else None,
                store_result_threshold_rows=store_result_threshold_rows,
                run_context=run_context,
            )
            results.append(self._parse_result_model(raw, SqlExecutionResult))

        failed_count = self._failed_count(results)
        return self._wrap_result(
            SqlExecutionBatchResult(
                success=failed_count == 0,
                message=f"Executed {len(results)} statement(s); {failed_count} failed.",
                results=results,
                results_count=len(results),
                failed_count=failed_count,
                execution_time_ms=sum(result.execution_time_ms for result in results),
            )
        )

    @tool_meta(result_class=SqlValidationResult, display_name="Validate Query")
    async def validate_sql(self, sql: str) -> str:
        """Validate SQL query against project schemas.

        :param sql: SQL query to validate.
        """
        try:
            self.logger.info(f"Validating SQL query for project {self.project_id}")

            if not self.runtime_provider:
                raise ValueError("Runtime provider is required for SQL validation")

            # Resolve enum from sticky context
            q_engine_type = QueryEngineType.DUCKDB
            if self.engine_type:
                try:
                    q_engine_type = QueryEngineType(self.engine_type)
                except ValueError:
                    self.logger.warning(
                        f"Invalid engine_type {self.engine_type}, defaulting to DUCKDB"
                    )

            # Get an execution engine in shadow (validation) mode to validate the SQL.
            # Using the protocol-based resolver ensures we don't depend on direct imports.
            engine = self.runtime_provider.get_query_execution_engine(
                q_engine_type,
                request=QueryEngineRequest(
                    project_id=self.project_id,
                    shadow=True,
                ),
            )

            if engine is None:
                raise RuntimeError(
                    "SQL validation is unavailable in this runtime. "
                    "Use in-process/server runtime with DuckDB dependencies enabled."
                )

            # Validate the SQL using the resolved engine
            try:
                await engine.connect()
                is_valid, error_message = await engine.validate_sql(sql)
            finally:
                await engine.dispose()

            if is_valid:
                self.logger.info(f"SQL validation successful for project {self.project_id}")
                self.logger.debug(f"Validated SQL: {sql}")
                return self._create_result(
                    success=True, result_class=SqlValidationResult, message="SQL is valid"
                )
            else:
                self.logger.warning(
                    f"SQL validation failed for project {self.project_id}: {error_message}"
                )
                self.logger.debug(f"Invalid SQL: {sql}")
                return self._create_result(
                    success=False,
                    result_class=SqlValidationResult,
                    message="SQL validation failed",
                    error=error_message or "SQL is invalid",
                )

        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            self.logger.error(f"SQL validation error for project {self.project_id}: {e}")
            return self._create_result(
                success=False,
                result_class=SqlValidationResult,
                message="SQL validation error",
                error=str(e),
            )

    @tool_meta(result_class=SqlValidationBatchResult, display_name="Validate Queries (Batch)")
    async def validate_sql_batch(self, statements: list[str]) -> str:
        """Validate several SQL statements in one call.

        Use this to check a set of planned statements up front instead of paying
        one roundtrip per statement.

        :param statements: SQL statements to validate.
        """
        input_error = self._batch_input_error(statements, action="validate")
        if input_error:
            return self._wrap_result(SqlValidationBatchResult(success=False, message=input_error))

        results: list[SqlValidationResult] = []
        for statement in statements:
            raw = await self.validate_sql(sql=statement)
            results.append(self._parse_result_model(raw, SqlValidationResult))

        failed_count = self._failed_count(results)
        return self._wrap_result(
            SqlValidationBatchResult(
                success=failed_count == 0,
                message=f"Validated {len(results)} statement(s); {failed_count} invalid.",
                results=results,
                results_count=len(results),
                failed_count=failed_count,
            )
        )

    @staticmethod
    def _batch_input_error(statements: list[str], *, action: str) -> str | None:
        """Reject empty/oversized batches before any statement is executed."""
        if not statements:
            return "No statements provided."
        if len(statements) > MAX_BATCH_STATEMENTS:
            return (
                f"Too many statements ({len(statements)}); "
                f"{action} at most {MAX_BATCH_STATEMENTS} per call."
            )
        return None

    @reads_artifact(
        SqlExecutionResult,
        artifact_type=ArtifactType.DATATABLE,
        display_name="Show Data Table",
        emit_tool_call=True,
        emit_result=True,
    )
    @validate_guids("data_table_id")
    async def show_data_table(
        self, data_table_id: str, run_context: RuntimeToolContext | None = None
    ) -> str:
        """Show a data table (transient or persistent) by ID to the user.
        If data is not persisted, the full table will be included in the result;
        otherwise, it includes preview records and UI actions to open the artifact tab.

        :param data_table_id: ID of the data table to show.
        :param run_context: runtime context.
        """
        try:
            self.logger.info(f"Showing data table for project {self.project_id}: {data_table_id}")
            durable_id = (
                self.resolve_shared_artifact_id(data_table_id, run_context=run_context)
                or data_table_id
            )

            # 1. Resolve logical data table (might be transient or persistent)
            ds_obj = self.get_transient_data(data_table_id)
            is_transient = ds_obj is not None

            if not ds_obj:
                # Try to load from file service if not transient
                file_service = self.get_file_service()
                if file_service:
                    try:
                        content = await file_service.get_file_content(self.project_id, durable_id)
                        ds_obj = InlineData.model_validate_json(content)
                    except Exception as e:
                        self.logger.debug(
                            f"Could not load data table {durable_id} from file service: {e}"
                        )

            if not ds_obj:
                raise ValueError(f"Data table with ID '{data_table_id}' not found.")

            # 2. Check size and determine if we should return full data or preview + action
            row_count = 0
            if ds_obj.table:
                # row_count might be missing in some cases if it was just created
                row_count = ds_obj.table.row_count
                if row_count is None:
                    row_count = len(ds_obj.table.rows) if ds_obj.table.rows else 0

            # Use threshold for embedding vs promotion
            embedding_threshold = QueryConstants.DOCUMENT_EMBEDDING_THRESHOLD

            preview_ds = None
            actions = None
            message = ds_obj.title or "Data table details"
            effective_id = durable_id
            action_sequencer = MonotonicActionSequencer()

            # Handoff Strategy:
            # 1. If already persisted: Return ID and preview records in actions immediately.
            # 2. If transient:
            #    - <= threshold: Embed full data in result.
            #    - > threshold: Promote to file and return ID/action.
            if not is_transient:
                # Case: Already persistent -> ensure the session link exists and
                # return an open action. This is a display operation, so it must
                # not overwrite the descriptive title/provenance recorded when
                # the table was created by ``execute_sql``.
                self.logger.info(f"Data table {effective_id} is already persisted.")
                await self.link_artifact_to_session(
                    artifact_id=effective_id,
                    artifact_type=ArtifactType.DATATABLE,
                    title=None,
                    meta=None,
                    run_context=run_context,
                    register_shared_descriptor=False,
                )

                # Create limited preview for persisted data
                if ds_obj.table:
                    preview_dt = DataTable(
                        columns=ds_obj.table.columns,
                        rows=ds_obj.table.rows[: QueryConstants.PREVIEW_ROW_LIMIT]
                        if ds_obj.table.rows
                        else [],
                        row_count=row_count,
                    )
                    preview_ds = InlineData(title=ds_obj.title, table=preview_dt)

                # Add Open Action
                actions = [
                    ArtifactAction(
                        root=DataTableOpenAction(
                            sequence=action_sequencer.next(),
                            payload=DataTableOpenActionPayload(
                                data_id=effective_id, title=ds_obj.title or "Data Table"
                            ),
                        )
                    )
                ]
                message = (
                    f"Data table (ID: {effective_id}) is available. Returning preview and UI link."
                )
            else:
                # Case: Transient
                if row_count <= embedding_threshold:
                    # Small enough to return fully embedded
                    self.logger.info(
                        f"Data table {data_table_id} is transient and small ({row_count} rows), embedding fully."
                    )
                    preview_ds = ds_obj
                else:
                    # Too large: Promote to file and return ID/action
                    self.logger.info(
                        f"Transient data table {data_table_id} exceeds threshold ({row_count} > {embedding_threshold}), promoting..."
                    )
                    effective_id = await self.resolve_data_table_id(
                        data_table_id, run_context=run_context
                    )

                    # Create limited preview for newly promoted data
                    if ds_obj.table:
                        preview_dt = DataTable(
                            columns=ds_obj.table.columns,
                            rows=ds_obj.table.rows[: QueryConstants.PREVIEW_ROW_LIMIT]
                            if ds_obj.table.rows
                            else [],
                            row_count=row_count,
                        )
                        preview_ds = InlineData(title=ds_obj.title, table=preview_dt)

                    # Add Open Action
                    actions = [
                        ArtifactAction(
                            root=DataTableOpenAction(
                                sequence=action_sequencer.next(),
                                payload=DataTableOpenActionPayload(
                                    data_id=effective_id, title=ds_obj.title or "Data Table"
                                ),
                            )
                        )
                    ]
                    message = f"Data table promoted to file (ID: {effective_id}). Returning preview and UI link."

            data_ref = DataRef(data_id=effective_id)
            result_obj = SqlExecutionResult(
                success=True,
                message=message,
                execution_time_ms=0,
                data_ref=data_ref,
                preview=preview_ds,
                actions=actions,
            )

            return self._wrap_result(result_obj)

        except Exception as e:
            self.logger.error(
                f"Failed to inspect data table {data_table_id} for project {self.project_id}: {e}"
            )
            return self._create_result(
                success=False,
                result_class=SqlExecutionResult,
                message=f"Failed to inspect data table: {e!s}",
                error=str(e),
                execution_time_ms=0,
            )

    @tool_meta(SqlExecutionResult, display_name="Read Result Slice", emit_tool_call=True)
    @validate_guids("data_table_id")
    async def query_result_slice(
        self,
        data_table_id: str,
        offset: int = 0,
        limit: int = 50,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Read a window of rows from a previously materialized data table.

        Prefer this over re-running a query when you only need to inspect more
        rows of a result you already produced. Large results keep their full
        rows in a columnar row store; small results are embedded in full in the
        descriptor. Either way this returns only the requested window.

        :param data_table_id: Durable data table ID from an earlier ``execute_sql``.
        :param offset: Zero-based row offset to start from.
        :param limit: Maximum number of rows to return.
        :param run_context: runtime context.
        """
        try:
            await self.hydrate_query_scope_from_chat_session()
            effective_id = (
                self.resolve_shared_artifact_id(data_table_id, run_context=run_context)
                or data_table_id
            )

            file_service = self.get_file_service()
            if not file_service:
                raise ValueError("File service is not available for result retrieval.")

            start = max(0, int(offset))
            bounded_limit = max(1, min(int(limit), QueryConstants.MAX_FETCH_ROWS))
            window = await file_service.get_inline_data_rows(
                self.project_id,
                effective_id,
                offset=start,
                limit=bounded_limit,
            )
            rows = (window.table.rows or []) if window.table else []
            total_row_count = window.table.row_count if window.table else 0

            returned = (
                f"rows {start}-{start + len(rows) - 1}" if rows else f"no rows at offset {start}"
            )
            result_obj = SqlExecutionResult(
                success=True,
                message=(
                    f"Returned {returned} of {total_row_count} from data table {effective_id}."
                ),
                execution_time_ms=0,
                data_ref=DataRef(data_id=effective_id),
                preview=window,
            )
            return self._wrap_result(result_obj)

        except Exception as e:
            self.logger.error(f"Failed to read result slice for {data_table_id}: {e}")
            return self._create_result(
                success=False,
                result_class=SqlExecutionResult,
                message=f"Failed to read result slice: {e!s}",
                error=str(e),
                execution_time_ms=0,
            )

    @tool_meta(SqlExecutionResult, display_name="Sample Records", emit_tool_call=True)
    async def sample_records(
        self,
        sql: str,
        limit: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Peek at rows of a table or view inline as CSV.

        Read-only sampling with no side effects: unlike ``execute_sql`` this
        returns no ``data_table_id``, creates no artifacts, and emits no UI
        actions. Use it for quick data profiling during discovery; use
        ``execute_sql`` when a downstream tool needs a reusable result. The
        statement is clamped to ``limit`` rows (default DEFAULT_SAMPLE_ROWS,
        ceiling SAMPLE_ROW_CAP) and long cells are truncated; a per-call
        character budget may stop rows early with a ``-- truncated`` marker.

        :param sql: Read-only SELECT statement over a table or view to sample.
        :param limit: Maximum number of rows to return.
        :param run_context: runtime context.
        """
        return await self._sample_statement(
            sql,
            limit=self._effective_row_limit(limit),
            budget=SAMPLE_BUDGET_CHARS,
            run_context=run_context,
        )

    @tool_meta(SqlExecutionResult, display_name="Sample Records (Batch)", emit_tool_call=True)
    async def sample_records_batch(
        self,
        statements: list[str],
        limit: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Sample several read-only statements in one turn.

        Prefer this over repeated ``sample_records`` calls once discovery has
        picked the candidate tables or views. Each statement returns its own
        CSV block tagged ``-- [i/N]`` plus a one-line SQL preview. Sampling
        continues when an individual statement errors, and a shared character
        budget may skip the remaining statements (reported in a trailer) —
        sample those with ``sample_records`` afterwards.

        :param statements: Read-only SELECT statements to sample in order.
        :param limit: Maximum number of rows per statement.
        :param run_context: runtime context.
        """
        input_error = self._batch_input_error(statements, action="sample")
        if input_error:
            return f"-- sample batch rejected: {input_error}"

        effective_limit = self._effective_row_limit(limit)
        blocks: list[str] = []
        remaining_budget = SAMPLE_BATCH_BUDGET_CHARS
        for index, statement in enumerate(statements, start=1):
            if remaining_budget <= _SAMPLE_BATCH_SKIP_BUDGET:
                blocks.append(
                    f"-- skipped statements {index}-{len(statements)}: batch sample budget "
                    "exhausted; sample them with `sample_records` individually"
                )
                break
            block = await self._sample_statement(
                statement,
                limit=effective_limit,
                budget=min(remaining_budget, SAMPLE_BUDGET_CHARS),
                run_context=run_context,
            )
            tagged = f"-- [{index}/{len(statements)}] {' '.join(statement.split())[:120]}\n{block}"
            blocks.append(tagged)
            remaining_budget -= len(tagged)
        return "\n\n".join(blocks)

    async def _sample_statement(
        self, sql: str, *, limit: int, budget: int, run_context: RuntimeToolContext | None
    ) -> str:
        """Execute one read-only statement and return an inline CSV block.

        Artifact-free by design: no transient registration, no lineage, no
        promotion, no session actions, no ``data_ref``.
        """
        try:
            service = self._require_query_session_service()
            effective_session_id = await self._resolve_query_session()
            triggered_by = (
                chat_session_actor(self.chat_session_id)
                if self.chat_session_id
                else agent_actor("sql_tool")
            )
            parent_run_id = self._get_current_execution_run_id(run_context)

            response = await service.execute_sql_with_session_management(
                project_id=self.project_id,
                sql_query=self._prepare_sample_sql(sql, limit),
                session_id=effective_session_id,
                catalog_connection_id=self.catalog_connection_id,
                default_namespace=self.default_namespace,
                default_entity_id=self.default_entity_id,
                store_result_threshold_rows=QueryConstants.MAX_FETCH_ROWS,
                triggered_by=triggered_by,
                chat_session_id=self.chat_session_id,
                parent_run_id=parent_run_id,
                store_result_as_resource=False,
                store_result_name=None,
                engine_type=self.engine_type,
            )

            if not response.success:
                return f"-- error: {response.error_message or 'Unknown error'}"

            result = response.result
            if result is None:
                return "-- error: statement returned no result"

            rows = result.rows or []
            columns = result.columns or []
            row_count = int(result.row_count or len(rows))
            csv_text, emitted, budget_truncated = self._format_sample_csv(
                columns, rows, row_limit=limit, budget=budget
            )
            ms = int(response.total_execution_time_ms or 0)
            lines = [f"-- sampled {emitted} of {row_count} rows in {ms}ms", csv_text.rstrip("\n")]
            hidden = row_count - emitted
            if budget_truncated:
                lines.append(
                    f"-- truncated: {hidden} of {row_count} rows not shown (call-char budget)"
                )
            elif hidden > 0:
                lines.append(
                    f"-- {hidden} of {row_count} rows not shown (sample limit);"
                    " narrow the projection or use execute_sql for full results"
                )
            return "\n".join(lines)
        except Exception as e:
            self.logger.error(f"Sample records failed for project {self.project_id}: {e}")
            return f"-- error: {e!s}"

    def _require_query_session_service(self):
        """Return the query session service or raise if the runtime lacks one."""
        service = self.query_session_service
        if service is None:
            raise ValueError("Query session service is not available")
        return service

    async def _resolve_query_session(self) -> str:
        """Ensure the sticky query session exists; return its effective ID.

        Hydrates chat-scoped scope first (which may update the sticky context),
        resolves or creates the session, and links a repaired session back to
        the chat session.
        """
        await self.hydrate_query_scope_from_chat_session()

        service = self._require_query_session_service()

        effective_session_id = await service.get_or_create_session(
            project_id=self.project_id,
            session_id=self.session_id,
            catalog_connection_id=self.catalog_connection_id,
            default_namespace=self.default_namespace,
            default_entity_id=self.default_entity_id,
            session_name="Agent Session",
            engine_type=self.engine_type,
        )

        if effective_session_id != self.session_id:
            if self.chat_session_id:
                await self._link_query_session_to_chat(effective_session_id)
            self.session_id = effective_session_id
        return effective_session_id

    def _effective_row_limit(self, limit: int | None) -> int:
        """Clamp an optional requested row limit into [1, SAMPLE_ROW_CAP]."""
        limit = limit if limit is not None else self.default_sample_limit
        limit = limit if limit is not None else DEFAULT_SAMPLE_ROWS
        return max(1, min(int(limit), SAMPLE_ROW_CAP))

    @staticmethod
    def _prepare_sample_sql(sql: str, limit: int) -> str:
        """Clamp a read-only statement to at most ``limit`` rows.

        Appends ``LIMIT`` when the statement has no terminal limit clause and
        tightens a terminal DuckDB/Postgres-style ``LIMIT``. A MySQL-style
        ``LIMIT <o>, <c>`` cannot be rewritten safely and is left untouched;
        serialization caps the rendered rows regardless.
        """
        statement = sql.strip()
        while statement.endswith(";"):
            statement = statement[:-1].rstrip()
        clamp = re.search(r"\bLIMIT\s+(\d+)\s*(?:OFFSET\s+\d+)?\s*$", statement, re.IGNORECASE)
        if clamp:
            if int(clamp.group(1)) <= limit:
                return statement
            return f"{statement[: clamp.start(1)]}{limit}{statement[clamp.end(1) :]}"
        if re.search(r"\bLIMIT\b[^()]*$", statement, re.IGNORECASE):
            return statement
        return f"{statement} LIMIT {limit}"

    @staticmethod
    def _format_sample_csv(
        columns: list[Any], rows: list[Any], *, row_limit: int, budget: int
    ) -> tuple[str, int, bool]:
        """Render rows as RFC-4180 CSV within a character budget.

        Returns ``(csv text, emitted rows, budget_truncated)``. Column names
        are paid once in the header; cells render through ``_truncate_cell``
        so one wide text column cannot blow the budget alone.
        """
        header_buffer = StringIO()
        csv.writer(header_buffer, lineterminator="\n").writerow([column.name for column in columns])
        header = header_buffer.getvalue()

        lines: list[str] = []
        emitted = 0
        used = 0
        truncated = False
        for row in rows[:row_limit]:
            row_buffer = StringIO()
            csv.writer(row_buffer, lineterminator="\n").writerow(
                [_truncate_cell(value) for value in row]
            )
            line = row_buffer.getvalue()
            if used + len(line) > budget:
                truncated = True
                break
            lines.append(line)
            used += len(line)
            emitted += 1
        return header + "".join(lines), emitted, truncated

    async def _link_query_session_to_chat(self, query_session_id: str) -> None:
        """Link query session to chat session if not already linked."""
        if not self.chat_session_id:
            return

        # Skip if session_id is already set (already linked)
        if self.session_id and self.session_id == query_session_id:
            return

        try:
            chat_session_service = (
                self.runtime_provider.get_chat_session_service() if self.runtime_provider else None
            )

            if not chat_session_service:
                self.logger.warning(
                    "Cannot link query session: chat session persistence unavailable"
                )
                return

            chat_session = await chat_session_service.get_session(str(self.chat_session_id))

            current_query_session_id = (
                str(chat_session.query_session_id)
                if chat_session and chat_session.query_session_id
                else None
            )

            # Persist the effective session whenever the chat points to no session
            # or to a different/incompatible one, so later notebook/tool calls
            # reuse the repaired chat-linked session.
            if current_query_session_id != query_session_id:
                await chat_session_service.update_session(
                    session_id=str(self.chat_session_id),
                    request=UpdateChatSessionRequest(query_session_id=query_session_id),
                    user_id=None,
                )
                # Update local reference
                self.session_id = query_session_id
                self.logger.info(
                    f"Linked query session {query_session_id} to chat session {self.chat_session_id}"
                )
        except Exception as e:
            self.logger.warning(f"Failed to link query session to chat session: {e}")

    def _get_current_execution_run_id(self, run_context: RuntimeToolContext | None) -> str | None:
        """Read the current execution run ID from shared session state."""
        session_state = get_session_state(run_context)
        store = SharedSessionStore.from_session_state(session_state)
        if store is None:
            return None
        return store.get_current_execution_run_id()
