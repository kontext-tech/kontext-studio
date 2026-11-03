"""Chart-block tool tests for NotebookTools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agentic.tools.notebook_tool import NotebookTools
from kontext.common.protocols import IFileServiceProtocol, IQuerySessionServiceProtocol
from kontext.file.charts import ChartService
from kontext.file.notebook.editor import NotebookEditor
from kontext.schema import (
    ChartBlock,
    ChartSpec,
    ChartType,
    CodeLanguage,
    DataColumn,
    DataRef,
    DataTable,
    InlineData,
    NotebookBlock,
    SqlBlock,
    SqlBlockData,
)

if TYPE_CHECKING:
    from kontext.agent import RuntimeToolContext

from .conftest import TestRuntimeContext


async def test_add_stock_chart_adds_chart_block_with_ohlc_fields(sample_project):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    editor = NotebookEditor()
    editor.create_notebook("Notebook")
    editor.add_block(
        NotebookBlock(
            SqlBlock(
                id="1eb96811-39fe-47a4-7e25-08de0be1d153",
                type="sql",
                data=SqlBlockData(
                    code="SELECT * FROM market_prices",
                    data_ref=DataRef(
                        data_id=data_id,
                        language=CodeLanguage.SQL,
                    ),
                ),
            )
        )
    )
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()
    file_service_mock.exists_by_id = AsyncMock(return_value=True)
    file_service_mock.get_data_table_file = AsyncMock(
        return_value=InlineData(
            title="Market Prices",
            table=DataTable(
                columns=[
                    DataColumn(name="trade_date", type="string"),
                    DataColumn(name="open_price", type="number"),
                    DataColumn(name="close_price", type="number"),
                    DataColumn(name="low_price", type="number"),
                    DataColumn(name="high_price", type="number"),
                ],
                rows=[
                    ["2024-01-02", 101.2, 104.8, 99.4, 106.1],
                    ["2024-01-03", 104.8, 103.5, 102.3, 107.0],
                ],
                row_count=2,
            ),
        )
    )

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(project=sample_project, runtime_provider=provider)

    result_json = await tools.add_stock_chart(
        notebook_id=notebook_id,
        data_table_id=data_id,
        x_field="trade_date",
        open_field="open_price",
        close_field="close_price",
        low_field="low_price",
        high_field="high_price",
        title="Daily Price Movement",
    )

    payload = json.loads(result_json)
    assert payload["success"] is True

    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]
    stock_block = saved_notebook.blocks[-1].root
    assert isinstance(stock_block, ChartBlock)
    assert stock_block.data.config.root.chart_type == "stock"
    assert stock_block.data.config.root.x_field == "trade_date"
    assert stock_block.data.config.root.y_field == [
        "open_price",
        "close_price",
        "low_price",
        "high_price",
    ]


@pytest.mark.asyncio
async def test_add_line_chart_auto_attaches_missing_data_table(sample_project):
    """A chart for a data table not yet in the notebook auto-adds its SQL block."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Notebook")
    notebook_json = notebook.model_dump_json(exclude_none=True, by_alias=True)

    inline_data = InlineData(
        title="Sales",
        table=DataTable(
            columns=[
                DataColumn(name="region", type="string"),
                DataColumn(name="revenue", type="number"),
            ],
        ),
    )

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()
    file_service_mock.exists_by_id = AsyncMock(return_value=True)
    file_service_mock.get_data_table_file = AsyncMock(return_value=inline_data)

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
                        "sql": "SELECT region, revenue FROM sales",
                        "title": "Sales",
                    }
                },
                "data_identity_index": {},
            }
        }
    )

    result_json = await tools.add_line_chart(
        notebook_id=notebook_id,
        data_table_id=data_id,
        x_field="region",
        y_field="revenue",
        title="Revenue by Region",
        run_context=run_context,
    )

    payload = json.loads(result_json)
    assert payload["success"] is True

    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]
    # The data table block is attached before the chart block.
    assert len(saved_notebook.blocks) == 2

    sql_block = saved_notebook.blocks[0].root
    chart_block = saved_notebook.blocks[1].root
    assert isinstance(sql_block, SqlBlock)
    assert isinstance(chart_block, ChartBlock)
    assert sql_block.data.data_ref is not None
    assert sql_block.data.data_ref.data_id == data_id
    assert sql_block.data.code == "SELECT region, revenue FROM sales"
    assert chart_block.data.data_ref is not None
    assert chart_block.data.data_ref.data_id == data_id


@pytest.mark.asyncio
async def test_add_line_chart_reuses_existing_data_table_block(sample_project):
    """An already-attached data table is not duplicated when adding a chart."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    editor = NotebookEditor()
    editor.create_notebook("Notebook")
    editor.add_block(
        NotebookBlock(
            SqlBlock(
                id="1eb96811-39fe-47a4-7e25-08de0be1d153",
                type="sql",
                data=SqlBlockData(
                    code="SELECT region, revenue FROM sales",
                    data_ref=DataRef(data_id=data_id, language=CodeLanguage.SQL),
                ),
            )
        )
    )
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()
    file_service_mock.get_data_table_file = AsyncMock(
        return_value=InlineData(
            title="Sales",
            table=DataTable(
                columns=[
                    DataColumn(name="region", type="string"),
                    DataColumn(name="revenue", type="number"),
                ],
            ),
        )
    )

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(project=sample_project, runtime_provider=provider)

    result_json = await tools.add_line_chart(
        notebook_id=notebook_id,
        data_table_id=data_id,
        x_field="region",
        y_field="revenue",
        title="Revenue by Region",
    )

    payload = json.loads(result_json)
    assert payload["success"] is True

    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]
    sql_blocks = [b.root for b in saved_notebook.blocks if isinstance(b.root, SqlBlock)]
    assert len(sql_blocks) == 1
    assert len(saved_notebook.blocks) == 2
    assert isinstance(saved_notebook.blocks[1].root, ChartBlock)


@pytest.mark.asyncio
async def test_add_line_chart_errors_when_data_table_unresolvable(sample_project):
    """A genuinely unresolvable data table still fails loudly and writes nothing."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    editor = NotebookEditor()
    notebook = editor.create_notebook("Notebook")
    notebook_json = notebook.model_dump_json(exclude_none=True, by_alias=True)

    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()
    file_service_mock.exists_by_id = AsyncMock(return_value=False)

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)

    tools = NotebookTools(project=sample_project, runtime_provider=provider)

    result_json = await tools.add_line_chart(
        notebook_id=notebook_id,
        data_table_id=data_id,
        x_field="region",
        y_field="revenue",
        title="Revenue by Region",
    )

    payload = json.loads(result_json)
    assert payload["success"] is False
    assert "could not be resolved" in payload["message"]
    # Nothing is persisted when the auto-attach cannot resolve the data table.
    file_service_mock.update_notebook.assert_not_called()


@pytest.mark.asyncio
async def test_edit_block_chart_auto_attaches_missing_data_table(sample_project):
    """Editing a chart block onto an unattached data table attaches it too."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    block_id = "1eb96811-39fe-47a4-7e25-08de0be1d153"
    old_data_id = "1eb96811-39fe-47a4-7e25-08de0be1d154"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d152"

    editor = NotebookEditor()
    editor.create_notebook("Notebook")
    editor.add_block(
        NotebookBlock(
            ChartBlock(
                id=block_id,
                type="chart",
                data=ChartSpec(
                    config=ChartService.create_line_chart_config(
                        title="Old", x_field="region", y_field="revenue"
                    ),
                    data_ref=DataRef(data_id=old_data_id, language=CodeLanguage.SQL),
                ),
            )
        )
    )
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)

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
                        "sql": "SELECT region, revenue FROM sales",
                        "title": "Sales",
                    }
                },
                "data_identity_index": {},
            }
        }
    )

    result_json = await tools.edit_block(
        notebook_id=notebook_id,
        block_id=block_id,
        data=ChartSpec(
            config=ChartService.create_line_chart_config(
                title="New", x_field="region", y_field="revenue"
            ),
            data_ref=DataRef(data_id=data_id, language=CodeLanguage.SQL),
        ).model_dump(by_alias=True, exclude_none=True),
        run_context=run_context,
    )

    payload = json.loads(result_json)
    assert payload["success"] is True

    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]
    sql_blocks = [b.root for b in saved_notebook.blocks if isinstance(b.root, SqlBlock)]
    chart_blocks = [b.root for b in saved_notebook.blocks if isinstance(b.root, ChartBlock)]
    assert len(sql_blocks) == 1
    assert sql_blocks[0].data.data_ref is not None
    assert sql_blocks[0].data.data_ref.data_id == data_id
    assert len(chart_blocks) == 1
    assert str(chart_blocks[0].id) == block_id
    assert chart_blocks[0].data.data_ref is not None
    assert chart_blocks[0].data.data_ref.data_id == data_id


def _chart_notebook_editor(block_id: str, data_id: str) -> NotebookEditor:
    editor = NotebookEditor()
    editor.create_notebook("Notebook")
    editor.add_block(
        NotebookBlock(
            ChartBlock(
                id=block_id,
                type="chart",
                data=ChartSpec(
                    config=ChartService.create_line_chart_config(
                        title="Old", x_field="region", y_field="revenue"
                    ),
                    data_ref=DataRef(data_id=data_id, language=CodeLanguage.SQL),
                ),
            )
        )
    )
    return editor


def _chart_notebook_tools(sample_project, notebook_json: str) -> tuple[NotebookTools, MagicMock]:
    file_service_mock = MagicMock(spec=IFileServiceProtocol)
    file_service_mock.get_file_content = AsyncMock(return_value=notebook_json)
    file_service_mock.update_notebook = AsyncMock()
    file_service_mock.exists_by_id = AsyncMock(return_value=True)

    provider = MagicMock()
    provider.get_file_service.return_value = file_service_mock
    provider.get_query_session_service.return_value = MagicMock(spec=IQuerySessionServiceProtocol)
    return NotebookTools(project=sample_project, runtime_provider=provider), file_service_mock


@pytest.mark.asyncio
async def test_edit_chart_block_updates_config_in_place(sample_project):
    """A flat config replaces the chart config and keeps block id + data ref."""
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    block_id = "1eb96811-39fe-47a4-7e25-08de0be1d153"
    data_id = "1eb96811-39fe-47a4-7e25-08de0be1d154"

    editor = _chart_notebook_editor(block_id, data_id)
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)
    tools, file_service_mock = _chart_notebook_tools(sample_project, notebook_json)

    result_json = await tools.edit_chart_block(
        notebook_id=notebook_id,
        block_id=block_id,
        config={
            "chartType": "bar",
            "title": "New",
            "height": 400,
            "xField": "region",
            "yField": "revenue",
            "colorField": "channel",
            "stack": True,
        },
    )

    payload = json.loads(result_json)
    assert payload["success"] is True
    assert payload["blockId"] == block_id

    saved_notebook = file_service_mock.update_notebook.call_args.kwargs["notebook"]
    chart_blocks = [b.root for b in saved_notebook.blocks if isinstance(b.root, ChartBlock)]
    assert len(chart_blocks) == 1
    edited = chart_blocks[0]
    assert str(edited.id) == block_id
    assert edited.data.config.root.chart_type == ChartType.BAR
    assert edited.data.config.root.title == "New"
    assert edited.data.data_ref is not None
    assert edited.data.data_ref.data_id == data_id


@pytest.mark.asyncio
async def test_edit_chart_block_requires_explicit_chart_type(sample_project):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    block_id = "1eb96811-39fe-47a4-7e25-08de0be1d153"

    editor = _chart_notebook_editor(block_id, "1eb96811-39fe-47a4-7e25-08de0be1d154")
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)
    tools, file_service_mock = _chart_notebook_tools(sample_project, notebook_json)

    result_json = await tools.edit_chart_block(
        notebook_id=notebook_id,
        block_id=block_id,
        config={"title": "New", "height": 400, "xField": "region", "yField": "revenue"},
    )

    payload = json.loads(result_json)
    assert payload["success"] is False
    assert "chartType" in payload["message"]
    file_service_mock.update_notebook.assert_not_called()


@pytest.mark.asyncio
async def test_edit_chart_block_rejects_non_chart_block(sample_project):
    notebook_id = "1eb96811-39fe-47a4-7e25-08de0be1d149"
    sql_block_id = "1eb96811-39fe-47a4-7e25-08de0be1d155"

    editor = NotebookEditor()
    editor.create_notebook("Notebook")
    editor.add_block(
        NotebookBlock(
            SqlBlock(
                id=sql_block_id,
                type="sql",
                data=SqlBlockData(code="SELECT 1"),
            )
        )
    )
    notebook_json = editor.get_notebook().model_dump_json(exclude_none=True, by_alias=True)
    tools, _file_service_mock = _chart_notebook_tools(sample_project, notebook_json)

    result_json = await tools.edit_chart_block(
        notebook_id=notebook_id,
        block_id=sql_block_id,
        config={
            "chartType": "bar",
            "title": "New",
            "height": 400,
            "xField": "region",
            "yField": "revenue",
        },
    )

    payload = json.loads(result_json)
    assert payload["success"] is False
    assert "not a chart block" in payload["message"]
