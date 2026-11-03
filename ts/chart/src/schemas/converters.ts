/**
 * Chart configuration converters
 * Utilities to convert Kontext chart configs to Ant Design Charts format
 */

import type {
   AreaChartConfig,
   BarChartConfig,
   BoxChartConfig,
   ChartConfig,
   ColumnChartConfig,
   DualAxesChartConfig,
   FunnelChartConfig,
   HeatMapConfig,
   HistogramChartConfig,
   LineChartConfig,
   NumberFormat,
   PieChartConfig,
   RadarChartConfig,
   ScatterChartConfig,
   StockChartConfig
} from "@kontext-labs/schema";
import { aggregateData } from "@kontext-labs/common/utils";
import { getChartAggregatedData } from "../utils/dataAggregation";
import { formatNumber } from "../utils/formatUtils";

/**
 * Helper to create scale configuration for number formatting
 */
function createNumberScale(
   fields: (string | undefined)[],
   format: NumberFormat = "short"
) {
   const scale: Record<string, unknown> = {};
   fields.forEach((field) => {
      if (field) {
         scale[field] = {
            formatter: (v: number | string) => formatNumber(v, format)
         };
      }
   });
   return scale;
}

function isScaleConfigRecord(value: unknown): value is Record<string, unknown> {
   return typeof value === "object" && value !== null && !Array.isArray(value);
}

function mergeScaleConfigs(...scales: (Record<string, unknown> | undefined)[]) {
   const merged: Record<string, unknown> = {};

   scales.forEach((scale) => {
      if (!scale) {
         return;
      }

      Object.entries(scale).forEach(([field, value]) => {
         const existing = merged[field];
         if (isScaleConfigRecord(existing) && isScaleConfigRecord(value)) {
            merged[field] = {
               ...existing,
               ...value
            };
            return;
         }

         merged[field] = value;
      });
   });

   return merged;
}

/**
 * Base conversion for common chart properties
 */
function convertBaseConfig(config: ChartConfig) {
   return {
      height: config.height,
      data: config.data || [], // Use the provided data or empty array as fallback
      title: config.title, // Include chart title in Ant Design Charts config
      colorPalette: config.colorPalette // Include color palette for theme application
      // Note: external data wiring is Kontext-specific and not passed to Ant Design Charts
   };
}

/**
 * Convert line chart config to Ant Design Charts LineOptions
 */
export function convertLineChartConfig(config: LineChartConfig) {
   const data = getChartAggregatedData(config, config.data || []);

   return {
      ...convertBaseConfig(config),
      data,
      xField: config.xField,
      yField: config.yField,
      colorField: config.colorField,
      connectNulls: config.connectNulls,
      scale: createNumberScale([config.yField], config.numberFormat)
   };
}

/**
 * Convert pie chart config to Ant Design Charts PieOptions
 */
export function convertPieChartConfig(config: PieChartConfig) {
   const data = getChartAggregatedData(config, config.data || []);

   return {
      ...convertBaseConfig(config),
      padding: "auto",
      data,
      angleField: config.angleField,
      colorField: config.colorField,
      scale: createNumberScale([config.angleField], config.numberFormat)
   };
}

/**
 * Convert bar chart config to Ant Design Charts BarOptions
 */
export function convertBarChartConfig(config: BarChartConfig) {
   const data = getChartAggregatedData(config, config.data || []);

   return {
      ...convertBaseConfig(config),
      data,
      xField: config.xField,
      yField: config.yField,
      colorField: config.colorField,
      stack: config.stack,
      group: config.group,
      scale: createNumberScale([config.yField], config.numberFormat)
   };
}

/**
 * Convert column chart config to Ant Design Charts ColumnOptions
 */
export function convertColumnChartConfig(config: ColumnChartConfig) {
   const data = getChartAggregatedData(config, config.data || []);

   return {
      ...convertBaseConfig(config),
      data,
      xField: config.xField,
      yField: config.yField,
      colorField: config.colorField,
      stack: config.stack,
      group: config.group,
      scale: createNumberScale([config.yField], config.numberFormat)
   };
}

/**
 * Convert area chart config to Ant Design Charts AreaOptions
 */
export function convertAreaChartConfig(config: AreaChartConfig) {
   const data = getChartAggregatedData(config, config.data || []);

   return {
      ...convertBaseConfig(config),
      data,
      xField: config.xField,
      yField: config.yField,
      colorField: config.colorField,
      stack: config.stack,
      scale: createNumberScale([config.yField], config.numberFormat)
   };
}

/**
 * Convert scatter chart config to Ant Design Charts ScatterOptions
 */
export function convertScatterChartConfig(config: ScatterChartConfig) {
   const format = config.numberFormat;
   return {
      ...convertBaseConfig(config),
      xField: config.xField,
      yField: config.yField,
      sizeField: config.sizeField,
      colorField: config.colorField,
      scale: createNumberScale(
         [config.xField, config.yField, config.sizeField],
         format
      )
   };
}

/**
 * Convert dual axes chart config to Ant Design Charts DualAxesOptions
 * Converts flattened structure back to children array format
 */
export function convertDualAxesChartConfig(config: DualAxesChartConfig) {
   const baseConfig = convertBaseConfig(config);
   const format = config.numberFormat;

   // Create children array from flattened structure
   const children = [
      // Left axis (typically bar/column)
      {
         data:
            config.leftAggregate && config.leftAggregate !== "none"
               ? aggregateData(config.data || [], {
                    dimensionFields: [
                       config.xField,
                       config.leftColorField
                    ].filter((f): f is string => !!f),
                    metricFields: [config.leftYField],
                    aggregationFunction: config.leftAggregate
                 }).data
               : config.data, // Each child needs its own data
         type: (config.leftChartType || "Interval").toLowerCase(),
         xField: config.xField,
         yField: config.leftYField,
         ...(config.leftColorField
            ? { colorField: config.leftColorField }
            : {}),
         // Only add stack for interval and area chart types
         ...(config.leftStack &&
         (config.leftChartType === "interval" ||
            config.leftChartType === "area")
            ? { stack: config.leftStack }
            : {}),
         axis: {
            y: {
               labelFormatter: (v: number | string) => formatNumber(v, format)
            }
         }
      },
      // Right axis (typically line)
      {
         data:
            config.rightAggregate && config.rightAggregate !== "none"
               ? aggregateData(config.data || [], {
                    dimensionFields: [
                       config.xField,
                       config.rightColorField
                    ].filter((f): f is string => !!f),
                    metricFields: [config.rightYField],
                    aggregationFunction: config.rightAggregate
                 }).data
               : config.data, // Each child needs its own data
         type: (config.rightChartType || "line").toLowerCase(),
         xField: config.xField,
         yField: config.rightYField,
         ...(config.rightColorField
            ? { colorField: config.rightColorField }
            : {}),
         // Only add stack for interval and area chart types
         ...(config.rightStack &&
         (config.rightChartType === "interval" ||
            config.rightChartType === "area")
            ? { stack: config.rightStack }
            : {}),
         axis: {
            y: {
               position: "right",
               labelFormatter: (v: number | string) => formatNumber(v, format)
            }
         }
      }
   ].filter((child) => child.yField); // Only include children with valid yField

   return {
      ...baseConfig,
      xField: config.xField,
      children,
      scale: createNumberScale([config.leftYField, config.rightYField], format)
   };
}

/**
 * Convert funnel chart config to Ant Design Charts FunnelOptions
 */
export function convertFunnelChartConfig(config: FunnelChartConfig) {
   return {
      ...convertBaseConfig(config),
      xField: config.xField,
      yField: config.yField,
      ...(config.compareField ? { compareField: config.compareField } : {}),
      ...(config.seriesField ? { seriesField: config.seriesField } : {}),
      ...(config.isTransposed !== undefined
         ? { isTransposed: config.isTransposed }
         : {}),
      scale: createNumberScale([config.yField], config.numberFormat)
   };
}

/**
 * Convert heat map chart config to Ant Design Charts HeatmapOptions
 */
export function convertHeatMapChartConfig(config: HeatMapConfig) {
   const format = config.numberFormat;
   return {
      ...convertBaseConfig(config),
      xField: config.xField,
      yField: config.yField,
      colorField: config.colorField,
      sizeField: config.sizeField,
      ...(config.shapeField ? { shapeField: config.shapeField } : {}),
      ...(config.label ? { label: config.label } : {}),
      ...(config.mark ? { mark: config.mark } : {}),
      scale: createNumberScale([config.colorField, config.sizeField], format)
   };
}

/**
 * Convert histogram chart config to Ant Design Charts HistogramOptions
 */
export function convertHistogramChartConfig(config: HistogramChartConfig) {
   return {
      ...convertBaseConfig(config),
      data: config.data || [],
      binField: config.binField,
      colorField: config.colorField,
      binWidth: config.binWidth,
      binNumber: config.binNumber,
      channel: config.channel,
      stack: config.stack,
      style: config.style
   };
}

/**
 * Convert box chart config to Ant Design Charts BoxOptions
 */
export function convertBoxChartConfig(config: BoxChartConfig) {
   return {
      ...convertBaseConfig(config),
      data: config.data || [],
      xField: config.xField,
      yField: config.yField,
      colorField: config.colorField,
      boxType: config.boxType,
      legend: config.legend,
      style: config.style,
      scale: config.scale
   };
}

/**
 * Convert radar chart config to Ant Design Charts RadarOptions
 */
export function convertRadarChartConfig(config: RadarChartConfig) {
   // `@ant-design/plots` currently throws for `coordinateType: "radar"`
   // (`Missing encode for position channel`), so we render through the
   // compatible polar path until the upstream radar coordinate is stable.
   const coordinateType =
      config.coordinateType === "radar"
         ? "polar"
         : (config.coordinateType ?? "polar");

   return {
      ...convertBaseConfig(config),
      data: config.data || [],
      xField: config.xField,
      yField: config.yField,
      colorField: config.colorField,
      coordinateType,
      axis: config.axis,
      area: config.area,
      point: config.point,
      style: config.style,
      scale: mergeScaleConfigs(
         createNumberScale([config.yField], config.numberFormat),
         config.scale
      )
   };
}

/**
 * Convert stock chart config to Ant Design Charts StockOptions
 */
export function convertStockChartConfig(config: StockChartConfig) {
   return {
      ...convertBaseConfig(config),
      data: config.data || [],
      xField: config.xField,
      yField: config.yField,
      lineStyle: config.lineStyle,
      style: config.style,
      tooltip: config.tooltip,
      scale: createNumberScale(config.yField, config.numberFormat)
   };
}

/**
 * Main converter function that routes to appropriate converter based on chart type
 */
export function convertChartConfig(config: ChartConfig): unknown {
   switch (config.chartType) {
      case "line":
         return convertLineChartConfig(config as LineChartConfig);
      case "pie":
         return convertPieChartConfig(config as PieChartConfig);
      case "bar":
         return convertBarChartConfig(config as BarChartConfig);
      case "column":
         return convertColumnChartConfig(config as ColumnChartConfig);
      case "area":
         return convertAreaChartConfig(config as AreaChartConfig);
      case "scatter":
         return convertScatterChartConfig(config as ScatterChartConfig);
      case "dualAxes":
         return convertDualAxesChartConfig(config as DualAxesChartConfig);
      case "funnel":
         return convertFunnelChartConfig(config as FunnelChartConfig);
      case "heatmap":
         return convertHeatMapChartConfig(config as HeatMapConfig);
      case "histogram":
         return convertHistogramChartConfig(config as HistogramChartConfig);
      case "box":
         return convertBoxChartConfig(config as BoxChartConfig);
      case "radar":
         return convertRadarChartConfig(config as RadarChartConfig);
      case "stock":
         return convertStockChartConfig(config as StockChartConfig);
      default:
         throw new Error(`Unsupported chart type.`);
   }
}
