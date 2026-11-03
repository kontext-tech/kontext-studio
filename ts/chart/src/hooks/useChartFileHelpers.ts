import {
   useFileWorkflow,
   useJsonFileHelpers,
   type UseFileWorkflowReturn
} from "@kontext-labs/file";
import type { ChartDocument, FileModel } from "@kontext-labs/schema";
import { useCallback } from "react";
import { CHART_FILE_EXTENSION } from "../constants";

type ChartFileWorkflow = Pick<
   UseFileWorkflowReturn,
   "fetchFile" | "getFileBlob" | "updateFile"
>;

export interface UseChartFileHelpersReturn {
   loadChart: (
      fileId: string,
      options?: {
         artifactContent?: string | ChartDocument;
         fallbackTitle?: string;
      }
   ) => Promise<{
      chart: ChartDocument | null;
      file: FileModel | null;
      error: string | null;
   }>;
   saveChart: (
      fileId: string,
      chart: ChartDocument,
      name?: string
   ) => Promise<{
      success: boolean;
      file?: FileModel;
   }>;
}

export const useChartFileHelpers = (
   fileWorkflow: ChartFileWorkflow
): UseChartFileHelpersReturn => {
   const { loadJsonFile, saveJsonFile } = useJsonFileHelpers(fileWorkflow);

   const loadChart = useCallback(
      async (
         fileId: string,
         options?: {
            artifactContent?: string | ChartDocument;
            fallbackTitle?: string;
         }
      ) => {
         const { document, file, error } = await loadJsonFile<ChartDocument>(
            fileId,
            {
               artifactContent: options?.artifactContent,
               parseDocument: (parsed: unknown) =>
                  ((parsed as Record<string, unknown>).chart ??
                     parsed) as ChartDocument,
               parseErrorMessage: "Failed to parse chart content",
               loadErrorMessage: "Failed to load chart"
            }
         );

         return { chart: document, file, error };
      },
      [loadJsonFile]
   );

   const saveChart = useCallback(
      async (fileId: string, chart: ChartDocument, name?: string) => {
         return saveJsonFile(fileId, chart, {
            documentName: name,
            fallbackName: chart.name || "Untitled Chart",
            extension: CHART_FILE_EXTENSION
         });
      },
      [saveJsonFile]
   );

   return {
      loadChart,
      saveChart
   };
};

export const useChartFileWorkflow = (
   options: Parameters<typeof useFileWorkflow>[0] = {}
) => {
   const fileWorkflow = useFileWorkflow(options);
   const chartHelpers = useChartFileHelpers(fileWorkflow);

   return {
      ...fileWorkflow,
      ...chartHelpers
   };
};
