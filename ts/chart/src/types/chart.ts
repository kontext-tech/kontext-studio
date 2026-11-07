// Import chart config types from schemas (these are generated from Zod schemas)
import type {
   AreaChartConfig,
   BarChartConfig,
   BoxChartConfig,
   ChartConfig,
   ChartType,
   ColumnChartConfig,
   DualAxesChartConfig,
   FunnelChartConfig,
   HeatMapConfig,
   HistogramChartConfig,
   LineChartConfig,
   PieChartConfig,
   RadarChartConfig,
   ScatterChartConfig,
   StockChartConfig
} from "@kontext-tech/schema";

export type { ChartConfig };

/**
 * Simple field definition for chart configuration
 */
export interface Field {
   name: string;
   type: string;
}

/**
 * Supported chart types from Ant Design Charts
 * Inferred from Zod schema for type safety and consistency
 */
export { type ChartType };

// Re-export the schema-generated types directly
export type {
   AreaChartConfig,
   BarChartConfig,
   BoxChartConfig,
   ColumnChartConfig,
   DualAxesChartConfig,
   FunnelChartConfig,
   HeatMapConfig,
   HistogramChartConfig,
   LineChartConfig,
   PieChartConfig,
   RadarChartConfig,
   ScatterChartConfig,
   StockChartConfig
};

/**
 * Chart type display names for UI
 */
export const CHART_TYPE_NAMES: Record<ChartType, string> = {
   line: "Line Chart",
   bar: "Bar Chart",
   column: "Column Chart",
   area: "Area Chart",
   pie: "Pie Chart",
   scatter: "Scatter Plot",
   dualAxes: "Mixed Chart",
   funnel: "Funnel Chart",
   heatmap: "Heat Map",
   histogram: "Histogram",
   box: "Box Chart",
   radar: "Radar Chart",
   stock: "Stock Chart"
};

/**
 * Chart type icons for UI (using Ant Design icon names)
 */
export const CHART_TYPE_ICONS: Record<ChartType, string> = {
   line: "LineChartOutlined",
   bar: "BarChartOutlined",
   column: "ColumnHeightOutlined",
   area: "AreaChartOutlined",
   pie: "PieChartOutlined",
   scatter: "DotChartOutlined",
   dualAxes: "StockOutlined",
   funnel: "FunnelPlotOutlined",
   heatmap: "HeatMapOutlined",
   histogram: "BarChartOutlined",
   box: "ChartNoAxesCombinedOutlined",
   radar: "DotChartOutlined",
   stock: "StockOutlined"
};
