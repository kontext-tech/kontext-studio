import { fileKeys } from "@kontext-tech/file";
import type { FileServiceContract } from "@kontext-tech/file";
import type { DataRef, DataTable } from "@kontext-tech/schema";
import { useQuery } from "@tanstack/react-query";

/**
 * App-level hook to load external data tables for charts.
 * This is intentionally kept in the app layer (not in @kontext-tech/chart) because
 * it depends on host-specific services (FileServiceContract) and React Query.
 *
 * @param dataRef - Reference to external data (from ChartDocument)
 * @param fileService - File service for loading data from storage
 * @param projectId - Project ID for resource access
 * @returns Query results with table, loading state, and error
 */
export function useChartDataRef(
   dataRef: DataRef | undefined,
   fileService: FileServiceContract | undefined,
   projectId: string | undefined
): {
   table: DataTable | undefined;
   isLoading: boolean;
   error?: Error | null;
} {
   const dataId = dataRef?.dataId;

   const query = useQuery({
      queryKey: fileKeys.chartDataRef(dataId, projectId),
      enabled: !!dataId && !!projectId && !!fileService,
      queryFn: async () => {
         if (!dataId || !projectId || !fileService) return undefined;

         const res = await fileService.getDataTableFile(dataId, projectId);

         if (res.succeed && res.data) {
            return res.data;
         }

         const error = new Error(
            res.error?.messages.join(", ") ||
               "Failed to load chart data table from storage"
         );
         throw error;
      },
      retry: 3,
      retryDelay: (attemptIndex: number) =>
         Math.min(1000 * 2 ** attemptIndex, 3000),
      staleTime: 5000
   });

   return {
      table: query.data?.table as DataTable | undefined,
      isLoading: query.isLoading,
      error: query.error
   };
}
