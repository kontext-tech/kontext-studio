/**
 * Data aggregation utilities for chart data
 * Supports simple aggregation when dimensions have duplicate values
 */

import {
   aggregateData,
   type AggregationFunction
} from "@kontext-labs/common/utils";
import type { TabularData } from "@kontext-labs/schema";
import type { ChartConfig } from "../types/chart";

/**
 * Gets aggregated data for a specific chart configuration.
 * Automatically identifies dimension and metric fields based on chart type.
 */
export function getChartAggregatedData(
   config: ChartConfig,
   data: TabularData
): TabularData {
   if (!data || data.length === 0) return [];

   // Separate logic for DualAxes as it has child axes
   if (config.chartType === "dualAxes") {
      // NOTE: For DualAxes, strictly speaking, it needs two sets of data if aggregations differ.
      // However, for single data return (e.g. data preview), we merge the metrics.
      const dimensionFields = [config.xField];
      if (config.leftColorField) dimensionFields.push(config.leftColorField);
      if (config.rightColorField) dimensionFields.push(config.rightColorField);

      const metricFields = [];
      if (config.leftYField) metricFields.push(config.leftYField);
      if (config.rightYField) metricFields.push(config.rightYField);

      // We use the left aggregation as the primary if they differ, or none if both are none
      const aggFunc =
         config.leftAggregate !== "none"
            ? config.leftAggregate
            : config.rightAggregate;

      if (!aggFunc || aggFunc === "none") return data;

      return aggregateData(data, {
         dimensionFields: Array.from(new Set(dimensionFields.filter(Boolean))),
         metricFields: Array.from(new Set(metricFields.filter(Boolean))),
         aggregationFunction: aggFunc as AggregationFunction
      }).data;
   }

   // Standard chart types
   const dimensionFields: string[] = [];
   const metricFields: string[] = [];
   let aggregateMethod: string | undefined;

   // Map fields based on chart config properties
   if ("xField" in config && typeof config.xField === "string")
      dimensionFields.push(config.xField);
   if ("yField" in config && typeof config.yField === "string")
      metricFields.push(config.yField);
   if ("colorField" in config && typeof config.colorField === "string")
      dimensionFields.push(config.colorField);
   if ("seriesField" in config && typeof config.seriesField === "string")
      dimensionFields.push(config.seriesField);
   if ("angleField" in config && typeof config.angleField === "string")
      metricFields.push(config.angleField);
   if ("sizeField" in config && typeof config.sizeField === "string")
      metricFields.push(config.sizeField);

   if ("aggregate" in config && typeof config.aggregate === "string") {
      aggregateMethod = config.aggregate;
   }

   if (
      !aggregateMethod ||
      aggregateMethod === "none" ||
      metricFields.length === 0
   ) {
      return data;
   }

   return aggregateData(data, {
      dimensionFields: Array.from(new Set(dimensionFields.filter(Boolean))),
      metricFields: Array.from(new Set(metricFields.filter(Boolean))),
      aggregationFunction: aggregateMethod as AggregationFunction
   }).data;
}
