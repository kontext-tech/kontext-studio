import type {
   ChartDocument,
   DataTable,
   QueryResponse
} from "@kontext-tech/schema";

/**
 * Resolves the tabular data to show in the chart's Data tab.
 * Embedded inline data takes priority over externally loaded tables.
 */
export function resolveChartQueryResponse(
   chart?: ChartDocument | null,
   remoteTable?: DataTable
): QueryResponse | null {
   const table = chart?.inlineData?.table ?? remoteTable;

   if (!table) {
      return null;
   }

   return {
      success: true,
      result: table
   };
}
