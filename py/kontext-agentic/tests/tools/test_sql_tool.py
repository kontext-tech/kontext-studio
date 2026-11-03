"""
Simple tests for SQL tool placeholder functionality.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agent import (
    KONTEXT_SESSION_NAMESPACE,
    SharedSessionStore,
    create_kontext_session_state,
)
from kontext.agentic.tools.sql_tool import (
    DEFAULT_SAMPLE_ROWS,
    MAX_BATCH_STATEMENTS,
    SAMPLE_CELL_CHARS,
    SqlTools,
)
from kontext.common.constants import QueryConstants
from kontext.common.query.engine import QueryEngineRequest
from kontext.schema import (
    ArtifactType,
    ChatSessionModel,
    DataColumn,
    DataTable,
    InlineData,
    QueryEngineType,
)

if TYPE_CHECKING:
    from kontext.agent import RuntimeToolContext


class TestRuntimeContext:
    def __init__(self, session_state: dict[str, Any] | None = None):
        self.session_state = session_state

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.any_schema()


class TestSqlToolsBasic:
    """Basic test cases for simplified SQL tool."""

    @pytest.mark.unit
    def test_sql_tool_initialization(self, mock_service_provider, sample_project):
        """Test SQL tool can be initialized properly."""
        sql_tool = SqlTools(project=sample_project, runtime_provider=mock_service_provider)
        assert sql_tool is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_query_placeholder(self, mock_service_provider, sample_project):
        """Test SQL query execution returns result."""
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",  # Provide session_id to skip session creation
        )

        result_json = await sql_tool.execute_sql(sql="SELECT * FROM test_table")

        result = json.loads(result_json)
        assert result["success"] is True
        assert "Query executed successfully" in result["message"]
        assert result["executionTimeMs"] > 0
        assert result["dataRef"]["dataId"] == "2eb96811-39fe-47a4-7e25-08de0be1d151"

        # Verify preview structure
        assert result["preview"] is not None
        table = result["preview"]["table"]
        assert table is not None
        assert table["rows"] == [["data"]]
        mock_service_provider.get_file_service.return_value.materialize_inline_data.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_different_queries(self, mock_service_provider, sample_project):
        """Test that multiple SQL queries execute successfully."""
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",  # Provide session_id to skip session creation
        )
        queries = [
            "SELECT 1",
            "SELECT 2",
            "SELECT COUNT(*) FROM fake_table",
            "SELECT 'hello'",
        ]

        for query in queries:
            result_json = await sql_tool.execute_sql(sql=query)
            result = json.loads(result_json)
            assert result["success"] is True
            assert result["dataRef"] is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_delegates_session_resolution_to_service(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        """Toolkit should pass explicit session context to the shared resolver."""
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
            catalog_connection_id="00000000-0000-0000-0000-00000000000a",
            default_namespace="bronze",
            default_entity_id="00000000-0000-0000-0000-00000000000b",
        )

        await sql_tool.execute_sql(sql="SELECT 1")

        mock_query_session_service.get_or_create_session.assert_called_once_with(
            project_id=sample_project.id,
            session_id="550e8400-e29b-41d4-a716-446655440000",
            catalog_connection_id="00000000-0000-0000-0000-00000000000a",
            default_namespace="bronze",
            default_entity_id="00000000-0000-0000-0000-00000000000b",
            session_name="Agent Session",
            engine_type=None,
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_forwards_chat_and_parent_run_linkage(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
            chat_session_id="550e8400-e29b-41d4-a716-446655440001",
        )
        session_state = create_kontext_session_state()
        session_state[KONTEXT_SESSION_NAMESPACE]["current_execution_run_id"] = (
            "550e8400-e29b-41d4-a716-446655440002"
        )
        run_context: RuntimeToolContext = TestRuntimeContext(session_state=session_state)

        await sql_tool.execute_sql(sql="SELECT 1", run_context=run_context)

        mock_query_session_service.execute_sql_with_session_management.assert_awaited_once()
        execute_kwargs = (
            mock_query_session_service.execute_sql_with_session_management.await_args.kwargs
        )
        assert execute_kwargs["chat_session_id"] == "550e8400-e29b-41d4-a716-446655440001"
        assert execute_kwargs["parent_run_id"] == "550e8400-e29b-41d4-a716-446655440002"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_hydrates_missing_scope_from_chat_session(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        chat_session_service = MagicMock()
        chat_session_service.get_session = AsyncMock(
            return_value=ChatSessionModel.model_construct(
                id="550e8400-e29b-41d4-a716-446655440010",
                project_id=sample_project.id,
                session_name="Chat Session",
                date_created=datetime.now(UTC),
                python_execution_approval_mode="auto",
                is_deleted=False,
                query_session_id="550e8400-e29b-41d4-a716-446655440011",
                default_catalog_connection_id="550e8400-e29b-41d4-a716-446655440012",
                default_namespace="sales",
                default_entity_id="550e8400-e29b-41d4-a716-446655440013",
                engine_type="sqlserver",
            )
        )
        mock_service_provider.get_chat_session_service.return_value = chat_session_service

        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            chat_session_id="550e8400-e29b-41d4-a716-446655440010",
        )

        await sql_tool.execute_sql(sql="SELECT 1")

        mock_query_session_service.get_or_create_session.assert_called_once_with(
            project_id=sample_project.id,
            session_id="550e8400-e29b-41d4-a716-446655440011",
            catalog_connection_id="550e8400-e29b-41d4-a716-446655440012",
            default_namespace="sales",
            default_entity_id="550e8400-e29b-41d4-a716-446655440013",
            session_name="Agent Session",
            engine_type=QueryEngineType.SQLSERVER,
        )
        execute_kwargs = (
            mock_query_session_service.execute_sql_with_session_management.await_args.kwargs
        )
        assert execute_kwargs["catalog_connection_id"] == "550e8400-e29b-41d4-a716-446655440012"
        assert execute_kwargs["default_namespace"] == "sales"
        assert execute_kwargs["default_entity_id"] == "550e8400-e29b-41d4-a716-446655440013"
        assert execute_kwargs["engine_type"] == QueryEngineType.SQLSERVER

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_relinks_chat_to_repaired_query_session(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        repaired_session_id = "550e8400-e29b-41d4-a716-446655440099"
        mock_query_session_service.get_or_create_session = AsyncMock(
            return_value=repaired_session_id
        )

        chat_session_service = MagicMock()
        chat_session_service.get_session = AsyncMock(
            return_value=ChatSessionModel.model_construct(
                id="550e8400-e29b-41d4-a716-446655440010",
                project_id=sample_project.id,
                session_name="Chat Session",
                date_created=datetime.now(UTC),
                python_execution_approval_mode="auto",
                is_deleted=False,
                query_session_id="550e8400-e29b-41d4-a716-446655440011",
                default_catalog_connection_id="550e8400-e29b-41d4-a716-446655440012",
                engine_type="sqlserver",
            )
        )
        chat_session_service.update_session = AsyncMock()
        mock_service_provider.get_chat_session_service.return_value = chat_session_service

        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            chat_session_id="550e8400-e29b-41d4-a716-446655440010",
        )

        await sql_tool.execute_sql(sql="SELECT 1")

        chat_session_service.update_session.assert_awaited_once()
        update_kwargs = chat_session_service.update_session.await_args.kwargs
        assert update_kwargs["session_id"] == "550e8400-e29b-41d4-a716-446655440010"
        assert update_kwargs["request"].query_session_id == repaired_session_id

    @pytest.mark.integration
    @pytest.mark.slow
    async def test_sql_tool_integration_placeholder(self):
        """Integration test placeholder - for when real services are available."""
        # This will be implemented when we integrate with real Kontext services
        pytest.skip("Integration tests not yet implemented - waiting for real service integration")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_sql_returns_success_for_valid_sql(
        self, mock_service_provider, sample_project
    ):
        """Test SQL validation returns success=True for valid SQL."""
        mock_engine = AsyncMock()
        mock_engine.validate_sql.return_value = (True, None)
        mock_service_provider.get_query_execution_engine.return_value = mock_engine

        sql_tool = SqlTools(project=sample_project, runtime_provider=mock_service_provider)
        result_json = await sql_tool.validate_sql(sql="SELECT * FROM valid_table")

        result = json.loads(result_json)
        assert result["success"] is True
        assert "valid" in result["message"]
        mock_engine.validate_sql.assert_called_once_with("SELECT * FROM valid_table")
        mock_service_provider.get_query_execution_engine.assert_called_once_with(
            QueryEngineType.DUCKDB,
            request=QueryEngineRequest(
                project_id=sample_project.id,
                shadow=True,
            ),
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_sql_returns_failure_for_invalid_sql(
        self, mock_service_provider, sample_project
    ):
        """Test SQL validation returns success=False for invalid SQL."""
        mock_engine = AsyncMock()
        mock_engine.validate_sql.return_value = (False, "Table 'invalid_table' does not exist")
        mock_service_provider.get_query_execution_engine.return_value = mock_engine

        sql_tool = SqlTools(project=sample_project, runtime_provider=mock_service_provider)

        result_json = await sql_tool.validate_sql(sql="SELECT * FROM invalid_table")

        result = json.loads(result_json)

        # Ensure the error message from the tool is surfaced
        assert result["success"] is False
        assert "invalid_table" in result["message"]
        mock_engine.validate_sql.assert_called_once_with("SELECT * FROM invalid_table")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_validate_sql_returns_failure_on_exception(
        self, mock_service_provider, sample_project
    ):
        """Test SQL validation returns success=False when validation raises an exception."""
        mock_engine = AsyncMock()
        mock_engine.validate_sql.side_effect = Exception("Validation setup failed")
        mock_service_provider.get_query_execution_engine.return_value = mock_engine

        sql_tool = SqlTools(project=sample_project, runtime_provider=mock_service_provider)

        result_json = await sql_tool.validate_sql(sql="SELECT * FROM test_table")

        result = json.loads(result_json)

        assert result["success"] is False
        assert "Validation setup failed" in result["message"]
        mock_engine.validate_sql.assert_called_once_with("SELECT * FROM test_table")

    @pytest.mark.unit
    @pytest.mark.asyncio
    def test_sql_tool_does_not_expose_search_schema(self, mock_service_provider, sample_project):
        """SQL tool surface should not duplicate catalog search tooling."""
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
        )

        tool_names = [tool.__name__ for tool in sql_tool.get_tool_callables()]

        assert "search_schema" not in tool_names
        assert tool_names == [
            "execute_sql",
            "execute_sql_batch",
            "validate_sql",
            "validate_sql_batch",
            "show_data_table",
            "query_result_slice",
            "sample_records",
            "sample_records_batch",
        ]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_forwards_title_as_store_result_name(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        """The tool title should name the persisted result file, not fall back to query-result."""
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )

        await sql_tool.execute_sql(sql="SELECT 1", title="Transactions by type")

        execute_kwargs = (
            mock_query_session_service.execute_sql_with_session_management.await_args.kwargs
        )
        assert execute_kwargs["store_result_name"] == "Transactions by type"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_show_data_table_does_not_clobber_artifact_title_or_meta(
        self, mock_service_provider, sample_project
    ):
        """Re-showing a persisted table must preserve its existing title and provenance."""
        data_id = "8b9e2545-1e90-49ec-a1a1-dd19515ad3ca"
        inline_data = InlineData(
            title="Transactions by type",
            table=DataTable(
                columns=[DataColumn(name="type", type="VARCHAR")],
                rows=[["Deposit"]],
                row_count=1,
            ),
        )

        file_service = mock_service_provider.get_file_service.return_value
        file_service.exists_by_id = AsyncMock(return_value=True)
        file_service.get_file_content = AsyncMock(
            return_value=inline_data.model_dump_json(by_alias=True).encode("utf-8")
        )

        chat_session_service = MagicMock()
        chat_session_service.upsert_artifact = AsyncMock()
        mock_service_provider.get_chat_session_service.return_value = chat_session_service

        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
            chat_session_id="550e8400-e29b-41d4-a716-446655440001",
        )

        await sql_tool.show_data_table(data_table_id=data_id)

        chat_session_service.upsert_artifact.assert_awaited_once()
        upsert_kwargs = chat_session_service.upsert_artifact.await_args.kwargs
        assert upsert_kwargs["artifact_id"] == data_id
        assert upsert_kwargs["title"] is None
        assert upsert_kwargs["meta"] is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_query_result_slice_reads_row_store_window(
        self, mock_service_provider, sample_project
    ):
        """The retrieval tool returns a bounded window from the materialized store."""
        data_id = "8b9e2545-1e90-49ec-a1a1-dd19515ad3ca"
        window = InlineData(
            title="Transactions by type",
            table=DataTable(
                columns=[DataColumn(name="type", type="VARCHAR")],
                rows=[["a"], ["b"]],
                row_count=10,
            ),
        )

        file_service = mock_service_provider.get_file_service.return_value
        file_service.exists_by_id = AsyncMock(return_value=True)
        file_service.get_inline_data_rows = AsyncMock(return_value=window)

        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )

        result_json = await sql_tool.query_result_slice(data_table_id=data_id, offset=3, limit=2)
        result = json.loads(result_json)

        assert result["success"] is True
        file_service.get_inline_data_rows.assert_awaited_once()
        await_args = file_service.get_inline_data_rows.await_args
        assert await_args is not None
        slice_kwargs = await_args.kwargs
        assert slice_kwargs["offset"] == 3
        assert slice_kwargs["limit"] == 2
        assert result["preview"]["table"]["rows"] == [["a"], ["b"]]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_registers_shared_descriptor(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        mock_query_session_service.execute_sql_with_session_management.return_value.data_id = (
            "1eb96811-39fe-47a4-7e25-08de0be1d151"
        )

        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )
        run_context: RuntimeToolContext = TestRuntimeContext(session_state={})

        result_json = await sql_tool.execute_sql(
            sql="SELECT * FROM transactions",
            run_context=run_context,
        )

        result = json.loads(result_json)
        session_state = run_context.session_state
        assert session_state is not None
        descriptor = session_state["kontext"]["artifacts_by_id"][
            "1eb96811-39fe-47a4-7e25-08de0be1d151"
        ]

        assert result["success"] is True
        assert descriptor["artifact_type"] == "DataTable"
        assert descriptor["sql"] == "SELECT * FROM transactions"
        assert descriptor["row_count"] == 1
        assert descriptor["column_names"] == ["placeholder"]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_without_reuse_still_registers_durable_descriptor(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        mock_query_session_service.execute_sql_with_session_management.return_value.data_id = (
            "1eb96811-39fe-47a4-7e25-08de0be1d151"
        )

        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )
        run_context: RuntimeToolContext = TestRuntimeContext(session_state={})

        result_json = await sql_tool.execute_sql(
            sql="SELECT * FROM transactions",
            run_context=run_context,
        )

        result = json.loads(result_json)
        session_state = run_context.session_state
        assert session_state is not None

        assert result["success"] is True
        descriptor = session_state["kontext"]["artifacts_by_id"][
            "1eb96811-39fe-47a4-7e25-08de0be1d151"
        ]
        assert descriptor["artifact_type"] == "DataTable"
        assert descriptor["sql"] == "SELECT * FROM transactions"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_without_reuse_promotes_preview_result(
        self, mock_service_provider, sample_project
    ):
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )
        run_context: RuntimeToolContext = TestRuntimeContext(session_state={})

        result_json = await sql_tool.execute_sql(
            sql="SELECT * FROM transactions",
            run_context=run_context,
        )

        result = json.loads(result_json)
        session_state = run_context.session_state
        assert session_state is not None

        assert result["success"] is True
        assert result["dataRef"]["dataId"] == "2eb96811-39fe-47a4-7e25-08de0be1d151"
        assert "Durable `data_table_id` is available for downstream reuse." in result["message"]
        descriptor = session_state["kontext"]["artifacts_by_id"][
            "2eb96811-39fe-47a4-7e25-08de0be1d151"
        ]
        assert descriptor["artifact_type"] == "DataTable"
        assert descriptor["sql"] == "SELECT * FROM transactions"
        mock_service_provider.get_file_service.return_value.materialize_inline_data.assert_awaited_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_without_reuse_reuses_existing_identity_artifact(
        self, mock_service_provider, sample_project
    ):
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )
        session_state = create_kontext_session_state()
        store = SharedSessionStore(session_state)
        identity_key = sql_tool.build_data_identity_key("SELECT * FROM transactions")
        store.upsert_artifact_descriptor(
            artifact_id="33333333-3333-4333-8333-333333333333",
            artifact_type=ArtifactType.DATATABLE,
            title="Transactions",
            sql="SELECT * FROM transactions",
            identity_key=identity_key,
            row_count=1,
            column_names=["placeholder"],
        )
        run_context: RuntimeToolContext = TestRuntimeContext(session_state=session_state)

        result_json = await sql_tool.execute_sql(
            sql="SELECT * FROM transactions",
            run_context=run_context,
        )

        result = json.loads(result_json)

        assert result["success"] is True
        assert result["dataRef"]["dataId"] == "33333333-3333-4333-8333-333333333333"
        mock_service_provider.get_file_service.return_value.materialize_inline_data.assert_not_awaited()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_execute_sql_save_for_reuse_promotes_preview_result(
        self, mock_service_provider, sample_project
    ):
        sql_tool = SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )
        run_context: RuntimeToolContext = TestRuntimeContext(session_state={})

        result_json = await sql_tool.execute_sql(
            sql="SELECT * FROM transactions",
            run_context=run_context,
        )

        result = json.loads(result_json)
        session_state = run_context.session_state
        assert session_state is not None

        assert result["success"] is True
        assert result["dataRef"]["dataId"] == "2eb96811-39fe-47a4-7e25-08de0be1d151"
        assert "Durable `data_table_id` is available for downstream reuse." in result["message"]
        descriptor = session_state["kontext"]["artifacts_by_id"][
            "2eb96811-39fe-47a4-7e25-08de0be1d151"
        ]
        assert descriptor["artifact_type"] == "DataTable"
        assert descriptor["sql"] == "SELECT * FROM transactions"
        mock_service_provider.get_file_service.return_value.materialize_inline_data.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_execute_sql_batch_aggregates_results(mock_service_provider, sample_project):
    sql_tool = SqlTools(
        project=sample_project,
        runtime_provider=mock_service_provider,
        session_id="550e8400-e29b-41d4-a716-446655440000",
    )

    payload = json.loads(
        await sql_tool.execute_sql_batch(statements=["SELECT 1", "SELECT 2"], title="Explore")
    )

    assert payload["success"] is True
    assert payload["type"] == "sql_execution_batch"
    assert payload["resultsCount"] == 2
    assert payload["failedCount"] == 0
    assert all(result["success"] for result in payload["results"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_sql_batch_validates_each_statement(mock_service_provider, sample_project):
    mock_engine = AsyncMock()
    mock_engine.validate_sql.return_value = (True, None)
    mock_service_provider.get_query_execution_engine.return_value = mock_engine

    sql_tool = SqlTools(project=sample_project, runtime_provider=mock_service_provider)

    payload = json.loads(await sql_tool.validate_sql_batch(statements=["SELECT 1", "SELECT 2"]))

    assert payload["success"] is True
    assert payload["type"] == "sql_validation_batch"
    assert payload["resultsCount"] == 2
    assert mock_engine.validate_sql.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_batch_sql_tools_reject_empty_and_oversized_input(
    mock_service_provider, sample_project
):
    sql_tool = SqlTools(project=sample_project, runtime_provider=mock_service_provider)

    empty = json.loads(await sql_tool.execute_sql_batch(statements=[]))
    assert empty["success"] is False
    assert empty["resultsCount"] == 0

    oversized = json.loads(
        await sql_tool.execute_sql_batch(statements=["SELECT 1"] * (MAX_BATCH_STATEMENTS + 1))
    )
    assert oversized["success"] is False
    assert "Too many" in oversized["message"]


class TestSampleRecordsTools:
    """Peek-only CSV sampling: no artifacts, no handles, no UI actions."""

    @staticmethod
    def _response(rows=None, columns=None, *, success=True, error_message=None, row_count=None):
        return SimpleNamespace(
            success=success,
            error_message=error_message,
            total_execution_time_ms=12,
            result=SimpleNamespace(
                success=success,
                columns=columns or [],
                rows=rows or [],
                row_count=row_count if row_count is not None else len(rows or []),
                data_id=None,
            ),
            data_id=None,
        )

    @staticmethod
    def _tool(mock_service_provider, sample_project) -> SqlTools:
        return SqlTools(
            project=sample_project,
            runtime_provider=mock_service_provider,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        )

    def test_prepare_sample_sql_clamps_and_appends_limit(self):
        prepare = SqlTools._prepare_sample_sql
        assert prepare("SELECT * FROM users", 20) == "SELECT * FROM users LIMIT 20"
        assert prepare("SELECT * FROM users;", 20) == "SELECT * FROM users LIMIT 20"
        assert prepare("SELECT * FROM t LIMIT 900", 20) == "SELECT * FROM t LIMIT 20"
        assert (
            prepare("SELECT * FROM t LIMIT 900 OFFSET 10", 20)
            == "SELECT * FROM t LIMIT 20 OFFSET 10"
        )
        assert prepare("SELECT * FROM t LIMIT 5", 20) == "SELECT * FROM t LIMIT 5"
        cte = "WITH x AS (SELECT 1) SELECT * FROM x"
        assert prepare(cte, 20) == f"{cte} LIMIT 20"
        sub = "SELECT * FROM (SELECT * FROM x LIMIT 3) s"
        assert prepare(sub, 20) == f"{sub} LIMIT 20"

    def test_prepare_sample_sql_leaves_mysql_comma_form_alone(self):
        sql = "SELECT * FROM t LIMIT 100, 5"
        assert SqlTools._prepare_sample_sql(sql, 20) == sql

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_returns_csv_without_artifacts(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        service.execute_sql_with_session_management = AsyncMock(
            return_value=self._response(
                rows=[["1", "acme"], ["2", "globex"]],
                columns=[
                    DataColumn(name="id", type="integer"),
                    DataColumn(name="name", type="string"),
                ],
            )
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        result = await sql_tool.sample_records(sql="SELECT * FROM customers")

        lines = result.splitlines()
        assert lines[0] == "-- sampled 2 of 2 rows in 12ms"
        assert lines[1] == "id,name"
        assert lines[2] == "1,acme"
        assert lines[3] == "2,globex"
        # peek only: execution is clamped, never persisted, no artifact work
        await_args = service.execute_sql_with_session_management.await_args
        assert await_args is not None
        execute_kwargs = await_args.kwargs
        assert execute_kwargs["sql_query"] == "SELECT * FROM customers LIMIT 20"
        assert execute_kwargs["store_result_threshold_rows"] == QueryConstants.MAX_FETCH_ROWS
        mock_service_provider.get_file_service.return_value.materialize_inline_data.assert_not_awaited()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_reports_hidden_rows(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        service.execute_sql_with_session_management = AsyncMock(
            return_value=self._response(
                rows=[[str(i)] for i in range(10)],
                columns=[DataColumn(name="id", type="integer")],
            )
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        result = await sql_tool.sample_records(sql="SELECT id FROM big_table", limit=3)

        assert result.startswith("-- sampled 3 of 10 rows")
        assert "-- 7 of 10 rows not shown (sample limit)" in result
        await_args = service.execute_sql_with_session_management.await_args
        assert await_args is not None
        assert await_args.kwargs["sql_query"] == "SELECT id FROM big_table LIMIT 3"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_default_limit_caps_rows(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        service.execute_sql_with_session_management = AsyncMock(
            return_value=self._response(
                rows=[[str(i)] for i in range(40)],
                columns=[DataColumn(name="id", type="integer")],
            )
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        result = await sql_tool.sample_records(sql="SELECT id FROM t")

        assert result.startswith(f"-- sampled {DEFAULT_SAMPLE_ROWS} of 40 rows")
        assert f"-- {40 - DEFAULT_SAMPLE_ROWS} of 40 rows not shown (sample limit)" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_truncates_long_cells(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        long_value = "x" * 500
        service.execute_sql_with_session_management = AsyncMock(
            return_value=self._response(
                rows=[["1", long_value]],
                columns=[
                    DataColumn(name="id", type="integer"),
                    DataColumn(name="blob", type="string"),
                ],
            )
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        result = await sql_tool.sample_records(sql="SELECT id, blob FROM t")

        assert "x" * SAMPLE_CELL_CHARS in result
        assert long_value not in result
        assert "…" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_respects_character_budget(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        service.execute_sql_with_session_management = AsyncMock(
            return_value=self._response(
                rows=[["y" * 300, "z" * 300] for _ in range(30)],
                columns=[DataColumn(name="a", type="string"), DataColumn(name="b", type="string")],
            )
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        result = await sql_tool.sample_records(sql="SELECT a, b FROM wide", limit=30)

        assert "-- truncated:" in result
        assert result.count("\n") < 12  # fewer rows than requested, budget stopped early

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_zero_rows(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        service.execute_sql_with_session_management = AsyncMock(
            return_value=self._response(rows=[], columns=[DataColumn(name="id", type="integer")])
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        result = await sql_tool.sample_records(sql="SELECT id FROM empty_table")

        assert result.startswith("-- sampled 0 of 0 rows")
        assert "id" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_execution_error(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        service.execute_sql_with_session_management = AsyncMock(
            return_value=self._response(success=False, error_message="relation does not exist")
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        result = await sql_tool.sample_records(sql="SELECT * FROM missing")

        assert result == "-- error: relation does not exist"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_batch_tags_blocks_and_continues_on_error(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        service.execute_sql_with_session_management = AsyncMock(
            side_effect=[
                self._response(rows=[["1"]], columns=[DataColumn(name="id", type="integer")]),
                self._response(success=False, error_message='relation "orederz" does not exist'),
            ]
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        result = await sql_tool.sample_records_batch(
            statements=["SELECT * FROM customers", "SELECT * FROM orederz"], limit=5
        )

        assert "-- sample batch rejected" not in result
        assert "-- [1/2] SELECT * FROM customers" in result
        assert "id\n1" in result
        assert "-- [2/2] SELECT * FROM orederz" in result
        assert '-- error: relation "orederz" does not exist' in result
        assert service.execute_sql_with_session_management.await_count == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_batch_budget_skips_rest(
        self, mock_service_provider, mock_query_session_service, sample_project
    ):
        service = mock_query_session_service
        service.execute_sql_with_session_management = AsyncMock(
            return_value=self._response(
                rows=[["y" * 300, "z" * 300] for _ in range(30)],
                columns=[DataColumn(name="a", type="string"), DataColumn(name="b", type="string")],
            )
        )
        sql_tool = self._tool(mock_service_provider, sample_project)

        statements = [f"SELECT a, b FROM table_{i}" for i in range(6)]
        result = await sql_tool.sample_records_batch(statements=statements, limit=30)

        assert "-- skipped statements 5-6" in result
        assert "-- [4/6]" in result
        assert "-- [5/6]" not in result
        assert service.execute_sql_with_session_management.await_count == 4

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_sample_records_batch_rejects_bad_input(
        self, mock_service_provider, sample_project
    ):
        sql_tool = self._tool(mock_service_provider, sample_project)

        empty = await sql_tool.sample_records_batch(statements=[])
        assert empty == "-- sample batch rejected: No statements provided."

        oversized = await sql_tool.sample_records_batch(
            statements=["SELECT 1"] * (MAX_BATCH_STATEMENTS + 1)
        )
        assert oversized == (
            f"-- sample batch rejected: Too many statements ({MAX_BATCH_STATEMENTS + 1}); "
            f"sample at most {MAX_BATCH_STATEMENTS} per call."
        )
