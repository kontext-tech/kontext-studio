from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.common.jobs.trigger_actor import agent_actor
from kontext.jobs.notebook_python_execution import (
    NotebookPythonExecutionError,
    NotebookPythonExecutionService,
)
from kontext.jobs.python_execution import PythonExecutionServiceResult
from kontext.schema import (
    CodeBlock,
    CodeBlockData,
    CodeExecutionOutput,
    CodeImageOutput,
    CodeJsonOutput,
    CodeTextOutput,
    DataRef,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    NotebookBlock,
    NotebookDocument,
    NotebookUpsertBlockAction,
    PythonExecutionResult,
    SqlBlock,
    SqlBlockData,
    TableBlock,
    TableBlockData,
)


def _create_notebook() -> tuple[NotebookDocument, str]:
    block_id = "22222222-2222-2222-2222-222222222222"
    notebook = NotebookDocument(
        title="Notebook",
        created=1,
        modified=1,
        blocks=[
            NotebookBlock(
                CodeBlock(
                    id=block_id,
                    type="code",
                    data=CodeBlockData(
                        code="print('hello')",
                        language="python",
                    ),
                )
            )
        ],
    )
    return notebook, block_id


def _create_table_notebook() -> tuple[NotebookDocument, str]:
    block_id = "22222222-2222-2222-2222-222222222222"
    notebook = NotebookDocument(
        title="Notebook",
        created=1,
        modified=1,
        blocks=[
            NotebookBlock(
                TableBlock(
                    id=block_id,
                    type="table",
                    data=TableBlockData(
                        content=[["value"], ["1"]],
                        with_headings=True,
                    ),
                )
            )
        ],
    )
    return notebook, block_id


@pytest.mark.asyncio
async def test_notebook_python_execution_service_persists_outputs_and_actions() -> None:
    notebook_id = "11111111-1111-1111-1111-111111111111"
    notebook, block_id = _create_notebook()
    stored_content = {"value": notebook.model_dump_json(by_alias=True, exclude_none=True)}

    file_service = MagicMock()

    async def get_file_content(*args, **kwargs):
        _ = args, kwargs
        return stored_content["value"]

    async def update_notebook(*args, **kwargs):
        updated_notebook = kwargs["notebook"]
        stored_content["value"] = updated_notebook.model_dump_json(
            by_alias=True,
            exclude_none=True,
        )
        return MagicMock(id=notebook_id)

    file_service.get_file_content = AsyncMock(side_effect=get_file_content)
    file_service.update_notebook = AsyncMock(side_effect=update_notebook)

    python_execution_service = MagicMock()
    python_execution_service.execute_notebook_code_async = AsyncMock(
        return_value=PythonExecutionServiceResult(
            execution_run=ExecutionRunModel.model_construct(
                id="run-456",
                kind=ExecutionRunKind.NOTEBOOK,
                status=ExecutionRunStatus.SUCCEEDED,
                created_at=datetime.now(UTC),
            ),
            python_result=PythonExecutionResult(
                success=True,
                message="Python execution completed successfully.",
                error=None,
                execution_run_id="run-456",
                outputs=[
                    CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="done"))
                ],
            ),
        )
    )

    service = NotebookPythonExecutionService(
        file_service=file_service,
        python_execution_service=python_execution_service,
    )

    result = await service.execute_notebook_code_async(
        project_id="33333333-3333-3333-3333-333333333333",
        notebook_id=notebook_id,
        block_id=block_id,
        owner_id="44444444-4444-4444-4444-444444444444",
        triggered_by=agent_actor("test"),
    )

    assert result.success is True
    assert result.notebook_id == notebook_id
    assert result.execution_run_id == "run-456"
    assert result.execution_mode == "persisted"
    assert len(result.actions or []) == 2
    assert file_service.update_notebook.await_count == 2
    execute_kwargs = python_execution_service.execute_notebook_code_async.await_args.kwargs
    assert execute_kwargs["owner_id"] == "44444444-4444-4444-4444-444444444444"

    saved_notebook = NotebookDocument.model_validate_json(stored_content["value"])
    saved_block = saved_notebook.blocks[0].root
    assert isinstance(saved_block, CodeBlock)
    assert saved_block.data.is_executing is False
    assert saved_block.data.last_executed is not None
    assert saved_block.data.outputs is not None
    saved_output = saved_block.data.outputs[0].root
    assert isinstance(saved_output, CodeTextOutput)
    assert saved_output.content == "done"


@pytest.mark.asyncio
async def test_notebook_python_execution_service_rejects_non_code_block() -> None:
    notebook, block_id = _create_table_notebook()
    file_service = MagicMock()
    file_service.get_file_content = AsyncMock(
        return_value=notebook.model_dump_json(by_alias=True, exclude_none=True)
    )

    service = NotebookPythonExecutionService(
        file_service=file_service,
        python_execution_service=MagicMock(),
    )

    with pytest.raises(NotebookPythonExecutionError) as exc_info:
        await service.execute_notebook_code_async(
            project_id="33333333-3333-3333-3333-333333333333",
            notebook_id="11111111-1111-1111-1111-111111111111",
            block_id=block_id,
        )

    assert exc_info.value.status_code == 400
    assert "not a code block" in exc_info.value.error


@pytest.mark.asyncio
async def test_notebook_python_execution_rejects_missing_notebook_data_blocks() -> None:
    notebook, block_id = _create_notebook()
    file_service = MagicMock()
    file_service.get_file_content = AsyncMock(
        return_value=notebook.model_dump_json(by_alias=True, exclude_none=True)
    )

    service = NotebookPythonExecutionService(
        file_service=file_service,
        python_execution_service=MagicMock(),
    )

    with pytest.raises(NotebookPythonExecutionError) as exc_info:
        await service.execute_notebook_code_async(
            project_id="33333333-3333-3333-3333-333333333333",
            notebook_id="11111111-1111-1111-1111-111111111111",
            block_id=block_id,
            code_override=(
                "df = await kontext.load_data('1eb96811-39fe-47a4-7e25-08de0be1d152')\nprint(df)"
            ),
        )

    assert exc_info.value.status_code == 400
    assert "materialized in the notebook" in exc_info.value.message
    assert "Add or import notebook data table blocks" in exc_info.value.error


@pytest.mark.asyncio
async def test_notebook_python_execution_service_persists_mixed_outputs() -> None:
    notebook_id = "11111111-1111-1111-1111-111111111111"
    notebook, block_id = _create_notebook()
    stored_content = {"value": notebook.model_dump_json(by_alias=True, exclude_none=True)}

    file_service = MagicMock()

    async def get_file_content(*args, **kwargs):
        _ = args, kwargs
        return stored_content["value"]

    async def update_notebook(*args, **kwargs):
        updated_notebook = kwargs["notebook"]
        stored_content["value"] = updated_notebook.model_dump_json(
            by_alias=True,
            exclude_none=True,
        )
        return MagicMock(id=notebook_id)

    file_service.get_file_content = AsyncMock(side_effect=get_file_content)
    file_service.update_notebook = AsyncMock(side_effect=update_notebook)

    python_execution_service = MagicMock()
    python_execution_service.execute_notebook_code_async = AsyncMock(
        return_value=PythonExecutionServiceResult(
            execution_run=ExecutionRunModel.model_construct(
                id="run-mixed",
                kind=ExecutionRunKind.NOTEBOOK,
                status=ExecutionRunStatus.SUCCEEDED,
                created_at=datetime.now(UTC),
            ),
            python_result=PythonExecutionResult(
                success=True,
                message="Python execution completed successfully.",
                error=None,
                execution_run_id="run-mixed",
                outputs=[
                    CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="done")),
                    CodeExecutionOutput(
                        CodeImageOutput(
                            mime_type="image/png",
                            content="ZmFrZS1pbWFnZQ==",
                        )
                    ),
                    CodeExecutionOutput(
                        CodeJsonOutput(
                            mime_type="application/json",
                            content='{"r2": 0.93}',
                        )
                    ),
                ],
            ),
        )
    )

    service = NotebookPythonExecutionService(
        file_service=file_service,
        python_execution_service=python_execution_service,
    )

    result = await service.execute_notebook_code_async(
        project_id="33333333-3333-3333-3333-333333333333",
        notebook_id=notebook_id,
        block_id=block_id,
    )

    assert result.success is True
    saved_notebook = NotebookDocument.model_validate_json(stored_content["value"])
    assert result.execution_run_id == "run-mixed"
    assert result.execution_mode == "persisted"
    assert result.target_type == "notebook"
    saved_block = saved_notebook.blocks[0].root
    assert isinstance(saved_block, CodeBlock)
    assert saved_block.data.outputs is not None
    assert isinstance(saved_block.data.outputs[0].root, CodeTextOutput)
    assert isinstance(saved_block.data.outputs[1].root, CodeImageOutput)
    assert isinstance(saved_block.data.outputs[2].root, CodeJsonOutput)


@pytest.mark.asyncio
async def test_notebook_python_execution_service_supports_draft_runs() -> None:
    notebook_id = "11111111-1111-1111-1111-111111111111"
    notebook, block_id = _create_notebook()
    file_service = MagicMock()
    file_service.get_file_content = AsyncMock(
        return_value=notebook.model_dump_json(by_alias=True, exclude_none=True)
    )
    file_service.update_notebook = AsyncMock()

    python_execution_service = MagicMock()
    python_execution_service.execute_notebook_code_async = AsyncMock(
        return_value=PythonExecutionServiceResult(
            execution_run=ExecutionRunModel.model_construct(
                id="run-draft",
                kind=ExecutionRunKind.NOTEBOOK,
                status=ExecutionRunStatus.SUCCEEDED,
                created_at=datetime.now(UTC),
            ),
            python_result=PythonExecutionResult(
                success=True,
                message="Python execution completed successfully.",
                error=None,
                execution_run_id="run-draft",
                outputs=[
                    CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="draft"))
                ],
            ),
        )
    )

    service = NotebookPythonExecutionService(
        file_service=file_service,
        python_execution_service=python_execution_service,
    )

    result = await service.execute_notebook_code_async(
        project_id="33333333-3333-3333-3333-333333333333",
        notebook_id=notebook_id,
        block_id=block_id,
        code_override="print('draft')",
        persist_notebook_state=False,
    )

    assert result.success is True
    assert result.notebook_id == notebook_id
    assert result.execution_run_id == "run-draft"
    assert result.execution_mode == "draft"
    assert result.target_type == "notebook"
    assert result.actions is not None
    assert len(result.actions) == 1
    action = result.actions[0].root
    assert isinstance(action, NotebookUpsertBlockAction)
    assert action.payload.cid == block_id
    payload_data = action.payload.data
    assert isinstance(payload_data, dict)
    assert payload_data["code"] == "print('draft')"
    payload_outputs = payload_data.get("outputs")
    assert isinstance(payload_outputs, list)
    first_output = payload_outputs[0]
    assert isinstance(first_output, dict)
    assert first_output["content"] == "draft"
    file_service.update_notebook.assert_not_awaited()
    execute_kwargs = python_execution_service.execute_notebook_code_async.await_args.kwargs
    assert execute_kwargs["code"] == "print('draft')"


SQL_DATA_ID = "55555555-5555-5555-5555-555555555555"
SQL_BLOCK_ID = "66666666-6666-6666-6666-666666666666"


def _create_sql_notebook(alias: str | None = "df_1") -> tuple[NotebookDocument, str]:
    """Notebook with one result-bearing SQL block plus a Python block to run."""
    notebook, block_id = _create_notebook()
    notebook.blocks.append(
        NotebookBlock(
            SqlBlock(
                id=SQL_BLOCK_ID,
                type="sql",
                data=SqlBlockData(
                    code="SELECT 1 AS n",
                    data_ref=DataRef(data_id=SQL_DATA_ID),
                    alias=alias,
                ),
            )
        )
    )
    return notebook, block_id


def _sql_execution_service(
    notebook: NotebookDocument,
) -> tuple[NotebookPythonExecutionService, MagicMock, MagicMock]:
    file_service = MagicMock()
    file_service.get_file_content = AsyncMock(
        return_value=notebook.model_dump_json(by_alias=True, exclude_none=True)
    )
    file_service.update_notebook = AsyncMock()
    python_execution_service = MagicMock()
    python_execution_service.execute_notebook_code_async = AsyncMock(
        return_value=PythonExecutionServiceResult(
            execution_run=ExecutionRunModel.model_construct(
                id="run-alias",
                kind=ExecutionRunKind.NOTEBOOK,
                status=ExecutionRunStatus.SUCCEEDED,
                created_at=datetime.now(UTC),
            ),
            python_result=PythonExecutionResult(
                success=True,
                message="Python execution completed successfully.",
                error=None,
                execution_run_id="run-alias",
                outputs=[CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))],
            ),
        )
    )
    service = NotebookPythonExecutionService(
        file_service=file_service,
        python_execution_service=python_execution_service,
    )
    return service, python_execution_service, file_service


def test_scoped_data_sources_include_sql_aliases() -> None:
    notebook, _block_id = _create_sql_notebook()

    service = NotebookPythonExecutionService(
        file_service=MagicMock(),
        python_execution_service=MagicMock(),
    )

    scoped = service._build_scoped_data_sources(notebook, None)

    assert scoped[SQL_DATA_ID] == SQL_DATA_ID
    assert scoped["df_1"] == SQL_DATA_ID


def test_scoped_data_sources_prefer_provided_sources() -> None:
    notebook, _block_id = _create_sql_notebook()

    service = NotebookPythonExecutionService(
        file_service=MagicMock(),
        python_execution_service=MagicMock(),
    )

    scoped = service._build_scoped_data_sources(
        notebook,
        {SQL_DATA_ID: "77777777-7777-7777-7777-777777777777"},
    )

    assert scoped[SQL_DATA_ID] == "77777777-7777-7777-7777-777777777777"
    assert scoped["df_1"] == SQL_DATA_ID


def test_ambiguous_alias_is_dropped_instead_of_resolved() -> None:
    notebook, _block_id = _create_sql_notebook(alias="df_1")
    notebook.blocks.append(
        NotebookBlock(
            SqlBlock(
                id="77777777-7777-7777-7777-777777777777",
                type="sql",
                data=SqlBlockData(
                    code="SELECT 2 AS n",
                    data_ref=DataRef(data_id="88888888-8888-8888-8888-888888888888"),
                    alias="df_1",
                ),
            )
        )
    )

    service = NotebookPythonExecutionService(
        file_service=MagicMock(),
        python_execution_service=MagicMock(),
    )

    assert service._collect_notebook_sql_aliases(notebook) == {}


@pytest.mark.asyncio
async def test_load_data_by_alias_and_uuid_passes_validation() -> None:
    notebook, block_id = _create_sql_notebook()
    service, python_execution_service, _file_service = _sql_execution_service(notebook)

    result = await service.execute_notebook_code_async(
        project_id="33333333-3333-3333-3333-333333333333",
        notebook_id="11111111-1111-1111-1111-111111111111",
        block_id=block_id,
        code_override=(
            f'df = await kontext.load_data("df_1")\n'
            f'df2 = await kontext.load_data("{SQL_DATA_ID}")\nprint(df, df2)'
        ),
    )

    assert result.success is True
    scoped = python_execution_service.execute_notebook_code_async.await_args.kwargs["data_sources"]
    assert scoped[SQL_DATA_ID] == SQL_DATA_ID
    assert scoped["df_1"] == SQL_DATA_ID


@pytest.mark.asyncio
async def test_load_data_by_unknown_alias_lists_available_aliases() -> None:
    notebook, block_id = _create_sql_notebook()
    service, _python_execution_service, _file_service = _sql_execution_service(notebook)

    with pytest.raises(NotebookPythonExecutionError) as exc_info:
        await service.execute_notebook_code_async(
            project_id="33333333-3333-3333-3333-333333333333",
            notebook_id="11111111-1111-1111-1111-111111111111",
            block_id=block_id,
            code_override='df = await kontext.load_data("monthly_summary")',
        )

    assert exc_info.value.status_code == 400
    assert "monthly_summary" in exc_info.value.error
    assert "'df_1'" in exc_info.value.error


@pytest.mark.asyncio
async def test_alias_without_persisted_results_is_not_loadable() -> None:
    notebook, block_id = _create_sql_notebook(alias="monthly_summary")
    # Strip the persisted result: the name is declared but bound to nothing.
    sql = next(block.root for block in notebook.blocks if isinstance(block.root, SqlBlock))
    sql.data.data_ref = None
    service, _python_execution_service, _file_service = _sql_execution_service(notebook)

    with pytest.raises(NotebookPythonExecutionError) as exc_info:
        await service.execute_notebook_code_async(
            project_id="33333333-3333-3333-3333-333333333333",
            notebook_id="11111111-1111-1111-1111-111111111111",
            block_id=block_id,
            code_override='df = await kontext.load_data("monthly_summary")',
        )

    assert exc_info.value.status_code == 400
    assert "monthly_summary" in exc_info.value.error


@pytest.mark.asyncio
async def test_execution_binds_missing_alias_server_side() -> None:
    """Client-stamped results may be saved without an alias; the python block's
    own execution binds df_N server-side before resolution and persists it."""
    notebook, block_id = _create_sql_notebook(alias=None)
    python_code_block = next(
        block.root for block in notebook.blocks if isinstance(block.root, CodeBlock)
    )
    python_code_block.data.code = 'df = await kontext.load_data("df_1")\nprint(df)'
    service, python_execution_service, file_service = _sql_execution_service(notebook)

    result = await service.execute_notebook_code_async(
        project_id="33333333-3333-3333-3333-333333333333",
        notebook_id="11111111-1111-1111-1111-111111111111",
        block_id=block_id,
    )

    assert result.success is True
    scoped = python_execution_service.execute_notebook_code_async.await_args.kwargs["data_sources"]
    assert scoped[SQL_DATA_ID] == SQL_DATA_ID
    assert scoped["df_1"] == SQL_DATA_ID

    # The binding is written back: the persisted notebook resolves the same
    # name on the next load.
    persisted = file_service.update_notebook.await_args.kwargs["notebook"]
    persisted_sql = next(
        block.root for block in persisted.blocks if isinstance(block.root, SqlBlock)
    )
    assert persisted_sql.data.alias == "df_1"
