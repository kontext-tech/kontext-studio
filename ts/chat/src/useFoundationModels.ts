import type { ApiErrorResult } from "@kontext-tech/common";
import { useUserStore } from "@kontext-tech/identity";
import { useService } from "@kontext-tech/app-runtime/hooks";
import { chatKeys } from "./queryKeys";
import { useQuery } from "@tanstack/react-query";
import { ModelCatalogService } from "./ModelCatalogService";

export function useFoundationModels(
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
) {
   const tokens = useUserStore((state) => state.tokens);
   const modelCatalogService = useService(ModelCatalogService, errorHandler);

   return useQuery({
      queryKey: chatKeys.modelCatalog(tokens?.accessToken),
      queryFn: async () => {
         const response = await modelCatalogService.getCatalog();

         if (!response.succeed || !response.data) {
            throw new Error(
               response.error?.title || "Failed to fetch model catalog"
            );
         }

         return response.data;
      },
      enabled: true,
      staleTime: 1000 * 60 * 10
   });
}
