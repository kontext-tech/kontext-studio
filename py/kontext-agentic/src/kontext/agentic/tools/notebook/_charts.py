"""Chart-block tools for NotebookTools, backed by the shared `_add_chart_block` pipeline."""

from collections.abc import Callable
from contextlib import suppress
from typing import Any
from uuid import uuid4

from kontext.agent import RuntimeToolContext
from kontext.agent.tools import (
    updates_artifact,
)
from kontext.agentic.utils.guid_validation import validate_guids
from kontext.file.charts import ChartService
from kontext.schema import (
    ArtifactType,
    BlockData,
    BoxChartType,
    ChartBlock,
    ChartConfig,
    ChartDocument,
    ChartSpec,
    DataRef,
    DualAxesChartType,
    InlineData,
    MarkTypes,
    NotebookBlock,
    NotebookBlockResult,
    NotebookBlockType,
    NotebookMultiBlockResult,
    RadarCoordinateType,
    SqlBlock,
    SqlBlockData,
)

from ..chart_tool import parse_flat_chart_config
from ._core import (
    ChartFieldInputs,
    NotebookCoreMixin,
    _validate_distinct_pie_fields,
)


class NotebookChartsMixin(NotebookCoreMixin):
    # Chart Block Tools

    async def _add_chart_block(
        self,
        *,
        chart_kind: str,
        notebook_id: str,
        data_table_id: str,
        fields: ChartFieldInputs,
        title: str,
        position: int | None,
        run_context: RuntimeToolContext | None,
        build_config: Callable[[], ChartConfig],
        precheck: Callable[[], None] | None = None,
    ) -> str:
        """Shared chart-block pipeline behind every `add_*_chart` tool.

        The per-type tool methods keep explicit, validated signatures so models
        cannot pass wrong parameters; this helper owns the create-and-add flow
        (data-table provisioning, field validation, block insertion) they all
        share. `precheck` runs inside the operation scope so its failures surface
        as structured tool results.
        """

        async def create_and_add_chart():
            effective_data_table_id, data_table_attached = await self._ensure_notebook_data_table(
                data_table_id,
                run_context=run_context,
                title=f"Data for {title}",
                position=position,
            )
            chart_position = (
                position + 1 if data_table_attached and position is not None else position
            )

            if precheck is not None:
                precheck()

            validation_errors = await self._validate_chart_fields(effective_data_table_id, fields)
            if validation_errors:
                raise ValueError(f"Chart field validation failed: {', '.join(validation_errors)}")

            data_ref, data_source = await self._prepare_chart_data_table(effective_data_table_id)

            chart_config = build_config()
            return self.editor.add_chart_block(
                chart_config=chart_config,
                data_ref=data_ref,
                inline_data=data_source,
                position=chart_position,
            )

        block, actions, error = await self._handle_operation(
            f"Adding {chart_kind} chart",
            self.project_id,
            notebook_id,
            create_and_add_chart,
            run_context=run_context,
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=error,
                message=f"Error adding {chart_kind} chart to notebook {notebook_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=str(block.root.id),
            error=None,
            message=f"Successfully added {chart_kind} chart '{title}' to notebook {notebook_id}",
        )

    @staticmethod
    def _chart_fields(**named_fields: str | None) -> dict[str, str]:
        """Drop None entries before field validation."""
        return {k: v for k, v in named_fields.items() if v is not None}

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_line_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        color_field: str | None = None,
        title: str = "Line Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add line chart to notebook."""
        return await self._add_chart_block(
            chart_kind="line",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_line_chart_config(
                title=title,
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_bar_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        color_field: str | None = None,
        stack: bool | None = None,
        title: str = "Bar Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add a bar chart to a notebook.

        :param notebook_id: Notebook ID.
        :param data_table_id: Data table ID supplying the chart data.
        :param x_field: Category field for the x-axis.
        :param y_field: Numeric field for the y-axis.
        :param color_field: Field that splits the bars into series by color.
        :param stack: True stacks the series bars; False places them side by side.
            Only applies when `color_field` is set.
        :param title: Chart title.
        :param position: Optional block position.
        """
        return await self._add_chart_block(
            chart_kind="bar",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: self.editor.create_bar_chart(
                # Default to stacked bars only when a series field is present.
                title=title,
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
                stack=stack if stack is not None else (True if color_field else None),
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_pie_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        angle_field: str,
        color_field: str,
        title: str = "Pie Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add pie chart to notebook."""
        return await self._add_chart_block(
            chart_kind="pie",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                angle_field=angle_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            precheck=lambda: _validate_distinct_pie_fields(angle_field, color_field),
            build_config=lambda: ChartService.create_pie_chart_config(
                title=title,
                angle_field=angle_field,
                color_field=color_field,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_scatter_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        color_field: str | None = None,
        size_field: str | None = None,
        title: str = "Scatter Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add scatter chart to notebook."""
        return await self._add_chart_block(
            chart_kind="scatter",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
                size_field=size_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_scatter_chart_config(
                title=title,
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
                size_field=size_field,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_area_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        color_field: str | None = None,
        stack: bool | None = None,
        title: str = "Area Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add an area chart to a notebook.

        :param notebook_id: Notebook ID.
        :param data_table_id: Data table ID supplying the chart data.
        :param x_field: Category field for the x-axis.
        :param y_field: Numeric field for the y-axis.
        :param color_field: Field that splits the areas into series by color.
        :param stack: True stacks the series areas; False overlays them.
            Only applies when `color_field` is set.
        :param title: Chart title.
        :param position: Optional block position.
        """
        return await self._add_chart_block(
            chart_kind="area",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: self.editor.create_area_chart(
                # Default to stacked areas only when a series field is present.
                title=title,
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
                stack=stack if stack is not None else (True if color_field else None),
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_column_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        color_field: str | None = None,
        stack: bool | None = None,
        title: str = "Column Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add a column chart to a notebook.

        :param notebook_id: Notebook ID.
        :param data_table_id: Data table ID supplying the chart data.
        :param x_field: Category field for the x-axis.
        :param y_field: Numeric field for the y-axis.
        :param color_field: Field that splits the columns into series by color.
        :param stack: True stacks the series columns; False places them side by side.
            Only applies when `color_field` is set.
        :param title: Chart title.
        :param position: Optional block position.
        """
        return await self._add_chart_block(
            chart_kind="column",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: self.editor.create_column_chart(
                # Default to stacked columns only when a series field is present.
                title=title,
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
                stack=stack if stack is not None else (True if color_field else None),
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_dual_axes_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        left_y_field: str,
        left_chart_type: DualAxesChartType,
        right_y_field: str,
        right_chart_type: DualAxesChartType,
        left_color_field: str | None = None,
        right_color_field: str | None = None,
        title: str = "Dual Axes Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add dual axes chart to notebook."""
        return await self._add_chart_block(
            chart_kind="dual axes",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                left_y_field=left_y_field,
                right_y_field=right_y_field,
                left_color_field=left_color_field,
                right_color_field=right_color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_dual_axes_chart_config(
                title=title,
                x_field=x_field,
                left_y_field=left_y_field,
                left_chart_type=left_chart_type,
                right_y_field=right_y_field,
                right_chart_type=right_chart_type,
                left_color_field=left_color_field,
                right_color_field=right_color_field,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_funnel_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        compare_field: str | None = None,
        title: str = "Funnel Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add funnel chart to notebook."""
        return await self._add_chart_block(
            chart_kind="funnel",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                compare_field=compare_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_funnel_chart_config(
                title=title,
                x_field=x_field,
                y_field=y_field,
                compare_field=compare_field,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_heatmap_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        color_field: str | None = None,
        title: str = "Heatmap Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add heatmap chart to notebook."""
        return await self._add_chart_block(
            chart_kind="heatmap",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_heatmap_chart_config(
                title=title,
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
                mark=MarkTypes.CELL,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_histogram_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        bin_field: str,
        color_field: str | None = None,
        bin_width: float | None = None,
        bin_number: int | None = None,
        title: str = "Histogram Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add histogram chart to notebook."""
        return await self._add_chart_block(
            chart_kind="histogram",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                bin_field=bin_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_histogram_chart_config(
                title=title,
                bin_field=bin_field,
                color_field=color_field,
                bin_width=bin_width,
                bin_number=bin_number,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_box_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        color_field: str | None = None,
        box_type: BoxChartType | None = None,
        title: str = "Box Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add box chart to notebook."""
        return await self._add_chart_block(
            chart_kind="box",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_box_chart_config(
                title=title,
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
                box_type=box_type,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_radar_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        y_field: str,
        color_field: str | None = None,
        coordinate_type: RadarCoordinateType | None = None,
        title: str = "Radar Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add radar chart to notebook."""
        return await self._add_chart_block(
            chart_kind="radar",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields=self._chart_fields(
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
            ),
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_radar_chart_config(
                title=title,
                x_field=x_field,
                y_field=y_field,
                color_field=color_field,
                coordinate_type=coordinate_type,
            ),
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "data_table_id")
    async def add_stock_chart(
        self,
        notebook_id: str,
        data_table_id: str,
        x_field: str,
        open_field: str,
        close_field: str,
        low_field: str,
        high_field: str,
        title: str = "Stock Chart",
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add stock chart to notebook."""
        return await self._add_chart_block(
            chart_kind="stock",
            notebook_id=notebook_id,
            data_table_id=data_table_id,
            fields={
                "x_field": x_field,
                "y_field": [open_field, close_field, low_field, high_field],
            },
            title=title,
            position=position,
            run_context=run_context,
            build_config=lambda: ChartService.create_stock_chart_config(
                title=title,
                x_field=x_field,
                open_field=open_field,
                close_field=close_field,
                low_field=low_field,
                high_field=high_field,
            ),
        )

    @updates_artifact(
        NotebookMultiBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Import Chart",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id", "chart_id")
    async def import_chart(
        self, notebook_id: str, chart_id: str, position: int | None = None
    ) -> str:
        """Import a chart referenced by chart_id into the notebook.

        This will create two blocks in the notebook:
        1. A data table (SQL) block with the chart's data table
        2. A Chart block with the chart's configuration, linked to the new data table block

        :param notebook_id: The ID of the notebook to import into
        :param chart_id: The ID of the chart document (.chart file) to import
        :param position: Optional position to insert the blocks at
        """

        async def import_chart_op():
            # 1. Fetch the chart document
            if not self.file_service:
                raise ValueError("File service is not available")

            content = await self.file_service.get_file_content(self.project_id, chart_id)
            chart = ChartDocument.model_validate_json(content)

            blocks_added = []

            # 2. Re-construct data table block
            ds_to_use: InlineData | None = chart.inline_data
            effective_ds_id: str

            # Prefer an explicit reference from the chart document if present.
            if chart.data_ref and chart.data_ref.data_id:
                effective_ds_id = chart.data_ref.data_id
            # If the chart only contains embedded data, persist it through the
            # canonical materialization path and use the returned file id.
            elif ds_to_use is not None:
                materialized_id = await self.file_service.materialize_inline_data(
                    project_id=self.project_id,
                    inline_data=ds_to_use,
                    name=(ds_to_use.title or f"Data for {chart.name}"),
                    notebook_id=notebook_id,
                    chat_session_id=self.chat_session_id,
                    sql=chart.data_ref.code if chart.data_ref else None,
                )
                if materialized_id is None:
                    raise ValueError("Chart data table could not be materialized.")
                effective_ds_id = materialized_id
            else:
                effective_ds_id = str(uuid4())

            # Check if this data ID is already in the notebook - if so, we do not need to add it again
            existing_sql_block_id = None
            notebook = self.editor.get_notebook()
            for block in notebook.blocks:
                # NotebookBlock wraps the actual block in .root
                b: Any = block.root if hasattr(block, "root") else block
                if (
                    b.type == NotebookBlockType.SQL
                    and hasattr(b.data, "data_ref")
                    and b.data.data_ref
                    and b.data.data_ref.data_id == effective_ds_id
                ):
                    existing_sql_block_id = str(b.id)
                    break

            if not existing_sql_block_id:
                # If we have a reference but no embedded, try to fetch the reference to get SQL
                if not ds_to_use and chart.data_ref and chart.data_ref.data_id:
                    with suppress(Exception):
                        ref_content = await self.file_service.get_file_content(
                            self.project_id, chart.data_ref.data_id
                        )
                        ds_to_use = InlineData.model_validate_json(ref_content)

                # Prepare SQL Block Data
                # Try to get SQL from embedded data table, then from reference, then fallback
                sql_code = None  # InlineData no longer stores SQL
                if not sql_code and chart.data_ref:
                    sql_code = chart.data_ref.code

                if not sql_code:
                    sql_code = f"-- Imported from Chart '{chart.name}'\n-- Original Data Table: {effective_ds_id}"

                sql_block_data = SqlBlockData(
                    code=sql_code,
                    title=f"Data for {chart.name}",
                    data_ref=DataRef(data_id=effective_ds_id),
                    is_executing=False,
                )

                sql_block = SqlBlock(id=str(uuid4()), type="sql", data=sql_block_data)
                nb_sql_block = NotebookBlock(sql_block)

                # Add SQL block
                self.editor.add_block(nb_sql_block, position)
                blocks_added.append(str(sql_block.id))
            else:
                pass

            # 3. Create Chart Block linked to this (new) SQL Block
            chart_config = chart.config
            if not chart_config:
                raise ValueError(f"Chart '{chart.name}' has no configuration.")

            # Add Chart block immediately after the SQL block (if we added one) or at current position
            chart_pos = None
            if position is not None:
                chart_pos = position + 1 if not existing_sql_block_id else position

            # Create a reference that points to the ID used in the SQL block above
            new_ds_ref = DataRef(
                data_id=effective_ds_id,
                connection_id=(chart.data_ref.connection_id if chart.data_ref else None),
                code=chart.data_ref.code if chart.data_ref else None,
            )

            nb_chart_block = self.editor.add_chart_block(
                chart_config=chart_config, data_ref=new_ds_ref, inline_data=None, position=chart_pos
            )

            # Extract ID from the added block
            inner_block: Any = (
                nb_chart_block.root if hasattr(nb_chart_block, "root") else nb_chart_block
            )
            blocks_added.append(str(inner_block.id))

            return blocks_added

        # Execute
        result_block_ids, actions, error = await self._handle_operation(
            f"Importing chart {chart_id}", self.project_id, notebook_id, import_chart_op
        )

        if error:
            return self._create_result(
                success=False,
                result_class=NotebookMultiBlockResult,
                notebook_id=notebook_id,
                block_ids=[],
                error=str(error),
                message=f"Failed to import chart: {error}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookMultiBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_ids=result_block_ids or [],
            blocks_count=len(result_block_ids or []),
            message="Successfully imported chart and data table into notebook.",
        )

    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Edit Chart Block",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id", "block_id")
    async def edit_chart_block(
        self,
        notebook_id: str,
        block_id: str,
        config: dict[str, Any],
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Update a notebook chart block's configuration in place.

        ``config`` is a flat camelCase chart configuration object with an
        explicit ``chartType`` (line, bar, column, area, pie, scatter, dualAxes,
        funnel, heatmap, histogram, box, radar, stock), ``title`` and
        ``height``, then the kind's field keys. The block keeps its id,
        position, and data reference - prefer this over delete-and-re-add for
        small changes.

        :param notebook_id: Notebook ID.
        :param block_id: Chart block ID.
        :param config: Flat chart configuration object.
        :param run_context: runtime context.
        """

        async def edit_operation():
            block = self.editor.get_block(block_id)
            if block is None:
                raise ValueError(f"Block {block_id} not found")

            block_root = block.root
            if not isinstance(block_root, ChartBlock) or not isinstance(block_root.data, ChartSpec):
                raise ValueError(f"Block {block_id} is not a chart block")

            chart_config = parse_flat_chart_config(config)
            chart_spec = block_root.data.model_copy(update={"config": chart_config})
            self.editor.edit_block(block_id, BlockData(chart_spec))
            return self.editor.get_block(block_id)

        block, actions, error = await self._handle_operation(
            f"Editing chart block {block_id}",
            self.project_id,
            notebook_id,
            edit_operation,
            run_context=run_context,
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                error=error,
                message=f"Error editing chart block {block_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=block_id,
            block=block,
            error=None,
            message=f"Successfully edited chart block {block_id}",
        )
