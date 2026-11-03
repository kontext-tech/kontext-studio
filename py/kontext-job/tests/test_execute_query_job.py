"""
Tests for ExecuteQueryJob.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kontext.common.protocols import ExecutionRunProvenance
from kontext.jobs.job_context import JobContext
from kontext.query.jobs.execute_query_job import (
    ExecuteQueryJob,
    _resolve_chat_session_id,
)
from kontext.schema import DataColumn, DataTable, QueryEngineType, QuerySessionModel


@pytest.mark.asyncio
async def test_resolve_chat_session_id_reads_run_context():
    chat_session_id = uuid.uuid4()
    context = MagicMock(spec=JobContext)
    context.job_run_id = str(uuid.uuid4())
    context.get_execution_run_context_service = MagicMock(
        return_value=SimpleNamespace(
            get_run_provenance=AsyncMock(
                return_value=ExecutionRunProvenance(
                    run_id=context.job_run_id,
                    chat_session_id=str(chat_session_id),
                )
            )
        )
    )

    resolved = await _resolve_chat_session_id(context)

    assert resolved == str(chat_session_id)


@pytest.mark.asyncio
async def test_resolve_chat_session_id_returns_none_without_context():
    context = MagicMock(spec=JobContext)
    context.job_run_id = str(uuid.uuid4())
    context.get_execution_run_context_service = MagicMock(
        return_value=SimpleNamespace(get_run_provenance=AsyncMock(return_value=None))
    )

    resolved = await _resolve_chat_session_id(context)

    assert resolved is None


class TestExecuteQueryJob:
    """Test cases for ExecuteQueryJob."""

    @pytest.fixture
    def job(self):
        """Create ExecuteQueryJob instance."""
        return ExecuteQueryJob()

    @pytest.fixture
    def mock_context(self):
        """Create mock JobContext."""
        context = MagicMock(spec=JobContext)
        context.project_id = str(uuid.uuid4())
        context.job_run_id = str(uuid.uuid4())
        context.log_info = AsyncMock()
        context.log_debug = AsyncMock()
        context.log_error = AsyncMock()
        context.log_warning = AsyncMock()
        context.update_progress = AsyncMock()
        context.get_runtime_provider = MagicMock()
        context.get_file_service = MagicMock()
        context.get_query_session_service = MagicMock(return_value=None)
        return context

    @pytest.fixture
    def mock_data_table(self):
        """Create a mock DataTable."""
        return DataTable(
            columns=[
                DataColumn(name="id", type="INTEGER"),
                DataColumn(name="name", type="VARCHAR"),
            ],
            rows=[[1, "test"]],
        )

    def test_job_metadata(self, job):
        """Test job metadata is correctly defined."""
        metadata = job.get_job_metadata()

        assert metadata.type == "python.jobs.ExecuteQueryJob"
        assert metadata.name == "Execute Query"
        assert metadata.description == "Executes a SQL query in a query session"
        assert metadata.is_system_job is True

        # Check parameters
        param_names = [p.name for p in metadata.parameters]
        assert "catalog_connection_id" in param_names
        assert "sql" in param_names
        assert "session_id" in param_names
        assert "query_timeout_seconds" in param_names

        # Check required parameters
        required_params = [p.name for p in metadata.parameters if p.required]
        assert "sql" in required_params
        assert "default_namespace" in param_names

    @pytest.mark.asyncio
    async def test_execute_job_missing_project_id(self, job, mock_context):
        """Test job fails when project_id is missing."""
        mock_context.project_id = None

        result = await job.execute(mock_context, {"sql": "SELECT 1"})

        assert result.success is False
        assert "Project ID not available" in result.message

    @pytest.mark.asyncio
    async def test_execute_job_missing_query(self, job, mock_context):
        """Test job fails when query parameter is missing."""
        result = await job.execute(mock_context, {})

        assert result.success is False
        # Pydantic validation error for missing required field
        assert "Parameter validation failed" in result.message

    def test_params_reject_provenance_only_keys(self, job):
        """Provenance must not be smuggled through the queue as job params.

        The chat session id is recovered from the persisted execution-run
        context instead, so it must not appear as an accepted parameter.
        """
        param_names = [p.name for p in job.get_job_metadata().parameters]
        assert "chat_session_id" not in param_names

    @pytest.mark.asyncio
    async def test_execute_job_invalid_uuid(self, job, mock_context):
        """Test job fails with invalid UUID parameters."""
        result = await job.execute(
            mock_context, {"sql": "SELECT 1", "catalog_connection_id": "invalid-uuid"}
        )

        assert result.success is False
        # Pydantic validation error for invalid UUID
        assert "Parameter validation failed" in result.message

    @pytest.mark.asyncio
    async def test_execute_job_invalid_timeout(self, job, mock_context):
        """Test job fails with invalid timeout parameter."""
        result = await job.execute(mock_context, {"sql": "SELECT 1", "query_timeout_seconds": 4000})

        assert result.success is False
        # Pydantic validation error
        assert "Parameter validation failed" in result.message

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    async def test_execute_job_successful_query(
        self, mock_resolve_engine, job, mock_context, mock_data_table
    ):
        """Test successful query execution."""
        mock_engine = AsyncMock()
        mock_engine.connect = AsyncMock()
        mock_engine.fetch_data_table = AsyncMock(return_value=mock_data_table)
        mock_engine.dispose = AsyncMock()
        mock_resolve_engine.return_value = mock_engine

        result = await job.execute(mock_context, {"sql": "SELECT 1 as id, 'test' as name"})

        assert result.success is True
        assert "Query executed successfully" in result.message
        assert result.data is not None

        # Verify the response structure (it's a dict because JobResult.data is Any)
        response_data = result.data
        assert "result" in response_data
        assert "totalExecutionTimeMs" in response_data
        assert "success" in response_data
        assert response_data["success"] is True

        # Verify engine resolution
        mock_resolve_engine.assert_called_once()

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    async def test_execute_job_with_catalog_scope(
        self, mock_resolve_engine, job, mock_context, mock_data_table
    ):
        """Test query execution with catalog scope parameters."""
        mock_engine = AsyncMock()
        mock_engine.connect = AsyncMock()
        mock_engine.fetch_data_table = AsyncMock(return_value=mock_data_table)
        mock_engine.dispose = AsyncMock()
        mock_resolve_engine.return_value = mock_engine
        connection_id = str(uuid.uuid4())

        result = await job.execute(
            mock_context,
            {
                "sql": "SELECT 1",
                "catalog_connection_id": connection_id,
                "default_namespace": "bronze",
            },
        )

        assert result.success is True
        mock_resolve_engine.assert_called_once()
        _call_args, call_kwargs = mock_resolve_engine.call_args
        request = call_kwargs["request"]
        assert request.catalog_connection_id == connection_id
        assert request.default_namespace == "bronze"

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    async def test_execute_job_with_session_id(
        self, mock_resolve_engine, job, mock_context, mock_data_table
    ):
        """Test query execution with session_id parameter."""
        mock_engine = AsyncMock()
        mock_engine.connect = AsyncMock()
        mock_engine.fetch_data_table = AsyncMock(return_value=mock_data_table)
        mock_engine.dispose = AsyncMock()
        mock_resolve_engine.return_value = mock_engine
        session_id = str(uuid.uuid4())

        result = await job.execute(mock_context, {"sql": "SELECT 1", "session_id": session_id})

        assert result.success is True
        mock_resolve_engine.assert_called_once()
        _call_args, call_kwargs = mock_resolve_engine.call_args
        assert call_kwargs["request"].session_id == session_id

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    async def test_execute_job_hydrates_live_sql_scope_from_session(
        self, mock_resolve_engine, job, mock_context, mock_data_table
    ):
        mock_engine = AsyncMock()
        mock_engine.connect = AsyncMock()
        mock_engine.fetch_data_table = AsyncMock(return_value=mock_data_table)
        mock_engine.dispose = AsyncMock()
        mock_resolve_engine.return_value = mock_engine
        session_id = str(uuid.uuid4())
        connection_id = str(uuid.uuid4())
        entity_id = str(uuid.uuid4())

        query_session_service = MagicMock()
        query_session_service.get_query_session = AsyncMock(
            return_value=QuerySessionModel.model_construct(
                id=session_id,
                session_name="Live SQL",
                project_id=mock_context.project_id,
                catalog_connection_id=connection_id,
                default_namespace="sales",
                default_entity_id=entity_id,
                status="Active",
                engine_type=QueryEngineType.SQLSERVER,
            )
        )
        mock_context.get_query_session_service.return_value = query_session_service

        result = await job.execute(mock_context, {"sql": "SELECT 1", "session_id": session_id})

        assert result.success is True
        query_session_service.get_query_session.assert_awaited_once_with(
            session_id=session_id,
            project_id=mock_context.project_id,
        )
        _, call_kwargs = mock_resolve_engine.call_args
        request = call_kwargs["request"]
        assert request.catalog_connection_id == connection_id
        assert request.default_namespace == "sales"
        assert request.default_entity_id == entity_id
        assert call_kwargs["engine_type"] == QueryEngineType.SQLSERVER

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    async def test_execute_job_returns_clear_error_for_broken_live_sql_scope(
        self, mock_resolve_engine, job, mock_context
    ):
        session_id = str(uuid.uuid4())
        query_session_service = MagicMock()
        query_session_service.get_query_session = AsyncMock(
            return_value=QuerySessionModel.model_construct(
                id=session_id,
                session_name="Broken Live SQL",
                project_id=mock_context.project_id,
                catalog_connection_id=None,
                status="Active",
                engine_type=QueryEngineType.SQLSERVER,
            )
        )
        mock_context.get_query_session_service.return_value = query_session_service

        result = await job.execute(
            mock_context,
            {"sql": "SELECT 1", "session_id": session_id},
        )

        assert result.success is False
        assert "missing catalog_connection_id" in result.message
        mock_resolve_engine.assert_not_called()

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    async def test_execute_job_ddl_statement(self, mock_resolve_engine, job, mock_context):
        """Test execution of a DDL statement."""
        mock_engine = AsyncMock()
        mock_engine.connect = AsyncMock()
        # DDL returns empty DataTable
        empty_table = DataTable(columns=[], rows=[])
        mock_engine.fetch_data_table = AsyncMock(return_value=empty_table)
        mock_engine.dispose = AsyncMock()
        mock_resolve_engine.return_value = mock_engine

        result = await job.execute(mock_context, {"sql": "CREATE TABLE test (id INTEGER)"})

        assert result.success is True
        assert "Query executed successfully" in result.message

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    async def test_execute_job_query_error(self, mock_resolve_engine, job, mock_context):
        """Test handling of query execution errors."""
        mock_engine = AsyncMock()
        mock_engine.connect = AsyncMock()
        mock_engine.fetch_data_table.side_effect = Exception("Table does not exist")
        mock_engine.dispose = AsyncMock()
        mock_resolve_engine.return_value = mock_engine

        result = await job.execute(mock_context, {"sql": "SELECT * FROM nonexistent_table"})

        assert result.success is False
        assert "Query execution failed: Table does not exist" in result.message

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    @patch("asyncio.wait_for")
    async def test_execute_job_timeout_error(
        self, mock_wait_for, mock_resolve_engine, job, mock_context
    ):
        """Test handling of query timeout."""
        mock_engine = AsyncMock()
        mock_engine.connect = AsyncMock()
        mock_engine.dispose = AsyncMock()
        mock_resolve_engine.return_value = mock_engine
        mock_wait_for.side_effect = TimeoutError("Timeout")

        result = await job.execute(
            mock_context,
            {
                "sql": "SELECT pg_sleep(10)",
                "query_timeout_seconds": 1,
            },
        )

        assert result.success is False
        assert "timed out after 1 seconds" in result.message

    @pytest.mark.asyncio
    @patch("kontext.query.jobs.execute_query_job.resolve_engine_for_session")
    async def test_execute_job_session_error(self, mock_resolve_engine, job, mock_context):
        """Test handling of session creation errors."""
        mock_resolve_engine.side_effect = Exception("Session creation failed")

        result = await job.execute(mock_context, {"sql": "SELECT 1"})

        assert result.success is False
        assert "Session error" in result.message
