import type { TabularData } from "@kontext-tech/schema";
import { useMemo } from "react";
import type { ChartConfig } from "../types/chart";
import { getChartAggregatedData } from "../utils/dataAggregation";

export interface UseChartDataAggregationOptions {
   /** Enable auto-aggregation based on config */
   autoAggregate?: boolean;
}

export interface UseChartDataAggregationResult {
   /** The processed data */
   data: TabularData;
   /** Whether aggregation was applied based on config */
   aggregated: boolean;
}

/**
 * Hook to process chart data with optional aggregation.
 * Leverages the central getChartAggregatedData utility for consistency.
 *
 * @param data - The input data
 * @param config - Chart configuration
 * @param options - Hook options
 * @returns Processed data and aggregation status
 */
export function useChartDataAggregation(
   data: TabularData,
   config?: ChartConfig,
   options?: UseChartDataAggregationOptions
): UseChartDataAggregationResult {
   const processedData = useMemo(() => {
      if (
         !data ||
         data.length === 0 ||
         !config ||
         options?.autoAggregate === false
      ) {
         return data || [];
      }

      return getChartAggregatedData(config, data);
   }, [data, config, options?.autoAggregate]);

   const aggregated = useMemo(() => {
      if (!config) return false;

      if (config.chartType === "dualAxes") {
         return (
            (config.leftAggregate && config.leftAggregate !== "none") ||
            (config.rightAggregate && config.rightAggregate !== "none")
         );
      }

      return (
         "aggregate" in config &&
         config.aggregate &&
         config.aggregate !== "none"
      );
   }, [config]);

   return {
      data: processedData,
      aggregated: !!aggregated
   };
}
