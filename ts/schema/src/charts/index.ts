import { type AreaChartConfig } from "./areaChart";
import { type BarChartConfig } from "./barChart";
import { type BoxChartConfig, type BoxChartConfigLegend } from "./boxChart";
import { MARK_TYPES } from "./base";
import { type ColumnChartConfig } from "./columnChart";
import { type DualAxesChartConfig } from "./dualAxesChart";
import { type FunnelChartConfig } from "./funnelChart";
import { type HeatMapConfig } from "./heatMap";
import { type HistogramChartConfig } from "./histogramChart";
import { type LineChartConfig } from "./lineChart";
import { type PieChartConfig } from "./pieChart";
import { type RadarChartConfig } from "./radarChart";
import { type ScatterChartConfig } from "./scatterChart";
import { type StockChartConfig, type StockYField } from "./stockChart";

export type {
   AreaChartConfig,
   BarChartConfig,
   BoxChartConfig,
   BoxChartConfigLegend,
   ColumnChartConfig,
   DualAxesChartConfig,
   FunnelChartConfig,
   HeatMapConfig as HeatmapChartConfig,
   HeatMapConfig,
   HistogramChartConfig,
   LineChartConfig,
   PieChartConfig,
   RadarChartConfig,
   ScatterChartConfig,
   StockChartConfig,
   StockYField
};

export { MARK_TYPES };

export {
   AggregateMethod,
   AggregateMethodSchema,
   AggregateSchema,
   chartGroupConfigSchema,
   chartGroupConfigSchema as ChartGroupConfigSchema,
   chartStackConfigSchema,
   chartStackConfigSchema as ChartStackConfigSchema,
   ChartType,
   ChartTypeSchema,
   ColorPalette,
   ColorPaletteSchema,
   ConnectNullsObjectSchema,
   ConnectNullsSchema,
   MarkTypes,
   MarkTypesSchema,
   NumberFormat,
   NumberFormatSchema,
   type ChartGroupConfig,
   type ChartStackConfig,
   type ConnectNulls,
   type ConnectNullsObject
} from "./base";

export {
   areaChartSchema as AreaChartConfigSchema,
   areaChartSchema
} from "./areaChart";
export {
   barChartSchema as BarChartConfigSchema,
   barChartSchema
} from "./barChart";
export {
   boxChartSchema as BoxChartConfigSchema,
   BoxChartType,
   boxChartSchema,
   BoxChartConfigLegendSchema,
   BoxChartTypeSchema
} from "./boxChart";
export {
   columnChartSchema as ColumnChartConfigSchema,
   columnChartSchema
} from "./columnChart";
export {
   dualAxesChartSchema as DualAxesChartConfigSchema,
   dualAxesChartSchema
} from "./dualAxesChart";
export {
   funnelChartSchema as FunnelChartConfigSchema,
   funnelChartSchema
} from "./funnelChart";
export {
   heatMapSchema as HeatmapChartConfigSchema,
   heatMapSchema
} from "./heatMap";
export {
   histogramChartSchema as HistogramChartConfigSchema,
   histogramChartSchema
} from "./histogramChart";
export {
   lineChartSchema as LineChartConfigSchema,
   lineChartSchema
} from "./lineChart";
export {
   pieChartSchema as PieChartConfigSchema,
   pieChartSchema
} from "./pieChart";
export {
   radarChartSchema as RadarChartConfigSchema,
   RadarCoordinateType,
   radarChartSchema,
   RadarCoordinateTypeSchema
} from "./radarChart";
export {
   scatterChartSchema as ScatterChartConfigSchema,
   scatterChartSchema
} from "./scatterChart";
export {
   stockChartSchema as StockChartConfigSchema,
   stockChartSchema,
   StockYFieldSchema
} from "./stockChart";

export * from "./document";
export { DualAxesChartType, DualAxesChartTypeSchema } from "./dualAxesChart";
export * from "./spec";
