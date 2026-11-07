import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useFileService } from "@kontext-tech/file";
import type { FileModel } from "@kontext-tech/schema";
import { fileKeys } from "@kontext-tech/file";
import { useQuery } from "@tanstack/react-query";
import type { ApiErrorResult } from "@kontext-tech/common";

/**
 * Loads a single file's metadata through React Query so detail screens get
 * request deduplication, caching, and consistent error handling instead of
 * hand-rolled `useState` + `useEffect` fetching.
 */
export function useFileResource(
   fileId: string | undefined,
   projectId: string | undefined,
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
) {
   const fallbackErrorHandler = useApiErrorHandler();
   const fileService = useFileService(errorHandler ?? fallbackErrorHandler);

   return useQuery<FileModel | null>({
      queryKey: fileKeys.fileResource(fileId, projectId),
      enabled: !!fileId && !!projectId,
      queryFn: async () => {
         if (!fileId || !projectId) {
            return null;
         }

         const result = await fileService.getFileById(fileId, projectId);

         if (result.succeed) {
            return result.data ?? null;
         }

         throw new Error(
            result.error?.messages?.join(", ") || "Failed to load file"
         );
      },
      staleTime: 30_000
   });
}
