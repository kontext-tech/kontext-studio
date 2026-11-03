import { z } from "zod";
import {
   DataRefSchema,
   InlineDataSchema,
   DataTableSchema,
   DataTableSummarySchema
} from "../core/data";
import { areaChartSchema } from "./areaChart";
import { barChartSchema } from "./barChart";
import { boxChartSchema } from "./boxChart";
import type { ChartType } from "./base";
import { columnChartSchema } from "./columnChart";
import { dualAxesChartSchema } from "./dualAxesChart";
import { funnelChartSchema } from "./funnelChart";
import { heatMapSchema } from "./heatMap";
import { histogramChartSchema } from "./histogramChart";
import { lineChartSchema } from "./lineChart";
import { pieChartSchema } from "./pieChart";
import { radarChartSchema } from "./radarChart";
import { scatterChartSchema } from "./scatterChart";
import { stockChartSchema } from "./stockChart";

export {
   DataRefSchema,
   InlineDataSchema,
   DataTableSchema,
   DataTableSummarySchema
};

export const CHART_SCHEMAS_ARRAY = [
   lineChartSchema,
   barChartSchema,
   columnChartSchema,
   areaChartSchema,
   pieChartSchema,
   scatterChartSchema,
   dualAxesChartSchema,
   funnelChartSchema,
   heatMapSchema,
   histogramChartSchema,
   boxChartSchema,
   radarChartSchema,
   stockChartSchema
] as const;

export const CHART_SCHEMAS = {
   line: lineChartSchema,
   bar: barChartSchema,
   column: columnChartSchema,
   area: areaChartSchema,
   pie: pieChartSchema,
   scatter: scatterChartSchema,
   dualAxes: dualAxesChartSchema,
   funnel: funnelChartSchema,
   heatmap: heatMapSchema,
   histogram: histogramChartSchema,
   box: boxChartSchema,
   radar: radarChartSchema,
   stock: stockChartSchema
} as const;

export function getChartSchema(chartType: ChartType) {
   return CHART_SCHEMAS[chartType];
}

export function hasChartSchema(chartType: ChartType): boolean {
   return chartType in CHART_SCHEMAS;
}

export function getAllChartTypes(): ChartType[] {
   return Object.keys(CHART_SCHEMAS) as ChartType[];
}

export const ChartConfigSchema = z
   .discriminatedUnion("chartType", CHART_SCHEMAS_ARRAY)
   .describe(
      "Flat chart configuration object: set `chartType` (line, bar, column, area, pie, scatter, dualAxes, funnel, heatmap, histogram, box, radar, stock) and the kind's field keys, in camelCase (xField/yField — never x/y shorthand, never a {bar: {...}} wrapper). Common keys: chartType, title, height (required for every kind), then the kind's required field keys: line/bar/column/area/scatter/funnel/heatmap/box/radar -> xField, yField; pie -> angleField; histogram -> binField; dualAxes -> xField, leftYField, leftChartType, rightYField, rightChartType; stock -> xField, yField (4 columns). Series/grouping uses colorField (combine with stack or group); seriesField is funnel-only."
   );

export type ChartConfig = z.infer<typeof ChartConfigSchema>;

/**
 * Unified chart specification that can be used both in notebook blocks
 * and standalone .chart files.
 *
 * It prioritizes embedded 'inlineData' if present, otherwise uses 'dataRef'.
 */
export const ChartSpecSchema = z
   .object({
      /**
       * Chart configuration (type, title, mappings, etc.)
       */
      config: ChartConfigSchema.describe(
         "Chart configuration including type and visual mappings"
      ),

      /**
       * Data table reference (lazy-loaded data)
       */
      dataRef: DataRefSchema.optional().describe(
         "Reference to an external data table (file or notebook resource)"
      ),

      /**
       * Embedded data (inline data)
       */
      inlineData: InlineDataSchema.optional().describe(
         "Embedded inline data. If present, it takes priority over dataRef."
      ),

      /**
       * Data summary (schema and row count)
       * Provides context for LLM agents without loading full data.
       */
      dataSummary: DataTableSummarySchema.optional().describe(
         "Summary of the underlying data (schema and row count) for context."
      )
   })
   .describe(
      "Unified chart specification with config and data table input (embedded or referenced)"
   );

export type ChartSpec = z.infer<typeof ChartSpecSchema>;
