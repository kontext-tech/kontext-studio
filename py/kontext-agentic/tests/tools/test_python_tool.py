from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agent import (
    AgentContext,
    ToolExecutionContext,
    agent_context_scope,
    unregister_session_context,
)
from kontext.agent.tools import get_declared_tool_meta
from kontext.agentic.tools.python_tool import PythonTools
from kontext.common.jobs.trigger_actor import agent_actor
from kontext.common.protocols import IFileServiceProtocol
from kontext.execution import PythonExecutionServiceResult
from kontext.file.notebook.editor import NotebookEditor
from kontext.schema import (
    ArtifactType,
    CodeBlock,
    CodeExecutionOutput,
    CodeTextOutput,
    DataRef,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    NotebookBlock,
    NotebookDocument,
    PythonExecutionMode,
    PythonExecutionResult,
    PythonExecutionTargetType,
    PythonSavedTable,
    SqlBlock,
    SqlBlockData,
)


def test_execute_python_code_tool_meta_emits_result() -> None:
    meta = get_declared_tool_meta(PythonTools.execute_python_code)

    assert meta is not None
    assert meta.emit_tool_call is True
    assert meta.emit_result is True
    assert meta.external_execution is True


def test_execute_python_script_tool_meta_emits_result() -> None:
    meta = get_declared_tool_meta(PythonTools.execute_python_script)

    assert meta is not None
    assert meta.emit_tool_call is True
    assert meta.emit_result is True
    assert meta.external_execution is True


def test_python_tools_can_exclude_notebook_execution(sample_project) -> None:
    """The standalone Python agent leaves notebook execution to Notebook Agent."""
    tools = PythonTools(project=sample_project, include_notebook_execution=False)

    names = [tool.__name__ for tool in tools.get_tool_callables()]
    assert "execute_python_code" not in names
    assert "execute_python_script" in names
    assert "validate_python_code" in names


@pytest.mark.asyncio
async def test_execute_python_code_runs_draft_execution_without_persisting_notebook(
    sample_project,
) -> None:
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    persistent_data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Python Notebook")
    editor.add_block(
        NotebookBlock(
            SqlBlock(
                id="1eb96811-39fe-47a4-7e25-08de0be1d153",
                type="sql",
                data=SqlBlockData(
                    code="SELECT * FROM demo_table",
                    data_ref=DataRef(data_id=persistent_data_id),
                ),
            )
        )
    )
    code_block = editor.add_code_block(
        "print('old')",
        language="python",
        title="Draft code",
    )
    stored_content = {"value": notebook.model_dump_json(exclude_none=True, by_alias=True)}

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=stored_content["value"])
    file_service_mock.update_notebook = AsyncMock()

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_chat_session_service.return_value = None

    tools = PythonTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id="chat-session-id",
    )

    tools.python_execution_service = AsyncMock()
    tools.python_execution_service.execute_notebook_code_async = AsyncMock(
        return_value=PythonExecutionServiceResult(
            execution_run=ExecutionRunModel.model_construct(
                id="run-123",
                kind=ExecutionRunKind.NOTEBOOK,
                status=ExecutionRunStatus.SUCCEEDED,
                created_at=datetime.now(UTC),
            ),
            python_result=PythonExecutionResult(
                success=True,
                message="Python execution completed successfully.",
                error=None,
                execution_run_id="run-123",
                execution_mode=PythonExecutionMode.DRAFT,
                outputs=[CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))],
            ),
        )
    )

    override_code = f"df = await kontext.load_data('{persistent_data_id}')\nprint('executed')"
    session_id = "chat-session-id"
    try:
        with agent_context_scope(
            AgentContext(project_id=str(sample_project.id), session_id=session_id),
            tool_ctx=ToolExecutionContext(project_id=str(sample_project.id), session_id=session_id),
        ):
            result_json = await tools.execute_python_code(
                notebook_id=notebook_id,
                block_id=str(code_block.root.id),
                code=override_code,
            )
        payload = json.loads(result_json)
        assert payload["success"] is True
        assert payload["notebookId"] == notebook_id
        assert payload["executionRunId"] == "run-123"
        assert payload["executionMode"] == "draft"
        assert payload["targetType"] == "notebook"
        assert len(payload["actions"]) == 1
        assert payload["actions"][0]["actionType"] == "upsertBlock"
        assert payload["actions"][0]["payload"]["cid"] == str(code_block.root.id)
        assert payload["actions"][0]["payload"]["data"]["outputs"][0]["content"] == "ok"
        file_service_mock.update_notebook.assert_not_awaited()

        execute_kwargs = (
            tools.python_execution_service.execute_notebook_code_async.await_args.kwargs
        )
        assert execute_kwargs["project_id"] == sample_project.id
        assert execute_kwargs["notebook_id"] == notebook_id
        assert execute_kwargs["block_id"] == str(code_block.root.id)
        assert execute_kwargs["chat_session_id"] == "chat-session-id"
        assert (
            execute_kwargs.get("code") == override_code
            or execute_kwargs.get("code_override") == override_code
        )
        assert execute_kwargs["data_sources"] == {
            persistent_data_id: persistent_data_id,
            "df_1": persistent_data_id,
        }

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
        assert saved_code_block.data.code == "print('old')"
    finally:
        unregister_session_context(session_id)


@pytest.mark.asyncio
async def test_execute_python_script_runs_managed_session_execution(
    sample_project,
    monkeypatch,
) -> None:
    chat_session_service = MagicMock()
    provider = MagicMock()
    provider.get_file_service.return_value = None
    provider.get_chat_session_service.return_value = chat_session_service

    tools = PythonTools(
        project=sample_project,
        runtime_provider=provider,
        session_id="query-session-id",
        chat_session_id="chat-session-id",
        catalog_connection_id="1eb96811-39fe-47a4-7e25-08de0be1d166",
        default_namespace="analytics",
        default_entity_id="1eb96811-39fe-47a4-7e25-08de0be1d167",
        engine_type="DuckDB",
    )
    tools.list_artifact_descriptors = MagicMock(return_value=[])
    tools.python_execution_service = AsyncMock()
    tools.python_execution_service.execute_script_async = AsyncMock(
        return_value=PythonExecutionServiceResult(
            execution_run=ExecutionRunModel.model_construct(
                id="run-script-123",
                kind=ExecutionRunKind.AGENT,
                status=ExecutionRunStatus.SUCCEEDED,
                created_at=datetime.now(UTC),
            ),
            python_result=PythonExecutionResult(
                success=True,
                message="Python execution completed successfully.",
                error=None,
                execution_run_id="run-script-123",
                target_type=PythonExecutionTargetType.SESSION,
                outputs=[CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))],
            ),
        )
    )
    execute_chat_session_python_script = AsyncMock(
        return_value=PythonExecutionServiceResult(
            execution_run=ExecutionRunModel.model_construct(
                id="run-script-123",
                kind=ExecutionRunKind.AGENT,
                status=ExecutionRunStatus.SUCCEEDED,
                created_at=datetime.now(UTC),
            ),
            python_result=PythonExecutionResult(
                success=True,
                message="Python execution completed successfully.",
                error=None,
                execution_run_id="run-script-123",
                target_type=PythonExecutionTargetType.SESSION,
                outputs=[CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))],
            ),
        )
    )
    monkeypatch.setattr(
        "kontext.agentic.tools.python_tool.execute_chat_session_python_script",
        execute_chat_session_python_script,
    )

    result_json = await tools.execute_python_script(
        code="print('ok')",
    )

    payload = json.loads(result_json)
    assert payload["success"] is True
    assert payload["executionRunId"] == "run-script-123"
    assert payload["targetType"] == "session"

    await_args = execute_chat_session_python_script.await_args
    assert await_args is not None
    execute_kwargs = await_args.kwargs
    assert execute_kwargs["project_id"] == sample_project.id
    assert execute_kwargs["chat_session_id"] == "chat-session-id"
    assert execute_kwargs["code"] == "print('ok')"
    assert execute_kwargs["chat_session_service"] is chat_session_service
    assert execute_kwargs["python_execution_service"] is tools.python_execution_service
    assert execute_kwargs["triggered_by"] == agent_actor("python_tool")


@pytest.mark.asyncio
async def test_execute_python_script_requires_chat_session_context(
    sample_project,
) -> None:
    provider = MagicMock()
    provider.get_file_service.return_value = None
    provider.get_chat_session_service.return_value = MagicMock()

    tools = PythonTools(
        project=sample_project,
        runtime_provider=provider,
    )
    tools.python_execution_service = AsyncMock()
    result_json = await tools.execute_python_script(code="print('ok')")

    payload = json.loads(result_json)
    assert payload["success"] is False
    assert payload["targetType"] == "session"
    assert "requires an active chat session" in payload["message"]
    tools.python_execution_service.execute_script_async.assert_not_awaited()


async def test_execute_python_script_registers_saved_tables_in_shared_state(
    sample_project,
    monkeypatch,
) -> None:
    """``kontext.save_table`` outputs flow to shared session state via the toolkit link.

    The execution bridge persists the durable table and links the chat session
    record; the tool layer then registers the descriptor so other team members
    can resolve the saved table by id.
    """
    provider = MagicMock()
    provider.get_file_service.return_value = None
    provider.get_chat_session_service.return_value = MagicMock()

    tools = PythonTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id="chat-session-id",
    )
    tools.list_artifact_descriptors = MagicMock(return_value=[])
    tools.link_artifact_to_session = AsyncMock(return_value=True)

    envelope = PythonExecutionResult(
        success=True,
        message="Python execution completed successfully.",
        error=None,
        execution_run_id="run-script-123",
        target_type=PythonExecutionTargetType.SESSION,
        outputs=[CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))],
        saved_tables=[PythonSavedTable(data_table_id="file-77", title="Res", row_count=3)],
    )
    monkeypatch.setattr(
        "kontext.agentic.tools.python_tool.execute_chat_session_python_script",
        AsyncMock(
            return_value=PythonExecutionServiceResult(
                execution_run=ExecutionRunModel.model_construct(
                    id="run-script-123",
                    kind=ExecutionRunKind.AGENT,
                    status=ExecutionRunStatus.SUCCEEDED,
                    created_at=datetime.now(UTC),
                ),
                python_result=envelope,
            )
        ),
    )

    result_json = await tools.execute_python_script(code="kontext.save_table(df, 'Res')")

    payload = json.loads(result_json)
    assert payload["success"] is True
    assert payload["savedTables"][0]["dataTableId"] == "file-77"

    tools.link_artifact_to_session.assert_awaited_once()
    assert tools.link_artifact_to_session.await_args is not None
    kwargs = tools.link_artifact_to_session.await_args.kwargs
    assert kwargs["artifact_id"] == "file-77"
    assert kwargs["artifact_type"] == ArtifactType.DATATABLE
    assert kwargs["title"] == "Res"
    assert kwargs["row_count"] == 3
