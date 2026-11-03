"""Chart tools for managing standalone .chart files in Kontext."""

import asyncio
import os
from collections.abc import Mapping
from typing import Any

from kontext.agent import RuntimeToolContext
from kontext.agent.tools import creates_artifact, reads_artifact, tool_meta, updates_artifact
from kontext.common.jobs.trigger_actor import agent_actor
from kontext.common.protocols import AIToolkitServiceProviderProtocol
from kontext.file.charts import ChartEditor, ChartFieldValidator, ChartService
from kontext.schema import (
    ArtifactOrigin,
    ArtifactProvenance,
    ArtifactType,
    BoxChartType,
    ChartBatchResult,
    ChartConfig,
    ChartDocument,
    ChartResult,
    CodeLanguage,
    DataRef,
    DataTableSummary,
    DualAxesChartType,
    InlineData,
    MarkTypes,
    ProjectModel,
    RadarCoordinateType,
)

from ..utils.guid_validation import validate_guid, validate_guids
from .kontext_toolkit import KontextToolkit, ToolkitScope

_FLAT_CHART_TYPE_KEYS = (
    "line, bar, column, area, pie, scatter, dualAxes, funnel, heatmap, histogram, box, radar, stock"
)


def parse_flat_chart_config(config: Mapping[str, Any]) -> ChartConfig:
    """Validate a flat camelCase chart config payload into a ``ChartConfig``.

    Requires an explicit ``chartType``: every ``ChartConfig`` variant declares
    ``chartType`` with a default, so pydantic resolves the union by trying the
    variants in order - a payload without an explicit ``chartType`` can
    silently validate another variant's shape (e.g. a bar payload with only
    ``xField``/``yField`` validating as a line config).
    """
    chart_type = config.get("chartType")
    if not isinstance(chart_type, str) or not chart_type.strip():
        raise ValueError(
            f"config must include an explicit, non-empty 'chartType' ({_FLAT_CHART_TYPE_KEYS})"
        )
    return ChartConfig.model_validate(config)


class ChartTools(KontextToolkit):
    """Toolkit for standalone chart management operations."""

    def __init__(
        self,
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: str | None = None,
        scope: ToolkitScope | None = None,
    ) -> None:
        """Initialize chart toolkit.

        Args:
            project: Project model with full context
            session_id: Optional query session ID
            chat_session_id: Optional chat session ID
            engine_type: Optional default engine type
        """
        tools = [
            self.get_chart,
            self.get_charts,
            self.update_chart,
            self.create_line_chart,
            self.create_bar_chart,
            self.create_pie_chart,
            self.create_scatter_chart,
            self.create_area_chart,
            self.create_column_chart,
            self.create_dual_axes_chart,
            self.create_funnel_chart,
            self.create_heatmap_chart,
            self.create_histogram_chart,
            self.create_box_chart,
            self.create_radar_chart,
            self.create_stock_chart,
        ]

        super().__init__(
            name="ChartTools",
            project=project,
            runtime_provider=runtime_provider,
            session_id=session_id,
            chat_session_id=chat_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
            scope=scope,
            tools=tools,
        )
        self.file_service = self.get_file_service()
        # Note: ChartTools intentionally does not execute SQL.
        # Data must be provided via DataRef or embedded data.
        self.query_session_service = self.get_query_session_service()

        # Validate project_id
        validate_guid(self.project_id, "project_id")

        self.editor = ChartEditor(
            file_service=self.file_service, logger=self.logger, project_id=self.project_id
        )

        # Agno runs tool calls from a single assistant turn concurrently; the
        # shared ChartEditor persists via load -> mutate -> save cycles, so
        # serialize editor access to prevent lost updates.
        self._editor_lock = asyncio.Lock()

    async def _get_chart_document_url(self, chart_id: str) -> str:
        """Get the public URL for a chart document."""
        base_url = os.environ.get("PUBLIC_KONTEXT_APP_URL", "http://localhost:8002")
        project_code = self.project.project_code
        project_ref = project_code or self.project_id
        return f"{base_url.rstrip('/')}/project/{project_ref}/chart/{chart_id}"

    async def _resolve_chart_data_table(
        self, data_table_id: str, run_context: RuntimeToolContext | None = None
    ) -> tuple[InlineData | None, DataRef, str | None]:
        """Resolve a data table ID to a durable reference plus optional validation data.

        Args:
            data_table_id: The data table ID to resolve
            run_context: runtime context for session state access

        Returns:
            tuple of (validation_data, data_ref, identity_key)
            - validation_data may be populated from local transient state
            - data_ref always points to a durable file-backed artifact
            - identity_key is the source data table's result identity,
              when known (shared-state descriptor or the ``.dt`` metadata)

        Raises:
            ValueError: If the data table cannot be resolved
        """
        descriptor = self.get_artifact_descriptor(data_table_id, run_context)
        if descriptor:
            self.logger.info("Found data table %s in shared session state", data_table_id)

        inline_data = self.get_transient_data(data_table_id)
        self.logger.info(f"Resolving durable data table reference: {data_table_id}")
        resolved_id = await self.resolve_data_table_id(data_table_id, run_context)
        identity_key = descriptor.identity_key if descriptor else None
        if inline_data is None and self.file_service:
            try:
                inline_data = await self.file_service.get_data_table_file(
                    self.project_id, resolved_id
                )
            except Exception as e:
                self.logger.warning(f"Could not fetch data table content for validation: {e}")

        if identity_key is None and inline_data is not None:
            source_metadata = inline_data.metadata
            if source_metadata is not None:
                identity_key = source_metadata.identity_key

        # Try to fetch SQL for the reference to preserve query lineage
        sql = descriptor.sql if descriptor else None
        if not sql and self.file_service:
            try:
                content = await self.file_service.get_file_content(self.project_id, resolved_id)
                from kontext.schema import InlineData

                InlineData.model_validate_json(content)  # validate only
            except Exception as e:
                self.logger.warning(f"Could not fetch SQL for data table reference: {e}")

        return (
            inline_data,
            DataRef(data_id=resolved_id, code=sql, language=CodeLanguage.SQL),
            identity_key,
        )

    @reads_artifact(ChartResult, artifact_type=ArtifactType.CHART)
    @validate_guids("chart_id")
    async def get_chart(self, chart_id: str) -> str:
        """Retrieve a chart by ID.

        :param chart_id: Chart ID.
        """
        try:
            self.logger.info(f"Retrieving chart: {chart_id}")

            if not self.file_service:
                raise ValueError("File service is not available")

            content = await self.file_service.get_file_content(self.project_id, chart_id)
            chart = ChartDocument.model_validate_json(content)

            data_summary = None
            if chart.inline_data:
                # Handle nested InlineData structure
                columns = []
                row_count = 0
                if chart.inline_data and chart.inline_data.table:
                    table = chart.inline_data.table
                    columns = table.columns or []
                    # Check row_count first, fallback to len(rows)
                    if table.row_count is not None:
                        row_count = table.row_count
                    elif table.rows:
                        row_count = len(table.rows)

                data_summary = DataTableSummary(
                    columns=columns,
                    row_count=row_count,
                    data_id=chart.data_ref.data_id if chart.data_ref else None,
                )

            result = ChartResult(
                success=True,
                chart_id=chart_id,
                chart=chart,
                chart_document_url=await self._get_chart_document_url(chart_id),
                data_summary=data_summary,
                message=f"Successfully retrieved chart '{chart.name}'",
            )

            return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to retrieve chart {chart_id}: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            return self._wrap_result(
                ChartResult(success=False, chart_id=chart_id, message=error_msg)
            )

    @tool_meta(ChartBatchResult, display_name="Get Charts (Batch)", emit_tool_call=True)
    async def get_charts(self, chart_ids: list[str]) -> str:
        """Retrieve several charts in one call.

        Prefer this over repeated ``get_chart`` calls when you already know the
        chart IDs to inspect.

        :param chart_ids: Chart IDs.
        """
        charts = await self._collect_batch_items(
            chart_ids,
            fetch=self.get_chart,
            parse_into=ChartResult,
            failure=lambda chart_id, exc: ChartResult(
                success=False, chart_id=chart_id, message=str(exc)
            ),
        )
        failed_count = self._failed_count(charts)
        return self._wrap_result(
            ChartBatchResult(
                success=bool(charts) and failed_count == 0,
                message=f"Retrieved {len(charts)} chart(s); {failed_count} failed.",
                charts=charts,
                charts_count=len(charts),
                failed_count=failed_count,
            )
        )

    @creates_artifact(ChartResult, artifact_type=ArtifactType.CHART, emit_tool_call=True)
    async def create_chart(
        self,
        name: str,
        config: ChartConfig,
        data_table_id: str,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a chart from data.

        :param name: Name.
        :param config: Configuration.
        :param data_table_id: Data table ID.
        :param description: Optional description.
        :param run_context: runtime context for session state access.
        """
        try:
            self.logger.info(f"Creating chart '{name}' in project: {self.project_id}")

            if not self.file_service:
                raise ValueError("File service is not available")

            # Resolve data table
            try:
                (
                    validation_data,
                    data_ref,
                    source_identity_key,
                ) = await self._resolve_chart_data_table(data_table_id, run_context)
            except Exception as e:
                error_msg = f"Data table '{data_table_id}' could not be resolved: {e!s}"
                self.logger.error(error_msg)
                return self._wrap_result(ChartResult(success=False, message=error_msg))

            # Validate chart config fields against data-table columns
            try:
                ChartFieldValidator.validate_config_against_data_table(
                    config=config, inline_data=validation_data, context_name=name
                )
            except ValueError as e:
                return self._wrap_result(ChartResult(success=False, message=str(e)))

            # Persisted charts must reference durable data artifacts rather than embedding transient payloads.
            chart_provenance = ArtifactProvenance(
                origin=ArtifactOrigin.CHARTCOMPOSE,
                created_by=agent_actor("chart_tool"),
                chat_session_id=str(self.chat_session_id) if self.chat_session_id else None,
                identity_key=source_identity_key,
            )
            async with self._editor_lock:
                self.editor.create_chart(
                    name=name,
                    config=config,
                    data_ref=data_ref,
                    inline_data=None,
                    description=description,
                    query_session_id=self.session_id,
                    chat_session_id=self.chat_session_id,
                    provenance=chart_provenance,
                )

                # Save the chart using editor (handles creation)
                await self.editor.save_chart()

                # Get the file ID from the editor (backend assigns it after save)
                file_id = self.editor._file_id
                if not file_id:
                    raise ValueError("Chart was not saved properly - no file ID returned")

                updated_chart = self.editor.chart
            if not updated_chart:
                raise ValueError("Chart was not saved properly")

            # Register artifact if we have a chat session
            await self.link_artifact_to_session(
                artifact_id=file_id,
                artifact_type=ArtifactType.CHART,
                title=name,
                meta={
                    "chart_type": config.root.chart_type,
                    "chart_document_url": await self._get_chart_document_url(file_id),
                },
                run_context=run_context,
                provenance=chart_provenance,
            )

            result = ChartResult(
                success=True,
                chart_id=file_id,
                chart=updated_chart,
                chart_document_url=await self._get_chart_document_url(file_id),
                data_summary=updated_chart.data_summary,
                message=f"Successfully created chart '{name}'",
            )

            return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to create chart: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            return self._wrap_result(ChartResult(success=False, message=error_msg))

    @updates_artifact(ChartResult, artifact_type=ArtifactType.CHART, emit_tool_call=True)
    @validate_guids("chart_id")
    async def update_chart(
        self,
        chart_id: str,
        name: str | None = None,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Update an existing chart.

        ``config`` is a flat camelCase chart configuration object: set an
        explicit ``chartType`` (line, bar, column, area, pie, scatter, dualAxes,
        funnel, heatmap, histogram, box, radar, stock), ``title`` and
        ``height``, then the kind's field keys (``xField``/``yField``,
        ``angleField``, ``binField``, ``leftYField``/``rightYField`` for dual
        axes, etc.). Omit ``config`` to change only ``name`` or ``description``.

        :param chart_id: Chart ID.
        :param name: New name.
        :param config: New configuration as a flat chart config object.
        :param description: New description.
        :param run_context: runtime context.
        """
        try:
            self.logger.info(f"Updating chart: {chart_id}")

            if not self.file_service:
                raise ValueError("File service is not available")

            # Load current chart using editor
            async with self._editor_lock:
                chart = await self.editor.load_chart_from_file(self.project_id, chart_id)

                # Apply updates (the data table cannot be changed)
                if name is not None:
                    chart.name = name

                if config is not None:
                    # Validate the flat payload on the server so the tool schema
                    # stays small (a typed ChartConfig union is ~38k chars). A
                    # full chart document payload ({"config": {...}}) is accepted
                    # too, using only its config object; programmatic callers may
                    # still pass an already-validated ChartConfig.
                    raw_config: Any = config
                    if isinstance(raw_config, dict):
                        raw_config = (
                            raw_config["config"]
                            if isinstance(raw_config.get("config"), dict)
                            else raw_config
                        )
                        raw_config = parse_flat_chart_config(raw_config)
                    self.editor.update_config(raw_config)

                if description is not None:
                    self.editor.update_metadata(description=description)

                # Save updated chart
                await self.editor.save_chart()

                # Take actions for streaming
                actions = self.editor.take_actions()

            # Update artifact if we have a chat session
            meta = None
            if chart.config:
                meta = {
                    "chart_type": chart.config.root.chart_type,
                    "chart_document_url": await self._get_chart_document_url(chart_id),
                }

            await self.link_artifact_to_session(
                artifact_id=chart_id,
                artifact_type=ArtifactType.CHART,
                title=chart.name,
                meta=meta,
                run_context=run_context,
            )

            data_summary = None
            if chart.inline_data:
                # Handle nested InlineData structure
                columns = []
                row_count = 0
                if chart.inline_data and chart.inline_data.table:
                    table = chart.inline_data.table
                    columns = table.columns or []
                    # Check row_count first, fallback to len(rows)
                    if table.row_count is not None:
                        row_count = table.row_count
                    elif table.rows:
                        row_count = len(table.rows)

                data_summary = DataTableSummary(
                    columns=columns,
                    row_count=row_count,
                    data_id=chart.data_ref.data_id if chart.data_ref else None,
                )

            result = ChartResult(
                success=True,
                chart_id=chart_id,
                chart=chart,
                chart_document_url=await self._get_chart_document_url(chart_id),
                data_summary=data_summary,
                message=f"Successfully updated chart '{chart.name}'",
                actions=actions,
            )

            return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to update chart {chart_id}: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            return self._wrap_result(
                ChartResult(success=False, chart_id=chart_id, message=error_msg)
            )

    # Specialized Chart Tools
    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Line Chart",
        emit_tool_call=True,
    )
    async def create_line_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        color_field: str | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a line chart."""
        config = ChartService.create_line_chart_config(
            title=title or name, x_field=x_field, y_field=y_field, color_field=color_field
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Bar Chart",
        emit_tool_call=True,
    )
    async def create_bar_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        color_field: str | None = None,
        stack: bool | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a bar chart from a data table.

        :param name: Chart name.
        :param x_field: Category field for the x-axis.
        :param y_field: Numeric field for the y-axis.
        :param data_table_id: Data table ID supplying the chart data.
        :param color_field: Field that splits the bars into series by color.
        :param stack: True stacks the series bars; False places them side by side.
            Only applies when `color_field` is set.
        :param title: Optional chart title.
        :param description: Optional description.
        :param run_context: runtime context for session state access.
        """
        if stack is None and color_field:
            stack = True

        config = ChartService.create_bar_chart_config(
            title=title or name,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            stack=stack,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Pie Chart",
        emit_tool_call=True,
    )
    async def create_pie_chart(
        self,
        name: str,
        angle_field: str,
        color_field: str,
        data_table_id: str,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a pie chart."""
        if angle_field == color_field:
            return self._wrap_result(
                ChartResult(
                    success=False,
                    message="Value field (angle) and Category field (color) must be different",
                )
            )

        config = ChartService.create_pie_chart_config(
            title=title or name, angle_field=angle_field, color_field=color_field
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Scatter Chart",
        emit_tool_call=True,
    )
    async def create_scatter_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        color_field: str | None = None,
        size_field: str | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a scatter chart."""
        config = ChartService.create_scatter_chart_config(
            title=title or name,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            size_field=size_field,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Area Chart",
        emit_tool_call=True,
    )
    async def create_area_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        color_field: str | None = None,
        stack: bool | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create an area chart from a data table.

        :param name: Chart name.
        :param x_field: Category field for the x-axis.
        :param y_field: Numeric field for the y-axis.
        :param data_table_id: Data table ID supplying the chart data.
        :param color_field: Field that splits the areas into series by color.
        :param stack: True stacks the series areas; False overlays them.
            Only applies when `color_field` is set.
        :param title: Optional chart title.
        :param description: Optional description.
        :param run_context: runtime context for session state access.
        """
        if stack is None and color_field:
            stack = True

        config = ChartService.create_area_chart_config(
            title=title or name,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            stack=stack,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Column Chart",
        emit_tool_call=True,
    )
    async def create_column_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        color_field: str | None = None,
        stack: bool | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a column chart from a data table.

        :param name: Chart name.
        :param x_field: Category field for the x-axis.
        :param y_field: Numeric field for the y-axis.
        :param data_table_id: Data table ID supplying the chart data.
        :param color_field: Field that splits the columns into series by color.
        :param stack: True stacks the series columns; False places them side by side.
            Only applies when `color_field` is set.
        :param title: Optional chart title.
        :param description: Optional description.
        :param run_context: runtime context for session state access.
        """
        if stack is None and color_field:
            stack = True

        config = ChartService.create_column_chart_config(
            title=title or name,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            stack=stack,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Dual Axes Chart",
        emit_tool_call=True,
    )
    async def create_dual_axes_chart(
        self,
        name: str,
        x_field: str,
        left_y_field: str,
        left_chart_type: DualAxesChartType,
        right_y_field: str,
        right_chart_type: DualAxesChartType,
        data_table_id: str,
        left_color_field: str | None = None,
        right_color_field: str | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a dual axes chart."""
        config = ChartService.create_dual_axes_chart_config(
            title=title or name,
            x_field=x_field,
            left_y_field=left_y_field,
            left_chart_type=left_chart_type,
            right_y_field=right_y_field,
            right_chart_type=right_chart_type,
            left_color_field=left_color_field,
            right_color_field=right_color_field,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Funnel Chart",
        emit_tool_call=True,
    )
    async def create_funnel_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        compare_field: str | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a funnel chart."""
        config = ChartService.create_funnel_chart_config(
            title=title or name, x_field=x_field, y_field=y_field, compare_field=compare_field
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Heatmap Chart",
        emit_tool_call=True,
    )
    async def create_heatmap_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        color_field: str | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a heatmap chart."""
        config = ChartService.create_heatmap_chart_config(
            title=title or name,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            mark=MarkTypes.CELL,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Histogram Chart",
        emit_tool_call=True,
    )
    async def create_histogram_chart(
        self,
        name: str,
        bin_field: str,
        data_table_id: str,
        color_field: str | None = None,
        bin_width: float | None = None,
        bin_number: int | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a histogram chart."""
        config = ChartService.create_histogram_chart_config(
            title=title or name,
            bin_field=bin_field,
            color_field=color_field,
            bin_width=bin_width,
            bin_number=bin_number,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Box Chart",
        emit_tool_call=True,
    )
    async def create_box_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        color_field: str | None = None,
        box_type: BoxChartType | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a box chart."""
        config = ChartService.create_box_chart_config(
            title=title or name,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            box_type=box_type,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Radar Chart",
        emit_tool_call=True,
    )
    async def create_radar_chart(
        self,
        name: str,
        x_field: str,
        y_field: str,
        data_table_id: str,
        color_field: str | None = None,
        coordinate_type: RadarCoordinateType | None = None,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a radar chart."""
        config = ChartService.create_radar_chart_config(
            title=title or name,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            coordinate_type=coordinate_type,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )

    @creates_artifact(
        ChartResult,
        artifact_type=ArtifactType.CHART,
        display_name="Create Stock Chart",
        emit_tool_call=True,
    )
    async def create_stock_chart(
        self,
        name: str,
        x_field: str,
        open_field: str,
        close_field: str,
        low_field: str,
        high_field: str,
        data_table_id: str,
        title: str | None = None,
        description: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a stock chart."""
        config = ChartService.create_stock_chart_config(
            title=title or name,
            x_field=x_field,
            open_field=open_field,
            close_field=close_field,
            low_field=low_field,
            high_field=high_field,
        )
        return await self.create_chart(
            name=name,
            config=config,
            data_table_id=data_table_id,
            description=description,
            run_context=run_context,
        )
