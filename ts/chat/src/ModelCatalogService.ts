import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, HttpApiService } from "@kontext-tech/common";
import type { ModelCatalogEntry } from "@kontext-tech/schema";

export class ModelCatalogService extends HttpApiService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      customBasePath?: string
   ) {
      super(authContext, errorHandler, customBasePath);
   }

   async getCatalog(): Promise<ApiResult<ModelCatalogEntry[]>> {
      try {
         const result =
            await this.requestJson<ModelCatalogEntry[]>("/models/catalog");
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
