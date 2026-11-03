"""Notebook CRUD and block-content tool tests for NotebookTools."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agent import render_tool_schema
from kontext.agentic.tools.notebook_tool import NotebookTools
from kontext.common.protocols import IFileServiceProtocol, IQuerySessionServiceProtocol
from kontext.file.notebook.editor import NotebookEditor
from kontext.schema import (
    BoxChartType,
    CodeBlock,
    CodeLanguage,
    DualAxesChartType,
    HeaderBlock,
    ListBlock,
    NotebookBlock,
    NotebookBlockType,
    NotebookDocument,
    ParagraphBlock,
    RadarCoordinateType,
    SqlBlock,
    SqlBlockData,
)

if TYPE_CHECKING:
    from kontext.agent import RuntimeToolContext

from .conftest import TestRuntimeContext


def test_generate_unique_notebook_name(mock_service_provider, sample_project):
    """Test the _generate_unique_notebook_name method."""
    notebook_tools = NotebookTools(project=sample_project, runtime_provider=mock_service_provider)

    # Test with a base name without an extension
    base_name1 = "My Test Notebook"
    unique_name1 = notebook_tools._generate_unique_notebook_name(base_name1)

    # Check format: "Name-short_id"
    assert unique_name1.startswith(f"{base_name1}-")
    # Extract ID part and check length (8 chars)
    id_part = unique_name1[len(base_name1) + 1 :]
    assert len(id_part) == 8

    # Test with a base name that includes an extension
    base_name2 = "My Test Notebook.kontext"
    unique_name2 = notebook_tools._generate_unique_notebook_name(base_name2)
    assert unique_name2.startswith("My Test Notebook-")
    assert unique_name2.endswith(".kontext")
    id_part2 = unique_name2[len("My Test Notebook-") : -len(".kontext")]
    assert len(id_part2) == 8

    # Test with a name that contains dots and a file extension
    base_name3 = "notebook.v1.final"
    unique_name3 = notebook_tools._generate_unique_notebook_name(base_name3)
    assert unique_name3.startswith("notebook.v1-")
    assert unique_name3.endswith(".final")
    id_part3 = unique_name3[len("notebook.v1-") : -len(".final")]
    assert len(id_part3) == 8


async def test_add_summary_adds_header_and_list_blocks(sample_project):
    """add_summary should create a header block (level 2) and a list block, then save both."""
    # Arrange initial empty notebook content
    editor = NotebookEditor()
    nb = editor.create_notebook("Test Notebook")
    notebook_json = nb.model_dump_json(exclude_none=True, by_alias=True)

    # Create a FileService mock that returns the notebook JSON and records updates
    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()

    # QuerySessionService is not used by add_summary, but provide a stub
    query_session_service_mock = MagicMock(spec=IQuerySessionServiceProtocol)

    # Factory that returns appropriate services based on requested class
    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = query_session_service_mock

    tools = NotebookTools(project=sample_project, runtime_provider=provider)

    # Act
    title = "Summary Title"
    points = ["Point 1", "Point 2"]
    # Use valid GUID format for notebook_id and project_id
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    result_json = await tools.add_summary(
        notebook_id=notebook_id, title=title, points=points, position=0
    )

    # Assert result payload basics
    import json

    payload = json.loads(result_json)
    assert payload["success"] is True
    assert "blockIds" in payload
    assert len(payload["blockIds"]) == 2  # header + list

    # Assert we saved a notebook with two blocks in expected order
    assert file_service_mock.update_notebook.call_count == 1
    call_args = file_service_mock.update_notebook.call_args
    # Support args or kwargs extraction
    saved_notebook = None
    if call_args and call_args.args and len(call_args.args) >= 2:
        saved_notebook = call_args.args[1]
    elif call_args and call_args.kwargs and "notebook" in call_args.kwargs:
        saved_notebook = call_args.kwargs["notebook"]

    assert saved_notebook is not None
    assert len(saved_notebook.blocks) == 2
    assert isinstance(saved_notebook.blocks[0].root, HeaderBlock)
    assert saved_notebook.blocks[0].root.data.level == 2
    assert saved_notebook.blocks[0].root.data.text == title
    assert isinstance(saved_notebook.blocks[1].root, ListBlock)
    # Ensure list items reflect the provided points
    list_items = saved_notebook.blocks[1].root.data.items
    assert [item.content for item in list_items] == points


@pytest.mark.asyncio
async def test_add_paragraph_markdown_parsing(sample_project):
    """add_paragraph should parse markdown into multiple blocks."""
    from kontext.schema import DelimiterBlock, ParagraphBlock, QuoteBlock, TableBlock

    # Setup
    editor = NotebookEditor()
    nb = editor.create_notebook("Test Notebook")
    notebook_json = nb.model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    tools = NotebookTools(project=sample_project, runtime_provider=provider)

    # Complex markdown
    markdown_text = """# Header 1
## Header 2
This is a paragraph with **bold** and *italic* and [a link](https://example.com).

* Item 1
* Item 2 with `code`

1. Ordered 1
2. Ordered 2

> This is a quote

```python
print("hello world")
```

---

| Col 1 | Col 2 |
|-------|-------|
| Val 1 | Val 2 |
"""

    # Act
    import json

    result_json = await tools.add_paragraph(notebook_id=notebook_id, text=markdown_text)

    # Assert
    payload = json.loads(result_json)
    assert payload["success"] is True

    # Verify blocks saved
    file_service_mock.update_notebook.assert_called_once()
    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]
    blocks = saved_notebook.blocks

    # Check block types in order
    assert isinstance(blocks[0].root, HeaderBlock)
    assert blocks[0].root.data.level == 2
    assert blocks[0].root.data.text == "Header 1"

    assert isinstance(blocks[1].root, HeaderBlock)
    assert blocks[1].root.data.level == 2
    assert blocks[1].root.data.text == "Header 2"

    assert isinstance(blocks[2].root, ParagraphBlock)
    expected_html = (
        'This is a paragraph with <b>bold</b> and <i>italic</i> and <a href="https://example.com" '
        'target="_blank">a link</a>.'
    )
    assert blocks[2].root.data.text == expected_html

    assert isinstance(blocks[3].root, ListBlock)
    assert blocks[3].root.data.items[0].content == "Item 1"
    assert blocks[3].root.data.items[1].content == "Item 2 with <code>code</code>"

    assert isinstance(blocks[5].root, QuoteBlock)
    assert blocks[5].root.data.text == "This is a quote"

    assert isinstance(blocks[6].root, CodeBlock)
    assert blocks[6].root.data.code == 'print("hello world")'

    assert isinstance(blocks[7].root, DelimiterBlock)

    assert isinstance(blocks[8].root, TableBlock)
    assert blocks[8].root.data.content[0] == ["Col 1", "Col 2"]
    assert blocks[8].root.data.content[1] == ["Val 1", "Val 2"]


@pytest.mark.asyncio
async def test_add_header_rejects_out_of_range_level(sample_project):
    editor = NotebookEditor()
    nb = editor.create_notebook("Test Notebook")
    notebook_json = nb.model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(project=sample_project, runtime_provider=provider)

    result_json = await tools.add_header(
        notebook_id="1eb96811-39fe-47a4-7e25-08de0be1d149",
        text="Notebook Title",
        level=1,
    )

    payload = json.loads(result_json)
    assert payload["success"] is False
    assert "Header level must be between 2 and 5" in payload.get(
        "error", payload.get("message", "")
    )
    file_service_mock.update_notebook.assert_not_called()


@pytest.mark.asyncio
async def test_add_data_table_preserves_source_sql_for_reuse(sample_project):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Notebook")
    notebook_json = notebook.model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()
    file_service_mock.exists_by_id = AsyncMock(return_value=True)

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(project=sample_project, runtime_provider=provider)
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

    result_json = await tools.add_data_table(
        notebook_id=notebook_id,
        data_table_id=data_id,
        run_context=run_context,
    )

    payload = json.loads(result_json)
    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]
    saved_sql_block = next(
        block.root for block in saved_notebook.blocks if isinstance(block.root, SqlBlock)
    )
    assert saved_sql_block.data.data_ref is not None

    assert payload["success"] is True
    assert saved_sql_block.data.code == "SELECT amount FROM bronze.transactions"
    assert saved_sql_block.data.data_ref.data_id == data_id
    assert saved_sql_block.data.data_ref.code == "SELECT amount FROM bronze.transactions"
    assert saved_sql_block.data.data_ref.language == CodeLanguage.SQL


@pytest.mark.asyncio
def test_notebook_tool_exposes_enum_choices_in_tool_schema(mock_service_provider, sample_project):
    tools = NotebookTools(project=sample_project, runtime_provider=mock_service_provider)

    box_schema = render_tool_schema(tools.add_box_chart, strict=False)["parameters"]
    assert box_schema["properties"]["box_type"]["anyOf"][0]["enum"] == [
        BoxChartType.BOX.value,
        BoxChartType.BOXPLOT.value,
    ]

    radar_schema = render_tool_schema(tools.add_radar_chart, strict=False)["parameters"]
    assert radar_schema["properties"]["coordinate_type"]["anyOf"][0]["enum"] == [
        RadarCoordinateType.RADAR.value,
        RadarCoordinateType.POLAR.value,
    ]

    dual_axes_schema = render_tool_schema(tools.add_dual_axes_chart, strict=False)["parameters"]
    assert dual_axes_schema["properties"]["left_chart_type"]["enum"] == [
        DualAxesChartType.INTERVAL.value,
        DualAxesChartType.LINE.value,
        DualAxesChartType.AREA.value,
    ]
    assert dual_axes_schema["properties"]["right_chart_type"]["enum"] == [
        DualAxesChartType.INTERVAL.value,
        DualAxesChartType.LINE.value,
        DualAxesChartType.AREA.value,
    ]


@pytest.mark.asyncio
async def test_parallel_block_mutations_do_not_lose_updates(sample_project):
    """Concurrent tool calls on one turn must not lose notebook updates.

    Agno gathers all tool calls of a single assistant turn concurrently, so
    the toolkit serializes load -> mutate -> save cycles over one shared
    editor (regression for the observed parallel add_header/add_paragraph/
    add_data_table run where only the header landed on disk).
    """
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Parallel Notebook")
    storage = {notebook_id: notebook.model_dump_json(exclude_none=True, by_alias=True)}

    def _read_content(_project_id: str, file_id: str) -> str:
        return storage[str(file_id)]

    def _record_update(**kwargs):
        saved = kwargs["notebook"]
        storage[str(kwargs["file_id"])] = saved.model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(side_effect=_read_content)
    file_service_mock.update_notebook = AsyncMock(side_effect=_record_update)
    file_service_mock.exists_by_id = AsyncMock(return_value=True)

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(project=sample_project, runtime_provider=provider)

    results = await asyncio.gather(
        tools.add_header(
            notebook_id=notebook_id,
            text="Customers by Country and Age Band",
            level=2,
        ),
        tools.add_paragraph(
            notebook_id=notebook_id,
            text="This notebook visualizes the distribution of customers.",
        ),
        tools.add_summary(
            notebook_id=notebook_id,
            title="Key takeaways",
            points=["Aggregation is a durable result set."],
        ),
    )

    payloads = [json.loads(result) for result in results]
    assert all(payload["success"] is True for payload in payloads)

    # Every operation recorded and retained its own mutation action instead
    # of having them stolen by a concurrent take_actions() call.
    for payload in payloads:
        assert payload.get("actions"), "mutation lost its recorded actions"

    final_notebook = NotebookDocument.model_validate_json(storage[notebook_id])
    block_types = [block.root.type for block in final_notebook.blocks]
    assert block_types.count(NotebookBlockType.HEADER) == 2
    assert block_types.count(NotebookBlockType.PARAGRAPH) == 1
    assert block_types.count(NotebookBlockType.LIST) == 1


@pytest.mark.asyncio
async def test_edit_list_block_replaces_list_items(sample_project):
    """edit_list_block edits list blocks without delete-and-re-add churn."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"

    editor = NotebookEditor()
    editor.create_notebook("Editing Lists")
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)
    storage = {notebook_id: notebook_json}
    tools = _persisting_notebook_tools(sample_project, storage)

    added = json.loads(
        await tools.add_list(notebook_id=notebook_id, items=["Old point 1", "Old point 2"])
    )
    block_id = added["blockId"]

    edited = json.loads(
        await tools.edit_list_block(
            notebook_id=notebook_id,
            block_id=block_id,
            items=["The aggregation is a durable, reusable SQL result set."],
            style="unordered",
        )
    )

    assert edited["success"] is True
    assert edited["actions"], "list edit should record an upsertBlock action"
    # The returned block must reflect the edit, not the pre-edit snapshot.
    assert "durable, reusable SQL result set" in json.dumps(edited["block"])

    final_notebook = NotebookDocument.model_validate_json(storage[notebook_id])
    edited_block = next(b for b in final_notebook.blocks if str(b.root.id) == block_id)
    assert isinstance(edited_block.root, ListBlock)
    assert [item.content for item in edited_block.root.data.items] == [
        "The aggregation is a durable, reusable SQL result set."
    ]

    rejected = json.loads(
        await tools.edit_list_block(
            notebook_id=notebook_id,
            block_id=block_id,
            items=["x"],
            style="invalid",
        )
    )
    assert rejected["success"] is False
    assert "Invalid list style" in rejected["message"]


def _persisting_notebook_tools(sample_project, storage: dict[str, str]) -> NotebookTools:
    def _read_content(_project_id: str, file_id: str) -> str:
        return storage[str(file_id)]

    def _record_update(**kwargs):
        storage[str(kwargs["file_id"])] = kwargs["notebook"].model_dump_json(
            exclude_none=True, by_alias=True
        )

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(side_effect=_read_content)
    file_service_mock.update_notebook = AsyncMock(side_effect=_record_update)

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)
    return NotebookTools(project=sample_project, runtime_provider=provider)


@pytest.mark.asyncio
async def test_edit_block_replaces_paragraph_with_flat_data(sample_project):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    editor = NotebookEditor()
    editor.create_notebook("Editing Paragraphs")
    storage = {notebook_id: editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)}
    tools = _persisting_notebook_tools(sample_project, storage)

    added = json.loads(
        await tools.add_paragraph(notebook_id=notebook_id, text="Old paragraph text")
    )
    block_id = added["blockId"]

    edited = json.loads(
        await tools.edit_block(
            notebook_id=notebook_id,
            block_id=block_id,
            data={"text": "New paragraph text"},
        )
    )

    assert edited["success"] is True
    final_notebook = NotebookDocument.model_validate_json(storage[notebook_id])
    edited_block = next(b for b in final_notebook.blocks if str(b.root.id) == block_id)
    assert isinstance(edited_block.root, ParagraphBlock)
    assert "New paragraph text" in edited_block.root.data.text


@pytest.mark.asyncio
async def test_edit_block_validates_against_existing_block_type(sample_project):
    """A code-shaped payload must not silently replace an SQL block's data."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    block_id = "1eb96811-39fe-47a4-7e25-08de0be1d153"

    editor = NotebookEditor()
    editor.create_notebook("Editing SQL")
    editor.add_block(
        NotebookBlock(
            SqlBlock(
                id=block_id,
                type="sql",
                data=SqlBlockData(code="SELECT 1", title="Q1"),
            )
        )
    )
    storage = {notebook_id: editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)}
    tools = _persisting_notebook_tools(sample_project, storage)

    edited = json.loads(
        await tools.edit_block(
            notebook_id=notebook_id,
            block_id=block_id,
            data={"code": "SELECT 2", "title": "Q2"},
        )
    )

    assert edited["success"] is True
    final_notebook = NotebookDocument.model_validate_json(storage[notebook_id])
    edited_block = next(b for b in final_notebook.blocks if str(b.root.id) == block_id)
    assert isinstance(edited_block.root, SqlBlock)
    assert edited_block.root.data.code == "SELECT 2"
    assert edited_block.root.data.title == "Q2"


@pytest.mark.asyncio
async def test_edit_block_rejects_data_for_a_different_block_type(sample_project):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    editor = NotebookEditor()
    editor.create_notebook("Editing Wrong Type")
    storage = {notebook_id: editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)}
    tools = _persisting_notebook_tools(sample_project, storage)

    added = json.loads(await tools.add_paragraph(notebook_id=notebook_id, text="A paragraph"))

    edited = json.loads(
        await tools.edit_block(
            notebook_id=notebook_id,
            block_id=added["blockId"],
            data={"code": "SELECT 1"},
        )
    )

    assert edited["success"] is False


@pytest.mark.asyncio
async def test_get_notebooks_and_blocks_batch_aggregate_results(
    sample_project, mock_service_provider
):
    tools = NotebookTools(project=sample_project, runtime_provider=mock_service_provider)
    tools.get_notebook = AsyncMock(
        return_value=json.dumps({"success": True, "notebookId": "n1", "message": "ok"})
    )
    tools.get_block = AsyncMock(
        return_value=json.dumps(
            {"success": True, "notebookId": "n1", "blockId": "b1", "message": "ok"}
        )
    )

    notebooks_payload = json.loads(await tools.get_notebooks(["n1", "n2"]))
    blocks_payload = json.loads(await tools.get_blocks("n1", ["b1"]))

    assert notebooks_payload["type"] == "notebook_batch"
    assert notebooks_payload["notebooksCount"] == 2
    assert notebooks_payload["failedCount"] == 0
    assert tools.get_notebook.await_count == 2

    assert blocks_payload["type"] == "notebook_block_batch"
    assert blocks_payload["blocksCount"] == 1
    assert blocks_payload["failedCount"] == 0
    tools.get_block.assert_awaited_once_with("n1", "b1")


def _notebook_tools_for_stored_notebook(sample_project, notebook_json: str):
    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()
    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)
    tools = NotebookTools(project=sample_project, runtime_provider=provider)
    return tools, file_service_mock


@pytest.mark.asyncio
async def test_delete_blocks_deletes_multiple_in_one_call(sample_project):
    from kontext.schema import ParagraphBlock, ParagraphBlockData

    block_ids = [
        "1eb96811-39fe-47a4-7e25-08de0be1d101",
        "1eb96811-39fe-47a4-7e25-08de0be1d102",
        "1eb96811-39fe-47a4-7e25-08de0be1d103",
    ]
    editor = NotebookEditor()
    editor.create_notebook("Delete Notebook")
    for block_id in block_ids:
        editor.add_block(
            NotebookBlock(ParagraphBlock(id=block_id, data=ParagraphBlockData(text=block_id)))
        )
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)
    tools, file_service_mock = _notebook_tools_for_stored_notebook(sample_project, notebook_json)

    payload = json.loads(
        await tools.delete_blocks(
            notebook_id="1eb96811-39fe-47a4-7e25-08de0be1d149",
            block_ids=[block_ids[0], block_ids[2]],
        )
    )

    assert payload["success"] is True
    assert payload["blocksCount"] == 2
    assert set(payload["blockIds"]) == {block_ids[0], block_ids[2]}

    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]
    assert [str(block.root.id) for block in saved_notebook.blocks] == [block_ids[1]]


@pytest.mark.asyncio
async def test_get_notebook_outline_returns_compact_blocks_without_payloads(sample_project):
    from kontext.schema import ParagraphBlock, ParagraphBlockData

    block_id = "1eb96811-39fe-47a4-7e25-08de0be1d201"
    editor = NotebookEditor()
    editor.create_notebook("Outline Notebook")
    editor.add_block(
        NotebookBlock(ParagraphBlock(id=block_id, data=ParagraphBlockData(text="hello")))
    )
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)
    tools, _ = _notebook_tools_for_stored_notebook(sample_project, notebook_json)

    payload = json.loads(await tools.get_notebook_outline("1eb96811-39fe-47a4-7e25-08de0be1d149"))

    assert payload["success"] is True
    assert payload["blocksCount"] == 1
    block = payload["blocks"][0]
    assert block["blockId"] == block_id
    assert block["type"] == "paragraph"
    # The outline must not carry the (potentially huge) block payload.
    assert "data" not in block
    assert "text" not in block
