// Export chart types (excluding ChartConfig to avoid conflict)
export type {
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
} from "./types/chart";

// Export Chart instance type from @ant-design/plots
export type { Chart } from "@ant-design/plots";

// Export chart constants
export * from "./constants";

// Export chart type constants
export { CHART_TYPE_ICONS, CHART_TYPE_NAMES } from "./types/chart";

// Export chart schemas and validation from centralized @kontext-tech/schema
export {
   CHART_SCHEMAS,
   CHART_SCHEMAS_ARRAY,
   ChartConfigSchema,
   getAllChartTypes,
   getChartSchema,
   hasChartSchema
} from "@kontext-tech/schema";

// Export chart validation utilities (charts-specific)
export { validateChartConfig as validateChart } from "./schemas/validation";

// Export converters (charts-specific utilities)
export * from "./schemas/converters";

// Export chart utilities
export * from "./utils/chartExport";
export * from "./utils/colorPalettes";
export * from "./utils/dataAggregation";
export * from "./utils/themeUtils";

// Export chart components
export * from "./components";

// Export chart hooks
export * from "./hooks/useChartDataAggregation";
export {
   useChartFileHelpers,
   useChartFileWorkflow,
   type UseChartFileHelpersReturn
} from "./hooks/useChartFileHelpers";

// Export additional components
export { ColorPalettePreview } from "./components/ColorPalettePreview";
