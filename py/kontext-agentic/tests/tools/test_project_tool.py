from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agent.tools import get_declared_tool_meta
from kontext.agentic.tools.project_tool import ProjectTools
from kontext.common.protocols import IFileServiceProtocol
from kontext.file.notebook.editor import NotebookEditor
from kontext.schema import (
    CodeBlock,
    CodeBlockData,
    CodeExecutionOutput,
    CodeTextOutput,
    NotebookBlock,
)


def _editor_notebook_json(blocks: list[NotebookBlock]) -> str:
    editor = NotebookEditor()
    editor.create_notebook("Pivot Notebook")
    for block in blocks:
        editor.add_block(block)
    return editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)


def _python_block(
    block_id: str,
    *,
    code: str = "import pandas as pd",
    outputs: list[CodeExecutionOutput] | None = None,
    is_executing: bool | None = None,
    last_executed: int | None = None,
    title: str | None = None,
) -> NotebookBlock:
    return NotebookBlock(
        CodeBlock(
            id=block_id,
            data=CodeBlockData(
                code=code,
                language="python",
                title=title,
                outputs=outputs,
                is_executing=is_executing,
                last_executed=last_executed,
            ),
        )
    )


def _project_tools(sample_project, file_service_mock) -> ProjectTools:
    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock()
    return ProjectTools(project=sample_project, runtime_provider=provider)


def test_inspect_notebook_python_state_tool_meta_emits_tool_call():
    meta = get_declared_tool_meta(ProjectTools.inspect_notebook_python_state)

    assert meta is not None
    assert meta.emit_tool_call is True
    assert meta.result_class is None


@pytest.mark.asyncio
async def test_inspect_notebook_python_state_flags_unexecuted_blocks(
    sample_project, mock_service_provider
):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    executed_block_id = "1eb96811-39fe-47a4-7e25-08de0be1d150"
    unexecuted_block_id = "1eb96811-39fe-47a4-7e25-08de0be1d151"
    executing_block_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.exists_by_id = AsyncMock(return_value=True)
    file_service_mock.get_file_content = AsyncMock(
        return_value=_editor_notebook_json(
            [
                _python_block(
                    executed_block_id,
                    title="Executed pivot",
                    outputs=[
                        CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))
                    ],
                    last_executed=1730000000000,
                ),
                _python_block(unexecuted_block_id, title="Draft pivot"),
                _python_block(executing_block_id, title="Running", is_executing=True),
            ]
        )
    )
    tools = _project_tools(sample_project, file_service_mock)

    payload = json.loads(await tools.inspect_notebook_python_state(notebook_id))

    assert payload["success"] is True
    assert payload["notebookId"] == notebook_id
    assert payload["hasUnexecutedBlocks"] is True
    assert payload["unexecutedBlockIds"] == [unexecuted_block_id]
    states = {block["blockId"]: block["executionState"] for block in payload["pythonBlocks"]}
    assert states[executed_block_id] == "executed"
    assert states[unexecuted_block_id] == "unexecuted"
    assert states[executing_block_id] == "executing"
    assert payload["pythonBlocks"][0]["outputCount"] == 1
    assert "1 unexecuted Python block" in payload["message"]


@pytest.mark.asyncio
async def test_inspect_notebook_python_state_all_executed(sample_project, mock_service_provider):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    executed_block_id = "1eb96811-39fe-47a4-7e25-08de0be1d150"

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.exists_by_id = AsyncMock(return_value=True)
    file_service_mock.get_file_content = AsyncMock(
        return_value=_editor_notebook_json(
            [
                _python_block(
                    executed_block_id,
                    outputs=[
                        CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content="ok"))
                    ],
                    last_executed=1730000000000,
                ),
            ]
        )
    )
    tools = _project_tools(sample_project, file_service_mock)

    payload = json.loads(await tools.inspect_notebook_python_state(notebook_id))

    assert payload["success"] is True
    assert payload["hasUnexecutedBlocks"] is False
    assert payload["unexecutedBlockIds"] == []
    assert "carry execution state" in payload["message"]


@pytest.mark.asyncio
async def test_inspect_notebook_python_state_reports_load_failure(
    sample_project, mock_service_provider
):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.exists_by_id = AsyncMock(return_value=False)
    file_service_mock.get_file_content = AsyncMock(return_value=None)
    tools = _project_tools(sample_project, file_service_mock)

    payload = json.loads(await tools.inspect_notebook_python_state(notebook_id))

    assert payload["success"] is False
    assert "Failed to load notebook" in payload["error"]


@pytest.mark.asyncio
async def test_inspect_notebook_python_state_requires_file_service(
    sample_project,
):
    provider = MagicMock()
    provider.get_file_service.return_value = None
    tools = ProjectTools(project=sample_project, runtime_provider=provider)

    payload = json.loads(
        await tools.inspect_notebook_python_state("1eb96811-39fe-47a4-7e25-08de0be1d149")
    )

    assert payload["success"] is False
    assert payload["error"] == "Notebook file service is not available in this runtime."


@pytest.mark.asyncio
async def test_inspect_notebooks_python_state_batch(sample_project, mock_service_provider):
    notebook_1 = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    notebook_2 = "2eb96811-39fe-47a4-7e25-08de0be1d150"
    unexecuted_block_id = "3eb96811-39fe-47a4-7e25-08de0be1d151"

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(
        return_value=_editor_notebook_json([_python_block(unexecuted_block_id)])
    )
    tools = _project_tools(sample_project, file_service_mock)

    payload = json.loads(await tools.inspect_notebooks_python_state([notebook_1, notebook_2]))

    assert payload["notebooksCount"] == 2
    assert payload["failedCount"] == 0
    assert [entry["notebookId"] for entry in payload["notebooks"]] == [notebook_1, notebook_2]
    assert all(entry["hasUnexecutedBlocks"] for entry in payload["notebooks"])


@pytest.mark.asyncio
async def test_inspect_notebooks_python_state_flags_invalid_guid(
    sample_project, mock_service_provider
):
    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=None)
    tools = _project_tools(sample_project, file_service_mock)

    payload = json.loads(await tools.inspect_notebooks_python_state(["not-a-guid"]))

    assert payload["success"] is False
    assert payload["failedCount"] == 1
    assert payload["notebooks"][0]["success"] is False
    assert "Invalid notebook_id" in payload["notebooks"][0]["error"]
