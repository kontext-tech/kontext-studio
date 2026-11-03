"""
ChartService - Shared chart configuration generation logic.

This service provides container-blind, static configuration generators
for all supported chart types, working only with ChartSpec and DataTable schemas.
"""

from kontext.schema import (
    AreaChartConfig,
    BarChartConfig,
    BoxChartConfig,
    BoxChartType,
    ChartConfig,
    ColumnChartConfig,
    DualAxesChartConfig,
    DualAxesChartType,
    FunnelChartConfig,
    HeatmapChartConfig,
    HistogramChartConfig,
    LineChartConfig,
    MarkTypes,
    PieChartConfig,
    RadarChartConfig,
    RadarCoordinateType,
    ScatterChartConfig,
    StockChartConfig,
)


class ChartService:
    """
    Shared service for chart configuration generation.

    All methods are static and container-blind, working only with chart schemas.
    This service can be used by both NotebookEditor (for chart blocks) and
    ChartEditor (for standalone .chart files).
    """

    @staticmethod
    def create_line_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a line chart configuration."""
        line_config = LineChartConfig(
            chart_type="line",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            **kwargs,
        )
        return ChartConfig(line_config)

    @staticmethod
    def create_bar_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a bar chart configuration."""
        bar_config = BarChartConfig(
            chart_type="bar",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            **kwargs,
        )
        return ChartConfig(bar_config)

    @staticmethod
    def create_pie_chart_config(
        title: str, angle_field: str, color_field: str, height: float = 400.0, **kwargs
    ) -> ChartConfig:
        """Create a pie chart configuration."""
        pie_config = PieChartConfig(
            chart_type="pie",
            title=title,
            height=height,
            angle_field=angle_field,
            color_field=color_field,
            **kwargs,
        )
        return ChartConfig(pie_config)

    @staticmethod
    def create_scatter_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        size_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a scatter chart configuration."""
        scatter_config = ScatterChartConfig(
            chart_type="scatter",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            size_field=size_field,
            **kwargs,
        )
        return ChartConfig(scatter_config)

    @staticmethod
    def create_area_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create an area chart configuration."""
        area_config = AreaChartConfig(
            chart_type="area",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            **kwargs,
        )
        return ChartConfig(area_config)

    @staticmethod
    def create_column_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a column chart configuration."""
        column_config = ColumnChartConfig(
            chart_type="column",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            **kwargs,
        )
        return ChartConfig(column_config)

    @staticmethod
    def create_dual_axes_chart_config(
        title: str,
        x_field: str,
        left_y_field: str,
        left_chart_type: DualAxesChartType,
        right_y_field: str,
        right_chart_type: DualAxesChartType,
        height: float = 400.0,
        left_color_field: str | None = None,
        right_color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a dual axes chart configuration."""
        dual_axes_config = DualAxesChartConfig(
            chart_type="dualAxes",
            title=title,
            height=height,
            x_field=x_field,
            left_y_field=left_y_field,
            left_chart_type=left_chart_type,
            right_y_field=right_y_field,
            right_chart_type=right_chart_type,
            left_color_field=left_color_field,
            right_color_field=right_color_field,
            **kwargs,
        )
        return ChartConfig(dual_axes_config)

    @staticmethod
    def create_funnel_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        compare_field: str | None = None,
        series_field: str | None = None,
        is_transposed: bool | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a funnel chart configuration."""
        funnel_config = FunnelChartConfig(
            chart_type="funnel",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            compare_field=compare_field,
            series_field=series_field,
            is_transposed=is_transposed,
            **kwargs,
        )
        return ChartConfig(funnel_config)

    @staticmethod
    def create_heatmap_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        size_field: str | None = None,
        shape_field: str | None = None,
        mark: MarkTypes | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a heatmap chart configuration."""
        heatmap_config = HeatmapChartConfig(
            chart_type="heatmap",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            size_field=size_field,
            shape_field=shape_field,
            mark=mark,
            **kwargs,
        )
        return ChartConfig(heatmap_config)

    @staticmethod
    def create_histogram_chart_config(
        title: str,
        bin_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        bin_width: float | None = None,
        bin_number: int | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a histogram chart configuration."""
        histogram_config = HistogramChartConfig(
            chart_type="histogram",
            title=title,
            height=height,
            bin_field=bin_field,
            color_field=color_field,
            bin_width=bin_width,
            bin_number=bin_number,
            **kwargs,
        )
        return ChartConfig(histogram_config)

    @staticmethod
    def create_box_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        box_type: BoxChartType | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a box chart configuration."""
        box_config = BoxChartConfig(
            chart_type="box",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            box_type=box_type,
            **kwargs,
        )
        return ChartConfig(box_config)

    @staticmethod
    def create_radar_chart_config(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        coordinate_type: RadarCoordinateType | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a radar chart configuration."""
        radar_config = RadarChartConfig(
            chart_type="radar",
            title=title,
            height=height,
            x_field=x_field,
            y_field=y_field,
            color_field=color_field,
            coordinate_type=coordinate_type,
            **kwargs,
        )
        return ChartConfig(radar_config)

    @staticmethod
    def create_stock_chart_config(
        title: str,
        x_field: str,
        open_field: str,
        close_field: str,
        low_field: str,
        high_field: str,
        height: float = 400.0,
        **kwargs,
    ) -> ChartConfig:
        """Create a stock chart configuration."""
        stock_config = StockChartConfig(
            chart_type="stock",
            title=title,
            height=height,
            x_field=x_field,
            y_field=[open_field, close_field, low_field, high_field],
            **kwargs,
        )
        return ChartConfig(stock_config)
