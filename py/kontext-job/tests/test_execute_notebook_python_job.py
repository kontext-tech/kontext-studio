from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.jobs.definitions.execute_notebook_python_job import (
    ExecuteNotebookPythonJob,
    ExecuteNotebookPythonParams,
)
from kontext.jobs.definitions.execute_python_script_job import (
    ExecutePythonScriptJob,
    ExecutePythonScriptParams,
    _ManagedPythonBridge,
)
from kontext.jobs.job_registry import PythonJobRegistry
from kontext.schema import ArtifactOrigin, DataColumn, DataTable, TriggerActorType


def _context_with_session_runner(runner: object) -> MagicMock:
    context = MagicMock()
    context.project_id = "11111111-1111-1111-1111-111111111111"
    context.log_info = AsyncMock()
    context.log_warning = AsyncMock()
    context.log_error = AsyncMock()
    context.get_file_service = MagicMock()
    context.get_runtime_provider.return_value = MagicMock()
    context.get_runtime_provider.return_value.create_python_session_runner.return_value = runner
    return context


class _ValidationFailureRunner:
    """Session runner stub that fails validation, as the real dispatcher would."""

    async def run(self, **_kwargs):
        from kontext.common.python_execution.runner import PythonRunnerResult

        return PythonRunnerResult(
            success=False,
            message="Python code validation failed.",
            error="Forbidden import: 'subprocess'",
            outputs=[],
            stdout="",
            stderr="",
        )


@pytest.mark.asyncio
async def test_notebook_job_surfaces_runner_validation_failure() -> None:
    """Code security is validated by the runner (dispatcher), not the job.

    The job must forward the runner's failure payload untouched so the agent
    still receives the policy message.
    """
    params = ExecuteNotebookPythonParams(
        notebook_id="22222222-2222-2222-2222-222222222222",
        block_id="33333333-3333-3333-3333-333333333333",
        code="import subprocess\nprint('unsafe')",
        data_sources={},
    )

    result = await ExecuteNotebookPythonJob().execute_job(
        _context_with_session_runner(_ValidationFailureRunner()), params
    )

    assert result.success is False
    assert result.message == "Forbidden import: 'subprocess'"
    assert result.data is not None
    assert result.data["type"] == "python_execution"
    assert result.data["targetType"] == "notebook"
    assert result.data["error"] == "Forbidden import: 'subprocess'"


def test_execute_notebook_python_job_is_discoverable_via_registry() -> None:
    registry = PythonJobRegistry()

    assert registry.is_job_registered("python.jobs.ExecuteNotebookPythonJob")
    assert isinstance(
        registry.create_job_instance("python.jobs.ExecuteNotebookPythonJob"),
        ExecuteNotebookPythonJob,
    )


@pytest.mark.asyncio
async def test_script_job_surfaces_runner_validation_failure() -> None:
    """The runner (dispatcher) owns code-security validation, not the job."""
    params = ExecutePythonScriptParams(
        code="import subprocess\nprint('unsafe')",
        data_sources={},
    )

    result = await ExecutePythonScriptJob().execute_job(
        _context_with_session_runner(_ValidationFailureRunner()), params
    )

    assert result.success is False
    assert result.message == "Forbidden import: 'subprocess'"
    assert result.data is not None
    assert result.data["targetType"] == "session"
    assert result.data["error"] == "Forbidden import: 'subprocess'"


def test_execute_python_script_job_is_discoverable_via_registry() -> None:
    registry = PythonJobRegistry()

    assert registry.is_job_registered("python.jobs.ExecutePythonScriptJob")
    assert isinstance(
        registry.create_job_instance("python.jobs.ExecutePythonScriptJob"),
        ExecutePythonScriptJob,
    )


@pytest.mark.asyncio
async def test_notebook_job_uses_session_kernel_when_provider_exposes_one() -> None:
    """With a session runner on the provider, the job runs via the session runner."""
    recorded: dict[str, object] = {}

    class FakeSessionRunner:
        async def run(self, **kwargs):
            recorded.update(kwargs)
            from kontext.common.python_execution.runner import PythonRunnerResult

            return PythonRunnerResult(
                success=True,
                message="ok",
                error=None,
                outputs=[],
                stdout="",
                stderr="",
            )

    context = MagicMock()
    context.project_id = "11111111-1111-1111-1111-111111111111"
    context.job_run_id = "run-1"
    context.log_info = AsyncMock()
    context.log_warning = AsyncMock()
    context.get_file_service = MagicMock()
    context.get_runtime_provider.return_value = MagicMock()
    context.get_runtime_provider.return_value.create_python_session_runner.return_value = None
    context.get_runtime_provider.return_value = MagicMock()
    context.get_runtime_provider.return_value.create_python_session_runner.return_value = (
        FakeSessionRunner()
    )

    params = ExecuteNotebookPythonParams(
        notebook_id="22222222-2222-2222-2222-222222222222",
        block_id="33333333-3333-3333-3333-333333333333",
        code="value = 1 + 1",
        data_sources={},
    )

    job = ExecuteNotebookPythonJob()
    result = await job.execute_job(context, params)

    assert result.success is True
    assert recorded["session_id"] == "22222222-2222-2222-2222-222222222222"
    assert recorded["code"] == "value = 1 + 1"


@pytest.mark.asyncio
async def test_execute_python_script_job_rejects_execute_sql_without_context() -> None:
    context = MagicMock()
    context.project_id = "11111111-1111-1111-1111-111111111111"
    context.log_warning = AsyncMock()
    context.log_info = AsyncMock()
    context.get_file_service = MagicMock()
    context.get_runtime_provider.return_value = MagicMock()
    context.get_runtime_provider.return_value.create_python_session_runner.return_value = None

    params = ExecutePythonScriptParams(
        code='result = await kontext.execute_sql("SELECT 1")',
        data_sources={},
    )

    job = ExecutePythonScriptJob()
    result = await job.execute_job(context, params)

    assert result.success is False
    assert result.data is not None
    assert "active query context" in result.message
    assert result.data["targetType"] == "session"


@pytest.mark.asyncio
async def test_managed_python_sql_bridge_executes_read_only_query() -> None:
    context = MagicMock()
    context.project_id = "11111111-1111-1111-1111-111111111111"
    context.log_info = AsyncMock()

    query_session_service = MagicMock()
    query_session_service.get_or_create_session = AsyncMock(
        return_value="22222222-2222-2222-2222-222222222222"
    )
    context.get_query_session_service.return_value = query_session_service

    engine = MagicMock()
    engine.connect = AsyncMock()
    engine.validate_sql = AsyncMock(return_value=(True, None))
    engine.fetch_data_table = AsyncMock(
        return_value=DataTable(
            columns=[DataColumn(name="value", type="INTEGER")],
            rows=[[1]],
            row_count=1,
        )
    )
    engine.dispose = AsyncMock()

    runtime_provider = MagicMock()
    runtime_provider.get_query_execution_engine.return_value = engine
    context.get_runtime_provider.return_value = runtime_provider

    bridge = _ManagedPythonBridge(
        context=context,
        parameters=ExecutePythonScriptParams(
            code='result = await kontext.execute_sql("SELECT 1")',
            data_sources={},
            query_session_id="33333333-3333-3333-3333-333333333333",
            engine_type="DuckDB",
        ),
    )

    result = await bridge.execute_sql("SELECT 1 AS value")

    assert result.row_count == 1
    query_session_service.get_or_create_session.assert_awaited_once()
    engine.validate_sql.assert_awaited_once_with("SELECT 1 AS value")
    engine.fetch_data_table.assert_awaited_once_with(
        "SELECT 1 AS value",
        max_rows=5_001,
    )


@pytest.mark.asyncio
async def test_managed_python_sql_bridge_rejects_non_read_only_query() -> None:
    bridge = _ManagedPythonBridge(
        context=MagicMock(),
        parameters=ExecutePythonScriptParams(
            code='result = await kontext.execute_sql("DELETE FROM demo")',
            data_sources={},
            query_session_id="33333333-3333-3333-3333-333333333333",
        ),
    )

    with pytest.raises(ValueError, match="read-only"):
        await bridge.execute_sql("DELETE FROM demo")


def _encoded_two_row_table() -> str:
    import base64
    import io

    import pyarrow as pa
    import pyarrow.parquet as pq

    buffer = io.BytesIO()
    pq.write_table(pa.table({"value": [1, 2]}), buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _SavingRunner:
    """Session runner stub that simulates a cell persisting a table."""

    def __init__(self, payload: str) -> None:
        self.payload = payload

    async def run(self, **kwargs):
        from kontext.common.python_execution.runner import PythonRunnerResult

        bridge = kwargs.get("host_bridge")
        assert bridge is not None
        await bridge.save_table({"title": "Saved", "data": self.payload})
        return PythonRunnerResult(
            success=True,
            message="Python execution completed successfully.",
            error=None,
            outputs=[],
            stdout="",
            stderr="",
        )


@pytest.mark.asyncio
async def test_script_job_lifts_saved_tables_into_payload() -> None:
    """The job records save_table outputs so the tool layer can register them."""
    durable_id = "44444444-4444-4444-4444-444444444444"
    file_service = MagicMock()
    file_service.materialize_parquet_inline_data = AsyncMock(return_value=durable_id)

    context = _context_with_session_runner(_SavingRunner(_encoded_two_row_table()))
    context.get_file_service.return_value = file_service
    context.job_run_id = "55555555-5555-5555-5555-555555555555"
    context.get_runtime_provider.return_value.get_chat_session_service.return_value = None

    params = ExecutePythonScriptParams(
        code="kontext.save_table(df, 'Saved')",
        data_sources={},
    )
    result = await ExecutePythonScriptJob().execute_job(context, params)

    assert result.success is True
    assert result.data is not None
    assert result.data["savedTables"] == [
        {"dataTableId": durable_id, "rowCount": 2, "title": "Saved"}
    ]


@pytest.mark.asyncio
async def test_notebook_job_serves_save_table_with_notebook_provenance() -> None:
    """Notebook blocks can persist tables, stamped as notebook_run with the block id."""
    durable_id = "66666666-6666-6666-6666-666666666666"
    file_service = MagicMock()
    file_service.materialize_parquet_inline_data = AsyncMock(return_value=durable_id)

    context = _context_with_session_runner(_SavingRunner(_encoded_two_row_table()))
    context.get_file_service.return_value = file_service
    context.job_run_id = "77777777-7777-7777-7777-777777777777"
    context.get_runtime_provider.return_value.get_chat_session_service.return_value = None

    params = ExecuteNotebookPythonParams(
        notebook_id="22222222-2222-2222-2222-222222222222",
        block_id="33333333-3333-3333-3333-333333333333",
        code="kontext.save_table(df, 'Block Result')",
        data_sources={},
    )
    result = await ExecuteNotebookPythonJob().execute_job(context, params)

    assert result.success is True
    assert result.data is not None
    assert result.data["savedTables"] == [
        {"dataTableId": durable_id, "rowCount": 2, "title": "Saved"}
    ]

    provenance = file_service.materialize_parquet_inline_data.call_args.kwargs["provenance"]
    assert provenance.origin == ArtifactOrigin.NOTEBOOKRUN
    assert provenance.block_id == "33333333-3333-3333-3333-333333333333"
    assert provenance.created_by is not None
    assert provenance.created_by.type == TriggerActorType.NOTEBOOK
    assert provenance.created_by.id == "22222222-2222-2222-2222-222222222222"


async def test_notebook_bridge_rejects_execute_sql() -> None:
    """Notebook bridges intentionally expose save_table but not execute_sql."""
    bridge = _ManagedPythonBridge(
        context=_context_with_session_runner(_ValidationFailureRunner()),
        parameters=ExecutePythonScriptParams(code="x", data_sources={}),
    )
    # The script bridge does have SQL access; the notebook bridge (built with
    # query_parameters=None) is the one under test here.
    from kontext.jobs.definitions.python_host_bridge import ManagedPythonBridge

    notebook_bridge = ManagedPythonBridge(
        context=_context_with_session_runner(_ValidationFailureRunner()),
        chat_session_id=None,
        origin=ArtifactOrigin.NOTEBOOKRUN,
        triggered_by=None,
        block_id="33333333-3333-3333-3333-333333333333",
    )
    with pytest.raises(ValueError, match="not available in notebook block execution"):
        await notebook_bridge.execute_sql("SELECT 1")

    # Sanity: the script bridge still exposes SQL execution to the same class.
    assert isinstance(bridge, ManagedPythonBridge)
