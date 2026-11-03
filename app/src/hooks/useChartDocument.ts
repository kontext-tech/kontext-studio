import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useChartDataRef } from "@/hooks/useChartDataRef";
import { useChartFileHelpers } from "@kontext-labs/chart";
import { useFileService, useFileWorkflow } from "@kontext-labs/file";
import type { ChartDocument } from "@kontext-labs/schema";
import { useCallback, useEffect, useRef, useState } from "react";

export interface UseChartDocumentOptions {
   fileId: string;
   projectId: string;
   fallbackTitle?: string;
   onTitleChange?: (title: string) => void;
   /** Bump to force a full chart reload (e.g. agent chat updates). */
   refreshToken?: number;
   /**
    * When true, a reload whose serialized document is identical to the last
    * applied one does not re-render (stream-adjacent refresh-token bumps
    * otherwise blink the chart).
    */
   suppressSameContentReload?: boolean;
}

/**
 * Shared chart-document lifecycle for both the file-detail page and the chat
 * artifact viewer: load/save/save-error state plus remote data-table wiring.
 */
export function useChartDocument({
   fileId,
   projectId,
   fallbackTitle,
   onTitleChange,
   refreshToken = 0,
   suppressSameContentReload = false
}: UseChartDocumentOptions) {
   const apiErrorHandler = useApiErrorHandler();
   const [chart, setChart] = useState<ChartDocument | null>(null);
   const [isLoading, setIsLoading] = useState(true);
   const [isSaving, setIsSaving] = useState(false);
   const [error, setError] = useState<string | null>(null);

   const fileService = useFileService(apiErrorHandler);

   const fileWorkflow = useFileWorkflow({ projectId });
   const { loadChart, saveChart } = useChartFileHelpers(fileWorkflow);

   // Signature of the last applied document (see suppressSameContentReload).
   const loadedChartSignatureRef = useRef<string | null>(null);

   // Fetch remote data if the chart has an external data reference
   const dataRef = chart?.dataRef;
   const {
      table: remoteTable,
      isLoading: isRemoteDataLoading,
      error: remoteDataError
   } = useChartDataRef(dataRef, fileService, projectId);

   // Stable ref for title change callback to avoid effect re-triggers
   const onTitleChangeRef = useRef(onTitleChange);
   useEffect(() => {
      onTitleChangeRef.current = onTitleChange;
   }, [onTitleChange]);

   // Load chart document
   useEffect(() => {
      let mounted = true;
      const doLoad = async () => {
         if (!fileId) {
            if (!mounted) return;
            setError("Missing artifact information");
            setIsLoading(false);
            return;
         }

         try {
            setIsLoading(true);
            setError(null);

            const { chart: loadedChart, error: loadError } = await loadChart(
               fileId,
               fallbackTitle ? { fallbackTitle } : undefined
            );

            if (!mounted) return;

            if (loadError) {
               setError(loadError);
            } else if (loadedChart) {
               const signature = JSON.stringify(loadedChart);
               if (
                  !suppressSameContentReload ||
                  loadedChartSignatureRef.current !== signature
               ) {
                  loadedChartSignatureRef.current = signature;
                  setChart(loadedChart);
               }
               setError(null);
            } else {
               setError("Chart document not found");
            }
         } catch (err) {
            console.error("Error loading chart:", err);
            if (mounted) setError("An unexpected error occurred while loading");
         } finally {
            if (mounted) setIsLoading(false);
         }
      };

      doLoad();

      return () => {
         mounted = false;
      };
   }, [
      fileId,
      refreshToken,
      projectId,
      loadChart,
      fallbackTitle,
      suppressSameContentReload
   ]);

   // Update tab title when chart loads or changes
   const currentTitle = chart?.name || "Chart";
   useEffect(() => {
      if (chart && onTitleChangeRef.current) {
         onTitleChangeRef.current(currentTitle);
      }
   }, [chart, currentTitle]);

   const handleSave = useCallback(
      async (updatedChart: ChartDocument): Promise<boolean> => {
         if (!fileId) {
            return false;
         }

         try {
            setIsSaving(true);

            const result = await saveChart(
               fileId,
               updatedChart,
               updatedChart.name
            );

            if (result.success) {
               if (suppressSameContentReload) {
                  loadedChartSignatureRef.current =
                     JSON.stringify(updatedChart);
               }
               setChart(updatedChart);
               return true;
            }
            setError("Failed to save chart changes to backend.");
            return false;
         } catch (err) {
            console.error("Error saving chart:", err);
            setError("An error occurred while saving the chart.");
            return false;
         } finally {
            setIsSaving(false);
         }
      },
      [fileId, saveChart, suppressSameContentReload]
   );

   return {
      chart,
      setChart,
      isLoading,
      isSaving,
      error,
      setError,
      setIsLoading,
      remoteTable,
      isRemoteDataLoading,
      remoteDataError,
      handleSave,
      fileWorkflow
   };
}
