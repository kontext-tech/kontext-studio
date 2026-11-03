import type { ApiErrorResult } from "@kontext-labs/common";
import type { DataTable, InlineData } from "@kontext-labs/schema";
import { fileKeys } from "../queryKeys";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { FileServiceContract } from "../types/fileService";
import { useFileService } from "./useFileService";

/**
 * Page size used when assembling the full result from the rows endpoint.
 * Matches the API's per-request maximum so a full fetch is a bounded number of
 * requests regardless of result size.
 */
const ROWS_FETCH_PAGE_SIZE = 1000;

/** Hard cap so a runaway result cannot page forever in the browser. */
const ROWS_FETCH_MAX = 100_000;

const isPreviewOnly = (inlineData: InlineData): boolean => {
   const total = inlineData.metadata?.rowCount;
   const loaded = inlineData.table?.rows?.length ?? 0;
   return (
      typeof total === "number" &&
      total > loaded &&
      Boolean(inlineData.metadata?.dataPath)
   );
};

async function fetchAllRows(
   fileService: FileServiceContract,
   fileId: string,
   projectId: string,
   first: InlineData
): Promise<InlineData> {
   const total = Math.min(first.metadata?.rowCount ?? 0, ROWS_FETCH_MAX);
   const columns = first.table?.columns ?? [];
   const rows: unknown[][] = [...(first.table?.rows ?? [])];

   while (rows.length < total) {
      const res = await fileService.getDataTableRows(
         fileId,
         projectId,
         rows.length,
         ROWS_FETCH_PAGE_SIZE
      );
      if (!res.succeed || !res.data?.table?.rows?.length) {
         break;
      }
      rows.push(...res.data.table.rows);
   }

   return {
      ...first,
      table: { columns, rows, rowCount: total }
   };
}

export function useInlineDataFile(
   fileId: string | undefined,
   projectId: string | undefined,
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
) {
   const fileService = useFileService(
      errorHandler
   ) as unknown as FileServiceContract;

   const query = useQuery({
      queryKey: fileKeys.inlineDataFile(fileId, projectId),
      enabled: !!fileId && !!projectId,
      queryFn: async () => {
         if (!fileId || !projectId) {
            return undefined;
         }

         const res = await fileService.getDataTableFile(fileId, projectId);

         if (!res.succeed || !res.data) {
            throw new Error(
               res.error?.messages.join(", ") || "Failed to load data table"
            );
         }

         // Large results store only a bounded preview in the descriptor; pull
         // the full rows from the rows endpoint so the viewer renders everything.
         if (isPreviewOnly(res.data)) {
            return fetchAllRows(fileService, fileId, projectId, res.data);
         }

         return res.data;
      },
      staleTime: 5000
   });

   return useMemo(
      () => ({
         table: query.data?.table as DataTable | undefined,
         inlineData: query.data,
         isLoading: query.isLoading,
         error: query.error
      }),
      [query.data, query.isLoading, query.error]
   );
}
