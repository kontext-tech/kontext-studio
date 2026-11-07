import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { AccountService } from "@kontext-tech/account";
import { useService } from "@kontext-tech/app-runtime/hooks";
import type { PythonEnvironmentInfo } from "@kontext-tech/schema";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const PYTHON_ENVIRONMENT_QUERY_KEY = ["python-environment"] as const;

/**
 * Reads the local Python runtime details and exposes an explicit "prepare"
 * mutation. React Query owns the cached server state so the page no longer
 * hand-rolls loading/error/refresh state.
 */
export function usePythonEnvironment(options?: { enabled?: boolean }) {
   const apiErrorHandler = useApiErrorHandler();
   const accountService = useService(AccountService, apiErrorHandler);
   const queryClient = useQueryClient();

   const query = useQuery<PythonEnvironmentInfo>({
      queryKey: PYTHON_ENVIRONMENT_QUERY_KEY,
      enabled: options?.enabled ?? true,
      queryFn: async () => {
         const response = await accountService.getPythonEnvironment();

         if (!response.succeed || !response.data) {
            throw new Error(
               response.error?.messages?.[0] ??
                  "Failed to load Python environment details."
            );
         }

         return response.data;
      },
      staleTime: 30_000
   });

   const prepare = useMutation({
      mutationFn: async () => {
         const response = await accountService.preparePythonEnvironment();

         if (!response.succeed || !response.data) {
            throw new Error(
               response.error?.messages?.[0] ??
                  "Failed to prepare Python environment."
            );
         }

         return response.data;
      },
      onSuccess: (data) => {
         queryClient.setQueryData(PYTHON_ENVIRONMENT_QUERY_KEY, data);
      }
   });

   return {
      environment: query.data ?? null,
      isLoading: query.isLoading,
      errorMessage: query.error instanceof Error ? query.error.message : null,
      isPreparing: prepare.isPending,
      refresh: () => query.refetch(),
      prepare: prepare.mutateAsync
   };
}
