import type { ApiErrorResult } from "@kontext-labs/common";
import { useDataService } from "@kontext-labs/app-runtime/hooks";
import {
   JobRunStatus,
   type JobRunLogModel,
   type JobRunModel
} from "@kontext-labs/schema";
import { useCallback, useEffect, useRef, useState } from "react";
import { DataJobRunService } from "./DataJobRunService";
import { ExecutionRunService } from "./ExecutionRunService";

export interface LoadJobRunsParams {
   status?: JobRunStatus;
   pageIndex?: number;
   pageSize?: number;
}

export function useDataJobRuns(
   projectId: string,
   errorHandler?: (error: ApiErrorResult) => Promise<void>,
   jobId?: string
) {
   const jobRunService = useRef(
      useDataService(DataJobRunService, errorHandler)
   );
   const executionRunService = useRef(
      useDataService(ExecutionRunService, errorHandler)
   );

   const [jobRuns, setJobRuns] = useState<JobRunModel[]>([]);
   const [totalCount, setTotalCount] = useState(0);
   const [loading, setLoading] = useState(false);
   const [error, setError] = useState<string | null>(null);
   const [pageIndex, setPageIndex] = useState(1);
   const [pageSize, setPageSize] = useState(10);
   const [status, setStatus] = useState<JobRunStatus | undefined>();
   const requestVersion = useRef(0);

   const loadJobRuns = useCallback(
      async (params?: LoadJobRunsParams) => {
         if (!projectId) return;

         const fetchParams: LoadJobRunsParams = {
            pageIndex: params?.pageIndex ?? pageIndex,
            pageSize: params?.pageSize ?? pageSize,
            status: params?.status ?? status
         };

         const version = ++requestVersion.current;
         setLoading(true);
         setError(null);
         try {
            const result = jobId
               ? await jobRunService.current.getJobRunsByJob(
                    projectId,
                    jobId,
                    fetchParams
                 )
               : await jobRunService.current.getJobRuns(projectId, fetchParams);

            if (version === requestVersion.current) {
               if (result.succeed && result.data) {
                  setJobRuns(result.data.items || []);
                  setTotalCount(result.data.totalCount || 0);
                  setError(null);
               } else {
                  setJobRuns([]);
                  setTotalCount(0);
                  setError(result.error?.title || "Failed to load job runs");
               }
            }
         } catch {
            if (version === requestVersion.current) {
               setError("An unexpected error occurred");
            }
         } finally {
            if (version === requestVersion.current) {
               setLoading(false);
            }
         }
      },
      [jobId, pageIndex, pageSize, projectId, status]
   );

   const getJobRun = useCallback(
      async (runId: string): Promise<JobRunModel | null> => {
         if (!projectId) return null;

         try {
            const result = await jobRunService.current.getJobRun(
               projectId,
               runId
            );
            if (result.succeed && result.data) {
               return result.data;
            }
            return null;
         } catch {
            return null;
         }
      },
      [projectId]
   );

   const getJobRunLogs = useCallback(
      async (runId: string, limit?: number): Promise<JobRunLogModel[]> => {
         if (!projectId) return [];

         try {
            const result = await jobRunService.current.getJobRunLogs(
               projectId,
               runId,
               limit
            );
            if (result.succeed && result.data) {
               return result.data;
            }
            return [];
         } catch {
            return [];
         }
      },
      [projectId]
   );

   const resetJobRuns = useCallback(
      async (jobRunIds: string[], reason: string) => {
         if (!projectId) return null;

         try {
            const result = await jobRunService.current.resetJobRuns({
               projectId,
               jobRunIds,
               reason
            });
            if (result.succeed) {
               await loadJobRuns();
               return result.data || { message: "Job runs reset" };
            }
            return null;
         } catch {
            return null;
         }
      },
      [loadJobRuns, projectId]
   );

   const cancelJobRun = useCallback(
      async (runId: string, reason?: string): Promise<boolean> => {
         if (!projectId) return false;

         try {
            const result = await executionRunService.current.cancelRun(
               runId,
               projectId,
               reason
            );
            if (result.succeed) {
               await loadJobRuns();
               return true;
            }
            return false;
         } catch {
            return false;
         }
      },
      [loadJobRuns, projectId]
   );

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         void loadJobRuns();
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [loadJobRuns]);

   return {
      jobRuns,
      totalCount,
      loading,
      error,
      pageIndex,
      pageSize,
      status,
      setPageIndex,
      setPageSize,
      setStatus,
      loadJobRuns,
      getJobRun,
      getJobRunLogs,
      resetJobRuns,
      cancelJobRun
   };
}
