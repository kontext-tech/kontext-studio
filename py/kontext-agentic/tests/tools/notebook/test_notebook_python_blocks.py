"""Python-block tool tests for NotebookTools (drafts, imports, persistence)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agent import (
    AgentContext,
    SharedSessionStore,
    ToolExecutionContext,
    agent_context_scope,
    create_kontext_session_state,
    unregister_session_context,
)
from kontext.agent.tools import get_declared_tool_meta
from kontext.agentic.tools.notebook_tool import NotebookTools
from kontext.agentic.tools.python_tool import NotebookPythonTools
from kontext.common.jobs.trigger_actor import agent_actor
from kontext.common.protocols import IFileServiceProtocol, IQuerySessionServiceProtocol
from kontext.execution import PythonExecutionServiceResult
from kontext.file.notebook.editor import NotebookEditor
from kontext.schema import (
    ArtifactType,
    CodeBlock,
    CodeExecutionOutput,
    CodeImageOutput,
    CodeJsonOutput,
    CodeTextOutput,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    NotebookDocument,
    PythonExecutionMode,
    PythonExecutionResult,
    PythonExecutionTargetType,
    SqlBlock,
)

if TYPE_CHECKING:
    from kontext.agent import RuntimeToolContext


from .conftest import TestRuntimeContext


def test_persist_python_execution_state_tool_meta_emits_tool_call():
    meta = get_declared_tool_meta(NotebookTools.persist_python_execution_state)

    assert meta is not None
    assert meta.emit_tool_call is True
    assert meta.emit_result is True


def test_import_executed_python_tool_meta_emits_tool_call():
    meta = get_declared_tool_meta(NotebookTools.import_executed_python)

    assert meta is not None
    assert meta.emit_tool_call is True
    assert meta.emit_result is True


def test_notebook_tools_expose_python_mutation_without_execution(
    mock_service_provider,
    sample_project,
):
    """Block mutation stays on NotebookTools; execution is a separate toolkit."""
    tools = NotebookTools(
        project=sample_project,
        runtime_provider=mock_service_provider,
        allow_python_blocks=True,
        allow_python_execution_persistence=True,
    )

    tool_names = [tool.__name__ for tool in tools.get_tool_callables()]
    assert "add_python" in tool_names
    assert "edit_python_code" in tool_names
    assert "import_executed_python" in tool_names
    assert "persist_python_execution_state" in tool_names
    assert "execute_python_code" not in tool_names


def test_notebook_python_tools_expose_only_execution(
    mock_service_provider,
    sample_project,
):
    tools = NotebookPythonTools(
        project=sample_project,
        runtime_provider=mock_service_provider,
    )

    tool_names = [tool.__name__ for tool in tools.get_tool_callables()]
    assert tool_names == ["execute_python_code"]
    assert tools.external_execution_required_tools == ["execute_python_code"]
    assert tools.python_execution_actor == "notebook_tool"


def test_notebook_tools_without_python_do_not_expose_python_tools(
    mock_service_provider,
    sample_project,
):
    tools = NotebookTools(
        project=sample_project,
        runtime_provider=mock_service_provider,
        allow_python_blocks=False,
    )

    tool_names = [tool.__name__ for tool in tools.get_tool_callables()]
    assert "add_python" not in tool_names
    assert "edit_python_code" not in tool_names
    assert "execute_python_code" not in tool_names


@pytest.mark.asyncio
async def test_persist_python_execution_state_updates_code_and_outputs(
    sample_project,
):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    session_id = "chat-session-id"
    execution_run_id = "1eb96811-39fe-47a4-7e25-08de0be1d151"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Python Notebook")
    code_block = editor.add_code_block(
        "print('draft')",
        language="python",
        title="Load data",
    )
    stored_content = {"value": notebook.model_dump_json(exclude_none=True, by_alias=True)}

    file_service_mock = MagicMock(spec=IFileServiceProtocol)

    async def get_file_content(*args, **kwargs):
        _ = args, kwargs
        return stored_content["value"]

    async def update_notebook(*args, **kwargs):
        notebook_arg = kwargs["notebook"]
        stored_content["value"] = notebook_arg.model_dump_json(exclude_none=True, by_alias=True)
        return MagicMock()

    file_service_mock.get_file_content = AsyncMock(side_effect=get_file_content)
    file_service_mock.update_notebook = AsyncMock(side_effect=update_notebook)

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id=session_id,
        allow_python_blocks=True,
        allow_python_execution_persistence=True,
    )

    outputs = [
        CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok")),
        CodeExecutionOutput(CodeImageOutput(mime_type="image/png", content="ZmFrZS1wbG90")),
        CodeExecutionOutput(
            CodeJsonOutput(
                mime_type="application/json",
                content='{"r2": 0.93}',
            )
        ),
    ]
    tools.python_execution_service = MagicMock(
        get_execution_result_async=AsyncMock(
            return_value=_managed_python_execution_result(
                project_id=str(sample_project.id),
                run_id=execution_run_id,
                code="print('final')",
                outputs=outputs,
                target_type=PythonExecutionTargetType.NOTEBOOK,
            )
        )
    )

    try:
        with agent_context_scope(
            AgentContext(project_id=str(sample_project.id), session_id=session_id),
            tool_ctx=ToolExecutionContext(project_id=str(sample_project.id), session_id=session_id),
        ):
            result_json = await tools.persist_python_execution_state(
                notebook_id=notebook_id,
                block_id=str(code_block.root.id),
                execution_run_id=execution_run_id,
                title="Final code",
            )

        payload = json.loads(result_json)
        assert payload["success"] is True
        assert payload["notebookId"] == notebook_id
        assert payload["blockId"] == str(code_block.root.id)
        assert file_service_mock.update_notebook.await_count == 1

        saved_notebook = NotebookDocument.model_validate_json(stored_content["value"])
        saved_code_block = next(
            (
                block.root
                for block in saved_notebook.blocks
                if isinstance(block.root, CodeBlock)
                and str(block.root.id) == str(code_block.root.id)
            ),
            None,
        )
        assert saved_code_block is not None
        assert saved_code_block.data.code == "print('final')"
        assert saved_code_block.data.title == "Final code"
        assert saved_code_block.data.is_executing is False
        assert saved_code_block.data.last_executed is not None
        assert saved_code_block.data.outputs is not None

        first_output = saved_code_block.data.outputs[0].root
        assert isinstance(first_output, CodeTextOutput)
        assert first_output.content == "ok"
        second_output = saved_code_block.data.outputs[1].root
        assert isinstance(second_output, CodeImageOutput)
        assert second_output.content == "ZmFrZS1wbG90"
        third_output = saved_code_block.data.outputs[2].root
        assert isinstance(third_output, CodeJsonOutput)
        assert third_output.content == '{"r2": 0.93}'
    finally:
        unregister_session_context(session_id)


@pytest.mark.asyncio
async def test_import_executed_python_updates_existing_block_and_materializes_data_tables(
    sample_project,
):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    session_id = "chat-session-id"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"
    execution_run_id = "1eb96811-39fe-47a4-7e25-08de0be1d153"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Python Notebook")
    code_block = editor.add_code_block(
        "print('draft')",
        language="python",
        title="Draft code",
    )
    stored_content = {"value": notebook.model_dump_json(exclude_none=True, by_alias=True)}

    file_service_mock = MagicMock(spec=IFileServiceProtocol)

    async def get_file_content(*args, **kwargs):
        _ = args, kwargs
        return stored_content["value"]

    async def update_notebook(*args, **kwargs):
        notebook_arg = kwargs["notebook"]
        stored_content["value"] = notebook_arg.model_dump_json(exclude_none=True, by_alias=True)
        return MagicMock()

    file_service_mock.get_file_content = AsyncMock(side_effect=get_file_content)
    file_service_mock.update_notebook = AsyncMock(side_effect=update_notebook)

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id=session_id,
        allow_python_blocks=True,
        allow_python_execution_persistence=True,
    )
    outputs = [CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))]
    tools.python_execution_service = MagicMock(
        get_execution_result_async=AsyncMock(
            return_value=_managed_python_execution_result(
                project_id=str(sample_project.id),
                run_id=execution_run_id,
                code=f"df = await kontext.load_data('{data_id}')\nprint(df)",
                outputs=outputs,
                target_type=PythonExecutionTargetType.SESSION,
            )
        )
    )
    run_context: RuntimeToolContext = TestRuntimeContext(
        session_state={
            "kontext": {
                "version": 1,
                "artifacts_by_id": {
                    data_id: {
                        "artifact_id": data_id,
                        "artifact_type": "DataTable",
                        "sql": "SELECT amount FROM bronze.transactions",
                        "title": "Transactions",
                    }
                },
                "data_identity_index": {},
            }
        }
    )

    try:
        with agent_context_scope(
            AgentContext(project_id=str(sample_project.id), session_id=session_id),
            tool_ctx=ToolExecutionContext(project_id=str(sample_project.id), session_id=session_id),
        ):
            result_json = await tools.import_executed_python(
                notebook_id=notebook_id,
                block_id=str(code_block.root.id),
                title="Final analysis",
                execution_run_id=execution_run_id,
                run_context=run_context,
            )

        payload = json.loads(result_json)
        assert payload["success"] is True
        assert payload["blockId"] == str(code_block.root.id)

        saved_notebook = NotebookDocument.model_validate_json(stored_content["value"])
        assert len(saved_notebook.blocks) == 2

        first_block = saved_notebook.blocks[0].root
        second_block = saved_notebook.blocks[1].root
        assert isinstance(first_block, SqlBlock)
        assert isinstance(second_block, CodeBlock)
        assert str(second_block.id) == str(code_block.root.id)
        assert first_block.data.data_ref is not None
        assert first_block.data.data_ref.data_id == data_id
        assert first_block.data.code == "SELECT amount FROM bronze.transactions"
        assert second_block.data.code.startswith("df = await kontext.load_data(")
        assert second_block.data.title == "Final analysis"
        assert second_block.data.outputs is not None
        assert isinstance(second_block.data.outputs[0].root, CodeTextOutput)
        assert second_block.data.outputs[0].root.content == "ok"
        assert second_block.data.last_executed is not None
    finally:
        unregister_session_context(session_id)


@pytest.mark.asyncio
async def test_import_executed_python_rejects_notebook_target_runs(
    sample_project,
) -> None:
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    execution_run_id = "1eb96811-39fe-47a4-7e25-08de0be1d154"

    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock(spec=IFileServiceProtocol)
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        allow_python_blocks=True,
        allow_python_execution_persistence=True,
    )
    tools.python_execution_service = MagicMock(
        get_execution_result_async=AsyncMock(
            return_value=_managed_python_execution_result(
                project_id=str(sample_project.id),
                run_id=execution_run_id,
                code="print('already notebook')",
                outputs=[],
                target_type=PythonExecutionTargetType.NOTEBOOK,
            )
        )
    )

    result_json = await tools.import_executed_python(
        notebook_id=notebook_id,
        execution_run_id=execution_run_id,
    )

    payload = json.loads(result_json)
    assert payload["success"] is False
    assert "persist_python_execution_state" in payload["message"]


@pytest.mark.asyncio
async def test_persist_python_execution_state_rejects_session_target_runs(
    sample_project,
) -> None:
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    block_id = "1eb96811-39fe-47a4-7e25-08de0be1d155"
    execution_run_id = "1eb96811-39fe-47a4-7e25-08de0be1d156"

    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock(spec=IFileServiceProtocol)
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        allow_python_blocks=True,
        allow_python_execution_persistence=True,
    )
    tools.python_execution_service = MagicMock(
        get_execution_result_async=AsyncMock(
            return_value=_managed_python_execution_result(
                project_id=str(sample_project.id),
                run_id=execution_run_id,
                code="print('session')",
                outputs=[],
                target_type=PythonExecutionTargetType.SESSION,
            )
        )
    )

    result_json = await tools.persist_python_execution_state(
        notebook_id=notebook_id,
        block_id=block_id,
        execution_run_id=execution_run_id,
    )

    payload = json.loads(result_json)
    assert payload["success"] is False
    assert "import_executed_python" in payload["message"]


@pytest.mark.asyncio
async def test_add_python_returns_created_block_id(
    sample_project,
) -> None:
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    session_id = "chat-session-id"
    editor = NotebookEditor()
    notebook = editor.create_notebook("Python Notebook")
    notebook_json = notebook.model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id=session_id,
        allow_python_blocks=True,
    )

    try:
        with agent_context_scope(
            AgentContext(project_id=str(sample_project.id), session_id=session_id),
            tool_ctx=ToolExecutionContext(project_id=str(sample_project.id), session_id=session_id),
        ):
            result_json = await tools.add_python(
                notebook_id=notebook_id,
                code="print('hello')",
                title="Analysis block",
            )

        payload = json.loads(result_json)
        assert payload["success"] is True
        assert payload["blockId"]
    finally:
        unregister_session_context(session_id)


@pytest.mark.asyncio
async def test_add_python_materializes_missing_data_table_blocks(
    sample_project,
) -> None:
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Python Notebook")
    notebook_json = notebook.model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        allow_python_blocks=True,
    )
    run_context: RuntimeToolContext = TestRuntimeContext(
        session_state={
            "kontext": {
                "version": 1,
                "artifacts_by_id": {
                    data_id: {
                        "artifact_id": data_id,
                        "artifact_type": "DataTable",
                        "sql": "SELECT amount FROM bronze.transactions",
                        "title": "Transactions",
                    }
                },
                "data_identity_index": {},
            }
        }
    )

    result_json = await tools.add_python(
        notebook_id=notebook_id,
        code=(f"df = await kontext.load_data('{data_id}')\nprint(df)"),
        title="Analysis block",
        run_context=run_context,
    )

    payload = json.loads(result_json)
    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]

    assert payload["success"] is True
    assert len(saved_notebook.blocks) == 2

    first_block = saved_notebook.blocks[0].root
    second_block = saved_notebook.blocks[1].root
    assert isinstance(first_block, SqlBlock)
    assert isinstance(second_block, CodeBlock)
    assert first_block.data.data_ref is not None
    assert first_block.data.data_ref.data_id == data_id
    assert first_block.data.code == "SELECT amount FROM bronze.transactions"
    assert second_block.data.code.startswith("df = await kontext.load_data(")
    assert data_id in second_block.data.code


@pytest.mark.asyncio
def _managed_python_execution_result(
    *,
    project_id: str,
    run_id: str,
    code: str,
    outputs: list[CodeExecutionOutput],
    target_type: PythonExecutionTargetType,
) -> PythonExecutionServiceResult:
    now = datetime.now(UTC)
    return PythonExecutionServiceResult(
        execution_run=ExecutionRunModel.model_construct(
            id=run_id,
            project_id=project_id,
            owner_id=None,
            kind=ExecutionRunKind.JOB,
            status=ExecutionRunStatus.SUCCEEDED,
            name="Managed Python",
            progress=100,
            created_at=now,
            started_at=now,
            completed_at=now,
            error_message=None,
            result_data=None,
            source_job_run_id=run_id,
            root_run_id=run_id,
            parent_run_id=None,
            workflow_key=None,
            step_key=None,
            is_workflow_root=True,
        ),
        python_result=PythonExecutionResult(
            success=True,
            message="ok",
            outputs=outputs,
            target_type=target_type,
        ),
        code=code,
    )


@pytest.mark.asyncio
async def test_notebook_python_execution_attributes_runs_to_notebook_actor(sample_project):
    """Notebook-triggered block execution is attributed `notebook_tool`."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Python Notebook")
    code_block = editor.add_code_block("print('draft')", language="python", title="Draft code")
    notebook_json = notebook.model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_chat_session_service.return_value = None

    tools = NotebookPythonTools(project=sample_project, runtime_provider=provider)
    tools.python_execution_service = AsyncMock()
    tools.python_execution_service.execute_notebook_code_async = AsyncMock(
        return_value=PythonExecutionServiceResult(
            execution_run=ExecutionRunModel.model_construct(
                id="run-nb",
                kind=ExecutionRunKind.NOTEBOOK,
                status=ExecutionRunStatus.SUCCEEDED,
                created_at=datetime.now(UTC),
            ),
            python_result=PythonExecutionResult(
                success=True,
                message="Python execution completed successfully.",
                error=None,
                execution_run_id="run-nb",
                execution_mode=PythonExecutionMode.DRAFT,
                outputs=[CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))],
            ),
        )
    )

    session_id = "chat-session-id"
    try:
        with agent_context_scope(
            AgentContext(project_id=str(sample_project.id), session_id=session_id),
            tool_ctx=ToolExecutionContext(project_id=str(sample_project.id), session_id=session_id),
        ):
            result_json = await tools.execute_python_code(
                notebook_id=notebook_id,
                block_id=str(code_block.root.id),
                code="print('executed')",
            )
        payload = json.loads(result_json)
        assert payload["success"] is True
        assert payload["executionMode"] == "draft"

        execute_kwargs = (
            tools.python_execution_service.execute_notebook_code_async.await_args.kwargs
        )
        assert execute_kwargs["triggered_by"] == agent_actor("notebook_tool")
        # A code-override draft must not touch the notebook document.
        file_service_mock.update_notebook.assert_not_awaited()
    finally:
        unregister_session_context(session_id)


def _session_state_with_notebooks(
    notebook_ids: list[str],
) -> dict[str, Any]:
    """Session state whose shared store lists the given notebook artifacts."""
    session_state = create_kontext_session_state()
    store = SharedSessionStore(session_state)
    for notebook_id in notebook_ids:
        store.upsert_artifact_descriptor(
            artifact_id=notebook_id,
            artifact_type=ArtifactType.NOTEBOOK,
            title=f"Notebook {notebook_id}",
        )
    return session_state


@pytest.mark.asyncio
async def test_add_python_omitted_notebook_id_resolves_single_linked_notebook(
    sample_project,
):
    """An omitted notebook_id defaults to the chat session's one linked notebook."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    editor = NotebookEditor()
    editor.create_notebook("Python Notebook")
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock(spec=IFileServiceProtocol)
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)
    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        allow_python_blocks=True,
    )

    resolved, defaulted, error = await tools._resolve_notebook_id(
        None, TestRuntimeContext(session_state=_session_state_with_notebooks([notebook_id]))
    )

    assert resolved == notebook_id
    assert defaulted is True
    assert error is None


@pytest.mark.asyncio
async def test_add_python_omitted_notebook_id_without_linked_notebook_fails_recoverably(
    sample_project,
):
    """No linked notebook produces guidance naming the sanctioned recovery paths."""
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock(spec=IFileServiceProtocol)
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)
    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        allow_python_blocks=True,
    )

    _, _, error = await tools._resolve_notebook_id(
        None, TestRuntimeContext(session_state=create_kontext_session_state())
    )

    assert error is not None
    assert "notebook_id is required" in error
    assert "create_notebook" in error


@pytest.mark.asyncio
async def test_add_python_omitted_notebook_id_with_multiple_notebooks_lists_them(
    sample_project,
):
    """Mutations never guess: several linked notebooks fail with the id list."""
    first = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    second = "1eb96811-39fe-47a4-7e25-08de0be1d150"
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock(spec=IFileServiceProtocol)
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)
    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        allow_python_blocks=True,
    )

    _, _, error = await tools._resolve_notebook_id(
        None, TestRuntimeContext(session_state=_session_state_with_notebooks([first, second]))
    )

    assert error is not None
    assert first in error and second in error


@pytest.mark.asyncio
async def test_notebook_id_resolution_passthrough_and_empty_state(
    sample_project,
):
    """A provided id passes through unchanged; the fallback chain tolerates missing state."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    editor = NotebookEditor()
    editor.create_notebook("Python Notebook")
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock(spec=IFileServiceProtocol)
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)
    tools = NotebookTools(
        project=sample_project,
        runtime_provider=provider,
        allow_python_blocks=True,
    )

    resolved, defaulted, error = await tools._resolve_notebook_id(notebook_id, None)

    assert resolved == notebook_id
    assert defaulted is False
    assert error is None
