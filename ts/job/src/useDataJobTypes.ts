import type { ApiErrorResult } from "@kontext-tech/common";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import type {
   UnifiedJobParameterModel,
   UnifiedJobTypeModel
} from "@kontext-tech/schema";
import { useCallback, useEffect, useRef, useState } from "react";
import { DataJobService } from "./DataJobService";

export function useDataJobTypes(
   projectId: string,
   errorHandler?: (error: ApiErrorResult) => Promise<void>
) {
   const jobService = useRef(useDataService(DataJobService, errorHandler));

   const [jobTypes, setJobTypes] = useState<UnifiedJobTypeModel[]>([]);
   const [loading, setLoading] = useState(false);
   const [error, setError] = useState<string | null>(null);

   const loadJobTypes = useCallback(async () => {
      if (!projectId) return;

      setLoading(true);
      setError(null);
      try {
         const result = await jobService.current.getJobTypes(projectId);
         if (result.succeed && result.data) {
            setJobTypes(result.data);
         } else {
            setError(result.error?.title || "Failed to load job types");
         }
      } catch {
         setError("An unexpected error occurred");
      } finally {
         setLoading(false);
      }
   }, [projectId]);

   const getJobTypeDetails = useCallback(
      async (jobType: string): Promise<UnifiedJobTypeModel | null> => {
         if (!projectId) return null;

         try {
            const result = await jobService.current.getJobType(
               projectId,
               jobType
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

   const fetchJobParametersByType = useCallback(
      async (jobType: string): Promise<UnifiedJobParameterModel[]> => {
         try {
            const jobRegistration = await getJobTypeDetails(jobType);
            return jobRegistration?.parameters || [];
         } catch (error) {
            console.error(
               `Failed to fetch parameters for job type ${jobType}:`,
               error
            );
            return [];
         }
      },
      [getJobTypeDetails]
   );

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         void loadJobTypes();
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [loadJobTypes]);

   return {
      jobTypes,
      loading,
      error,
      loadJobTypes,
      getJobTypeDetails,
      fetchJobParametersByType
   };
}
