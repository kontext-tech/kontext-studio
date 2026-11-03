from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agent import (
    AgentContext,
    ToolExecutionContext,
    agent_context_scope,
    render_tool_schema,
)
from kontext.agentic.tools.chart_tool import ChartTools
from kontext.file.charts import ChartEditor, ChartService
from kontext.schema import (
    ArtifactOrigin,
    ArtifactType,
    BoxChartConfig,
    BoxChartType,
    ChartDocument,
    ChartDocumentMetadata,
    ChartType,
    CodeLanguage,
    DataColumn,
    DataRef,
    DataTable,
    DualAxesChartType,
    HistogramChartConfig,
    InlineData,
    InlineDataMetadata,
    RadarChartConfig,
    RadarCoordinateType,
    StockChartConfig,
)


class TestRuntimeContext:
    def __init__(self, session_state: dict[str, Any] | None = None):
        self.session_state = session_state

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.any_schema()


class FakeChartEditor(ChartEditor):
    def __init__(self) -> None:
        super().__init__()

    def create_chart(
        self,
        name,
        config,
        data_ref=None,
        inline_data=None,
        description=None,
        chart_id=None,
        data_summary=None,
        notebook_id=None,
        query_session_id=None,
        chat_session_id=None,
        provenance=None,
    ):
        from datetime import UTC, datetime

        from kontext.schema import ChartDocumentMetadata

        now = datetime.now(UTC)
        self.chart = ChartDocument(
            name=name,
            config=config,
            data_ref=data_ref,
            inline_data=inline_data,
            metadata=ChartDocumentMetadata(
                description=description,
                created_at=now,
                modified_at=now,
                version="1.0.0",
                notebook_id=notebook_id,
                query_session_id=query_session_id,
                chat_session_id=chat_session_id,
            ),
        )
        self.last_provenance = provenance
        return self.chart

    async def save_chart(self):
        self._file_id = "3eb96811-39fe-47a4-7e25-08de0be1d151"


@pytest.mark.asyncio
async def test_create_chart_promotes_transient_data_to_durable_reference(sample_project):
    file_service = MagicMock()
    file_service.exists_by_id = AsyncMock(return_value=False)
    file_service.get_data_table_file = AsyncMock()
    file_service.get_file_content = AsyncMock(return_value="{}")
    response = MagicMock()
    response.file.id = "2eb96811-39fe-47a4-7e25-08de0be1d151"
    file_service.materialize_inline_data = AsyncMock(
        return_value="2eb96811-39fe-47a4-7e25-08de0be1d151"
    )

    provider = MagicMock()
    provider.get_file_service.return_value = file_service
    provider.get_query_session_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None

    chart_tool = ChartTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id="550e8400-e29b-41d4-a716-446655440000",
    )
    chart_tool.editor = FakeChartEditor()

    inline_data = InlineData(
        title="Customers by Country",
        table=DataTable(
            columns=[
                DataColumn(name="country", type="string"),
                DataColumn(name="count", type="integer"),
            ],
            rows=[["AUS", 10], ["USA", 8]],
            row_count=2,
        ),
    )

    run_context = TestRuntimeContext(session_state={})
    with agent_context_scope(
        AgentContext(
            project_id=sample_project.id, session_id="550e8400-e29b-41d4-a716-446655440000"
        ),
        ToolExecutionContext(
            project_id=sample_project.id, session_id="550e8400-e29b-41d4-a716-446655440000"
        ),
    ):
        transient_id = chart_tool.register_transient_artifact(
            payload=inline_data,
            artifact_type=ArtifactType.DATATABLE,
            title=inline_data.title,
        )
        result_json = await chart_tool.create_bar_chart(
            name="Customers by Country",
            x_field="country",
            y_field="count",
            data_table_id=transient_id,
            run_context=run_context,
        )

    result = json.loads(result_json)
    assert result["success"] is True
    assert result["chartId"] == "3eb96811-39fe-47a4-7e25-08de0be1d151"

    created_chart = chart_tool.editor.chart
    assert created_chart is not None
    assert created_chart.inline_data is None
    assert created_chart.data_ref == DataRef(
        data_id="2eb96811-39fe-47a4-7e25-08de0be1d151",
        language=CodeLanguage.SQL,
    )
    assert created_chart.metadata is not None
    assert created_chart.metadata.chat_session_id == "550e8400-e29b-41d4-a716-446655440000"

    session_state = run_context.session_state
    assert session_state is not None
    descriptor = session_state["kontext"]["artifacts_by_id"]["2eb96811-39fe-47a4-7e25-08de0be1d151"]
    assert descriptor["artifact_type"] == "DataTable"
    alias_targets = set(session_state["kontext"]["artifact_aliases"].values())
    assert alias_targets == {"2eb96811-39fe-47a4-7e25-08de0be1d151"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "kwargs", "expected_chart_type"),
    [
        (
            "create_histogram_chart",
            {
                "bin_field": "metric",
                "color_field": "segment",
                "bin_number": 5,
            },
            ChartType.HISTOGRAM,
        ),
        (
            "create_box_chart",
            {
                "x_field": "category",
                "y_field": "metric",
                "color_field": "segment",
                "box_type": BoxChartType.BOXPLOT,
            },
            ChartType.BOX,
        ),
        (
            "create_radar_chart",
            {
                "x_field": "category",
                "y_field": "metric",
                "color_field": "segment",
                "coordinate_type": RadarCoordinateType.POLAR,
            },
            ChartType.RADAR,
        ),
        (
            "create_stock_chart",
            {
                "x_field": "trade_date",
                "open_field": "open_price",
                "close_field": "close_price",
                "low_field": "low_price",
                "high_field": "high_price",
            },
            ChartType.STOCK,
        ),
    ],
)
async def test_create_new_chart_types(sample_project, method_name, kwargs, expected_chart_type):
    file_service = MagicMock()
    file_service.exists_by_id = AsyncMock(return_value=False)
    file_service.get_data_table_file = AsyncMock()
    file_service.get_file_content = AsyncMock(return_value="{}")
    response = MagicMock()
    response.file.id = "2eb96811-39fe-47a4-7e25-08de0be1d151"
    file_service.materialize_inline_data = AsyncMock(
        return_value="2eb96811-39fe-47a4-7e25-08de0be1d151"
    )

    provider = MagicMock()
    provider.get_file_service.return_value = file_service
    provider.get_query_session_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None

    chart_tool = ChartTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id="550e8400-e29b-41d4-a716-446655440000",
    )
    chart_tool.editor = FakeChartEditor()

    inline_data = InlineData(
        title="Chart Inputs",
        table=DataTable(
            columns=[
                DataColumn(name="category", type="string"),
                DataColumn(name="metric", type="integer"),
                DataColumn(name="segment", type="string"),
                DataColumn(name="trade_date", type="string"),
                DataColumn(name="open_price", type="number"),
                DataColumn(name="close_price", type="number"),
                DataColumn(name="low_price", type="number"),
                DataColumn(name="high_price", type="number"),
            ],
            rows=[
                ["North", 10, "A", "2024-01-02", 101.2, 104.8, 99.4, 106.1],
                ["South", 14, "B", "2024-01-03", 104.8, 103.5, 102.3, 107.0],
            ],
            row_count=2,
        ),
    )

    run_context = TestRuntimeContext(session_state={})
    with agent_context_scope(
        AgentContext(
            project_id=sample_project.id,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        ),
        ToolExecutionContext(
            project_id=sample_project.id,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        ),
    ):
        transient_id = chart_tool.register_transient_artifact(
            payload=inline_data,
            artifact_type=ArtifactType.DATATABLE,
            title=inline_data.title,
        )
        result_json = await getattr(chart_tool, method_name)(
            name=f"Test {expected_chart_type.value.title()} Chart",
            data_table_id=transient_id,
            run_context=run_context,
            **kwargs,
        )

    result = json.loads(result_json)
    assert result["success"] is True

    created_chart = chart_tool.editor.chart
    assert created_chart is not None
    assert created_chart.config is not None
    config_root = created_chart.config.root
    assert config_root.chart_type == expected_chart_type

    if expected_chart_type == ChartType.HISTOGRAM:
        assert isinstance(config_root, HistogramChartConfig)
        assert config_root.bin_field == "metric"
        assert config_root.bin_number == 5
    elif expected_chart_type == ChartType.BOX:
        assert isinstance(config_root, BoxChartConfig)
        assert config_root.x_field == "category"
        assert config_root.y_field == "metric"
        assert config_root.box_type is not None
        assert config_root.box_type.value == "boxplot"
    elif expected_chart_type == ChartType.RADAR:
        assert isinstance(config_root, RadarChartConfig)
        assert config_root.x_field == "category"
        assert config_root.y_field == "metric"
        assert config_root.coordinate_type is not None
        assert config_root.coordinate_type.value == "polar"
    elif expected_chart_type == ChartType.STOCK:
        assert isinstance(config_root, StockChartConfig)
        assert config_root.x_field == "trade_date"
        assert config_root.y_field == [
            "open_price",
            "close_price",
            "low_price",
            "high_price",
        ]


def _bar_chart_tool(sample_project) -> ChartTools:
    file_service = MagicMock()
    file_service.exists_by_id = AsyncMock(return_value=False)
    file_service.get_data_table_file = AsyncMock()
    file_service.get_file_content = AsyncMock(return_value="{}")
    file_service.materialize_inline_data = AsyncMock(
        return_value="2eb96811-39fe-47a4-7e25-08de0be1d151"
    )

    provider = MagicMock()
    provider.get_file_service.return_value = file_service
    provider.get_query_session_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None

    chart_tool = ChartTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id="550e8400-e29b-41d4-a716-446655440000",
    )
    chart_tool.editor = FakeChartEditor()
    return chart_tool


def _series_inline_data() -> InlineData:
    return InlineData(
        title="Revenue by Region",
        table=DataTable(
            columns=[
                DataColumn(name="region", type="string"),
                DataColumn(name="revenue", type="integer"),
                DataColumn(name="channel", type="string"),
            ],
            rows=[["North", 10, "Online"], ["South", 14, "Retail"]],
            row_count=2,
        ),
    )


class _UpdateChartEditor(ChartEditor):
    """Minimal chart editor double for update_chart tests."""

    def __init__(self) -> None:
        super().__init__()
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        self.chart = ChartDocument(
            name="Old",
            config=ChartService.create_line_chart_config(
                title="Old", x_field="region", y_field="revenue"
            ),
            metadata=ChartDocumentMetadata(created_at=now, modified_at=now, version="1.0.0"),
        )

    async def load_chart_from_file(self, project_id: str, chart_id: str):
        return self.chart

    def update_config(self, config) -> None:
        self.chart.config = config

    async def save_chart(self) -> None:
        pass

    def take_actions(self) -> list:
        return []


def _update_chart_tool(sample_project) -> tuple[ChartTools, _UpdateChartEditor]:
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock()
    provider.get_query_session_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None

    chart_tool = ChartTools(project=sample_project, runtime_provider=provider)
    editor = _UpdateChartEditor()
    chart_tool.editor = editor
    return chart_tool, editor


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requested_stack", "expected_stack"),
    [(None, True), (False, False), (True, True)],
)
async def test_create_bar_chart_stack_default_and_override(
    sample_project, requested_stack, expected_stack
):
    """Multi-series bars default to stacked; stack=False groups explicitly."""
    chart_tool = _bar_chart_tool(sample_project)
    inline_data = _series_inline_data()
    run_context = TestRuntimeContext(session_state={})

    with agent_context_scope(
        AgentContext(
            project_id=sample_project.id,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        ),
        ToolExecutionContext(
            project_id=sample_project.id,
            session_id="550e8400-e29b-41d4-a716-446655440000",
        ),
    ):
        transient_id = chart_tool.register_transient_artifact(
            payload=inline_data,
            artifact_type=ArtifactType.DATATABLE,
            title=inline_data.title,
        )
        result_json = await chart_tool.create_bar_chart(
            name="Revenue by Region",
            x_field="region",
            y_field="revenue",
            color_field="channel",
            data_table_id=transient_id,
            stack=requested_stack,
            run_context=run_context,
        )

    assert json.loads(result_json)["success"] is True
    created_chart = chart_tool.editor.chart
    assert created_chart is not None
    config_root = created_chart.config.root
    assert config_root.chart_type == ChartType.BAR
    assert config_root.stack is not None
    assert config_root.stack.root is expected_stack


def test_chart_tool_documents_stacking_in_tool_schema(sample_project):
    """`stack` param descriptions state factual semantics; layout policy stays out."""
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock()
    provider.get_query_session_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None

    chart_tool = ChartTools(project=sample_project, runtime_provider=provider)

    for method_name, non_stacked_word in (
        ("create_bar_chart", "side by side"),
        ("create_column_chart", "side by side"),
        ("create_area_chart", "overlays"),
    ):
        schema = render_tool_schema(getattr(chart_tool, method_name), strict=False)
        stack_description = (
            schema["parameters"]["properties"]["stack"]["description"].lower().replace("\n", " ")
        )
        assert "stack" in stack_description
        assert "series" in stack_description
        assert "color_field" in stack_description
        assert non_stacked_word in stack_description
        # Regression guard for the ambiguous escape hatch that led agents to
        # un-stack multi-series charts without user intent.
        assert "independent metrics" not in stack_description
        assert "independent metrics" not in (schema["description"] or "").lower()


def test_chart_tool_exposes_enum_choices_in_tool_schema(sample_project):
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock()
    provider.get_query_session_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None

    chart_tool = ChartTools(project=sample_project, runtime_provider=provider)

    box_schema = render_tool_schema(chart_tool.create_box_chart, strict=False)["parameters"]
    assert box_schema["properties"]["box_type"]["anyOf"][0]["enum"] == [
        BoxChartType.BOX.value,
        BoxChartType.BOXPLOT.value,
    ]

    radar_schema = render_tool_schema(chart_tool.create_radar_chart, strict=False)["parameters"]
    assert radar_schema["properties"]["coordinate_type"]["anyOf"][0]["enum"] == [
        RadarCoordinateType.RADAR.value,
        RadarCoordinateType.POLAR.value,
    ]

    dual_axes_schema = render_tool_schema(chart_tool.create_dual_axes_chart, strict=False)[
        "parameters"
    ]
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
async def test_get_charts_batch_aggregates_results(sample_project):
    toolkit = ChartTools(project=sample_project)
    toolkit.get_chart = AsyncMock(
        side_effect=[
            json.dumps({"success": True, "chartId": "chart-a", "message": "ok"}),
            json.dumps({"success": False, "chartId": "chart-b", "message": "missing"}),
        ]
    )

    payload = json.loads(await toolkit.get_charts(["chart-a", "chart-b"]))

    assert payload["type"] == "chart_batch"
    assert payload["chartsCount"] == 2
    assert payload["failedCount"] == 1
    assert payload["success"] is False
    assert [chart["chartId"] for chart in payload["charts"]] == ["chart-a", "chart-b"]
    assert toolkit.get_chart.await_count == 2


async def test_create_chart_propagates_source_identity_key(sample_project):
    """Charts stamp the source data table's identity into their provenance.

    The identity flows from whichever resolution path knows it - here the
    transient payload's ``.dt`` metadata - so a chart carries the identity of
    the data it renders without re-resolving the source file later.
    """
    file_service = MagicMock()
    file_service.exists_by_id = AsyncMock(return_value=False)
    file_service.get_file_content = AsyncMock(return_value="{}")
    file_service.materialize_inline_data = AsyncMock(
        return_value="2eb96811-39fe-47a4-7e25-08de0be1d151"
    )
    provider = MagicMock()
    provider.get_file_service.return_value = file_service
    provider.get_query_session_service.return_value = MagicMock()
    provider.get_chat_session_service.return_value = None

    chart_tool = ChartTools(
        project=sample_project,
        runtime_provider=provider,
        chat_session_id="550e8400-e29b-41d4-a716-446655440000",
    )
    chart_tool.editor = FakeChartEditor()

    inline_data = InlineData(
        title="Customers by Country",
        table=DataTable(
            columns=[
                DataColumn(name="country", type="string"),
                DataColumn(name="count", type="integer"),
            ],
            rows=[["AUS", 10], ["USA", 8]],
            row_count=2,
        ),
        metadata=InlineDataMetadata(identity_key="a" * 64),
    )

    run_context = TestRuntimeContext(session_state={})
    with agent_context_scope(
        AgentContext(
            project_id=sample_project.id, session_id="550e8400-e29b-41d4-a716-446655440000"
        ),
        ToolExecutionContext(
            project_id=sample_project.id, session_id="550e8400-e29b-41d4-a716-446655440000"
        ),
    ):
        transient_id = chart_tool.register_transient_artifact(
            payload=inline_data,
            artifact_type=ArtifactType.DATATABLE,
            title=inline_data.title,
        )
        result_json = await chart_tool.create_bar_chart(
            name="Customers by Country",
            x_field="country",
            y_field="count",
            data_table_id=transient_id,
            run_context=run_context,
        )

    assert json.loads(result_json)["success"] is True
    provenance = chart_tool.editor.last_provenance
    assert provenance is not None
    assert provenance.origin == ArtifactOrigin.CHARTCOMPOSE
    assert provenance.identity_key == "a" * 64


@pytest.mark.asyncio
async def test_update_chart_requires_explicit_chart_type(sample_project):
    """A flat config without `chartType` must not silently match another variant."""
    chart_tool, editor = _update_chart_tool(sample_project)

    # Shape-valid for a bar config but missing the explicit chartType: the
    # LineChartConfig variant could otherwise consume it (line and bar share
    # xField/yField and chartType carries a default).
    result_json = await chart_tool.update_chart(
        chart_id="3eb96811-39fe-47a4-7e25-08de0be1d151",
        config={"title": "New", "height": 400, "xField": "region", "yField": "revenue"},
    )

    payload = json.loads(result_json)
    assert payload["success"] is False
    assert "chartType" in payload["message"]
    assert editor.chart.config.root.chart_type == ChartType.LINE


@pytest.mark.asyncio
async def test_update_chart_accepts_flat_config_and_validates_on_server(sample_project):
    """The tool schema stays small; the flat config is validated server-side."""
    chart_tool, editor = _update_chart_tool(sample_project)

    result_json = await chart_tool.update_chart(
        chart_id="3eb96811-39fe-47a4-7e25-08de0be1d151",
        config={
            "chartType": "bar",
            "title": "New",
            "height": 400,
            "xField": "region",
            "yField": "revenue",
        },
    )

    payload = json.loads(result_json)
    assert payload["success"] is True
    assert editor.chart.config.root.chart_type == ChartType.BAR
    assert editor.chart.config.root.title == "New"


@pytest.mark.asyncio
async def test_update_chart_rejects_invalid_flat_config(sample_project):
    chart_tool, _editor = _update_chart_tool(sample_project)

    result_json = await chart_tool.update_chart(
        chart_id="3eb96811-39fe-47a4-7e25-08de0be1d151",
        config={"chartType": "bar"},
    )

    payload = json.loads(result_json)
    assert payload["success"] is False
