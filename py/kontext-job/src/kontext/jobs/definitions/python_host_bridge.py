"""Host bridge shared by managed Python execution jobs.

The bridge serves kernel host calls (``execute_sql``, ``save_table``) for both
session scripts and notebook blocks. Origin and actor are parameters so the
same implementation stamps the right provenance on either path:

* session scripts -> ``agent_python`` (or the requesting actor);
* notebook blocks -> ``notebook_run`` with the block id.

Notebook bridges are constructed without ``query_parameters``, which disables
``execute_sql`` (the portable-code contract) while keeping ``save_table``.
"""

from __future__ import annotations

import base64
import io
import re
from contextlib import suppress
from typing import Any, Protocol
from uuid import UUID

from kontext.common.python_execution.runner import PythonRunnerHostBridge
from kontext.common.query.engine import QueryEngineRequest, QueryEngineType
from kontext.jobs.job_context import JobContext
from kontext.schema import (
    ArtifactOrigin,
    ArtifactProvenance,
    ArtifactType,
    DataTable,
    TriggerActorModel,
)

_PYTHON_SQL_MAX_ROWS = 5_000
_SAVE_TABLE_MAX_ROWS = 200_000
_SAVE_TABLE_MAX_PARQUET_BYTES = 48 * 1024 * 1024

_LINE_COMMENT_PATTERN = re.compile(r"--[^\n]*")
_BLOCK_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.DOTALL)
_READ_ONLY_SQL_PATTERN = re.compile(
    r"\b("
    r"insert|update|delete|alter|create|drop|truncate|merge|replace|copy|"
    r"call|attach|detach|grant|revoke|use|set|pragma|vacuum"
    r")\b",
    re.IGNORECASE,
)


class QueryContext(Protocol):
    """Query-scope fields the bridge needs to serve ``execute_sql``."""

    query_session_id: str | None
    engine_type: str | None
    catalog_connection_id: str | None
    default_namespace: str | None
    default_entity_id: str | None


def normalize_read_only_sql(sql: str) -> str:
    """Validate that ``sql`` is a single read-only statement and normalize it."""
    normalized = _BLOCK_COMMENT_PATTERN.sub(" ", sql or "")
    normalized = _LINE_COMMENT_PATTERN.sub(" ", normalized)
    normalized = normalized.strip()
    if not normalized:
        raise ValueError("Managed Python SQL execution requires a non-empty SQL query.")

    normalized = normalized.rstrip(";").strip()
    if ";" in normalized:
        raise ValueError(
            "Managed Python SQL execution only supports a single read-only SQL statement."
        )

    lowered = normalized.lower()
    if not lowered.startswith(("select", "with")):
        raise ValueError(
            "Managed Python SQL execution only supports read-only SELECT / WITH queries."
        )

    match = _READ_ONLY_SQL_PATTERN.search(lowered)
    if match:
        raise ValueError(
            "Managed Python SQL execution rejected a non-read-only statement "
            f"containing `{match.group(0).lower()}`."
        )

    return normalized


def resolve_query_engine_type(engine_type: str | None) -> QueryEngineType:
    if not engine_type:
        return QueryEngineType.DUCKDB

    try:
        return QueryEngineType(engine_type)
    except ValueError:
        return QueryEngineType.DUCKDB


class ManagedPythonBridge(PythonRunnerHostBridge):
    """Serve kernel host calls for one managed Python execution."""

    def __init__(
        self,
        *,
        context: JobContext,
        chat_session_id: str | None,
        origin: ArtifactOrigin,
        triggered_by: TriggerActorModel | None,
        block_id: str | None = None,
        query_parameters: QueryContext | None = None,
    ) -> None:
        self._context = context
        self._chat_session_id = chat_session_id
        self._origin = origin
        self._triggered_by = triggered_by
        self._block_id = block_id
        self._query_parameters = query_parameters
        self._saved_tables: list[dict[str, Any]] = []

    @property
    def saved_tables(self) -> list[dict[str, Any]]:
        """Tables materialized via ``save_table`` during this run, in save order."""
        return list(self._saved_tables)

    def provenance(self) -> ArtifactProvenance:
        """Run-level provenance for artifacts produced by this execution.

        The job payloads embed this on the result envelope, and ``save_table``
        uses it (plus the table title) for each materialized table, so both
        surfaces stamp the same origin/actor/run/block identity.
        """
        # The schema's id fields are strict strings; JobContext may carry a
        # UUID (or a test double), so normalize here instead of leaking a
        # validation error into the job result.
        run_id = self._context.job_run_id
        execution_run_id = str(run_id) if isinstance(run_id, UUID | str) and run_id else None
        return ArtifactProvenance(
            origin=self._origin,
            created_by=self._triggered_by,
            execution_run_id=execution_run_id,
            chat_session_id=self._chat_session_id,
            block_id=self._block_id,
        )

    async def execute_sql(self, sql: str, title: str | None = None) -> DataTable:
        parameters = self._query_parameters
        if parameters is None:
            raise ValueError(
                "SQL execution is not available in notebook block execution. "
                "Keep notebook code portable: load data with "
                "`await kontext.load_data(...)` and use the SQL tool for query work."
            )

        normalized_sql = normalize_read_only_sql(sql)
        query_session_service = self._context.get_query_session_service()
        runtime_provider = self._context.get_runtime_provider()
        effective_engine_type = resolve_query_engine_type(parameters.engine_type)

        effective_session_id = await query_session_service.get_or_create_session(
            project_id=str(self._context.project_id),
            session_id=parameters.query_session_id,
            catalog_connection_id=parameters.catalog_connection_id,
            default_namespace=parameters.default_namespace,
            default_entity_id=parameters.default_entity_id,
            session_name="Managed Python SQL",
            engine_type=effective_engine_type.value,
        )

        engine = runtime_provider.get_query_execution_engine(
            effective_engine_type,
            request=QueryEngineRequest(
                project_id=str(self._context.project_id),
                session_id=effective_session_id,
                catalog_connection_id=parameters.catalog_connection_id,
                default_namespace=parameters.default_namespace,
                default_entity_id=parameters.default_entity_id,
            ),
            query_session_service=query_session_service,
        )
        if engine is None:
            raise RuntimeError(
                "Query execution engine is not available for managed Python SQL execution."
            )

        await self._context.log_info(
            "Executing managed Python SQL query",
            {
                "Title": title,
                "QuerySessionId": effective_session_id,
                "EngineType": effective_engine_type.value,
            },
        )

        await engine.connect()
        try:
            is_valid, error_message = await engine.validate_sql(normalized_sql)
            if not is_valid:
                raise ValueError(error_message or "SQL validation failed.")

            table = await engine.fetch_data_table(
                normalized_sql,
                max_rows=_PYTHON_SQL_MAX_ROWS + 1,
            )
        finally:
            await engine.dispose()

        if (table.row_count or 0) > _PYTHON_SQL_MAX_ROWS:
            raise ValueError(
                "Managed Python SQL queries may return at most "
                f"{_PYTHON_SQL_MAX_ROWS} rows. Add a tighter `LIMIT` or use "
                "the SQL tool "
                "to create a durable reusable `data_id` first."
            )

        return table

    async def save_table(self, content: dict[str, Any]) -> dict[str, Any]:
        """Materialize a kernel-side table as a durable data-table artifact.

        Kernel code hands over base64-encoded Parquet bytes (see the kernel
        adapter); the file service materializes them without a full decode,
        then the artifact is linked to the chat session so it appears in the
        session's artifact panel.
        """
        import pyarrow.parquet as parquet

        encoded = content.get("data") if isinstance(content, dict) else None
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("save_table requires a table payload.")
        raw = base64.b64decode(encoded)
        if len(raw) > _SAVE_TABLE_MAX_PARQUET_BYTES:
            raise ValueError(
                "save_table payloads may be at most "
                f"{_SAVE_TABLE_MAX_PARQUET_BYTES // (1024 * 1024)} MiB of "
                "serialized table data. Save a sampled or narrowed frame."
            )

        title = content.get("title") if isinstance(content, dict) else None
        effective_title = str(title).strip() if title and str(title).strip() else "Python Result"

        # Read only the footer here: the row store and preview are built by the
        # file service from the original bytes, so large frames never round-trip
        # through row objects.
        reader = parquet.ParquetFile(io.BytesIO(raw))
        total_rows = int(reader.metadata.num_rows)
        if total_rows > _SAVE_TABLE_MAX_ROWS:
            raise ValueError(
                f"save_table supports at most {_SAVE_TABLE_MAX_ROWS} rows; "
                f"the frame has {total_rows}. Save a sampled frame instead."
            )

        file_service = self._context.get_file_service()
        if file_service is None:
            raise RuntimeError(
                "File service is not available in this execution context; "
                "save_table cannot materialize durable tables."
            )

        provenance = self.provenance()
        materialized_id = await file_service.materialize_parquet_inline_data(
            project_id=self._context.project_id or "",
            parquet_bytes=raw,
            name=effective_title,
            chat_session_id=self._chat_session_id,
            sql=None,
            provenance=provenance,
        )
        if not materialized_id:
            raise RuntimeError("save_table could not materialize a durable data table.")

        self._saved_tables.append(
            {
                "dataTableId": materialized_id,
                "rowCount": total_rows,
                "title": effective_title,
            }
        )
        await self._link_saved_table(
            artifact_id=materialized_id,
            title=effective_title,
            provenance=provenance,
        )
        await self._context.log_info(
            "Managed Python saved a data table",
            {
                "DataTableId": materialized_id,
                "Title": effective_title,
                "RowCount": total_rows,
                "Origin": str(self._origin),
            },
        )
        return {
            "dataTableId": materialized_id,
            "rowCount": total_rows,
            "title": effective_title,
        }

    async def _link_saved_table(
        self, *, artifact_id: str, title: str, provenance: ArtifactProvenance
    ) -> None:
        """Link the saved table to the chat session artifact panel, best-effort."""
        chat_session_id = self._chat_session_id
        if not chat_session_id:
            return
        try:
            chat_session_service = self._context.get_runtime_provider().get_chat_session_service()
        except Exception:
            chat_session_service = None
        if chat_session_service is None:
            return

        with suppress(Exception):
            await chat_session_service.upsert_artifact(
                session_id=chat_session_id,
                artifact_id=artifact_id,
                artifact_type=ArtifactType.DATATABLE,
                title=title,
                meta={"provenance": provenance.model_dump(by_alias=True, exclude_none=True)},
            )
