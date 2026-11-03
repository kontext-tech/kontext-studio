import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import { ApiResult, HttpApiService } from "@kontext-labs/common";
import type {
   ModelConnection,
   ModelProviderDefinition
} from "@kontext-labs/schema";

/** Service for managing executable model providers. */
export class ModelProviderService extends HttpApiService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      customBasePath?: string
   ) {
      super(authContext, errorHandler, customBasePath);
   }

   async getModelProviders(): Promise<ApiResult<ModelConnection[]>> {
      try {
         const result =
            await this.requestJson<ModelConnection[]>("/model-connections");
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getModelProviderDefinitions(): Promise<
      ApiResult<ModelProviderDefinition[]>
   > {
      try {
         const result = await this.requestJson<ModelProviderDefinition[]>(
            "/model-connections/providers"
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async createModelProvider(
      provider: ModelConnection
   ): Promise<ApiResult<ModelConnection>> {
      try {
         const result = await this.requestJson<ModelConnection>(
            "/model-connections",
            {
               method: "POST",
               headers: { "Content-Type": "application/json" },
               body: JSON.stringify(provider)
            }
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async updateModelProvider(
      id: string,
      provider: ModelConnection
   ): Promise<ApiResult<ModelConnection>> {
      try {
         const result = await this.requestJson<ModelConnection>(
            `/model-connections/${id}`,
            {
               method: "PUT",
               headers: { "Content-Type": "application/json" },
               body: JSON.stringify(provider)
            }
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async deleteModelProvider(id: string): Promise<ApiResult<void>> {
      try {
         await this.requestJson<void>(`/model-connections/${id}`, {
            method: "DELETE"
         });
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
