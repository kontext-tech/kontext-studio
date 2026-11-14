import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, HttpApiService } from "@kontext-tech/common";
import type {
   ModelConnection,
   ModelProviderDefinition
} from "@kontext-tech/schema";

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
      return this.wrap(async () => {
         const result =
            await this.requestJson<ModelConnection[]>("/model-connections");
         return result;
      });
   }

   async getModelProviderDefinitions(): Promise<
      ApiResult<ModelProviderDefinition[]>
   > {
      return this.wrap(async () => {
         const result = await this.requestJson<ModelProviderDefinition[]>(
            "/model-connections/providers"
         );
         return result;
      });
   }

   async createModelProvider(
      provider: ModelConnection
   ): Promise<ApiResult<ModelConnection>> {
      return this.wrap(async () => {
         const result = await this.requestJson<ModelConnection>(
            "/model-connections",
            {
               method: "POST",
               headers: { "Content-Type": "application/json" },
               body: JSON.stringify(provider)
            }
         );
         return result;
      });
   }

   async updateModelProvider(
      id: string,
      provider: ModelConnection
   ): Promise<ApiResult<ModelConnection>> {
      return this.wrap(async () => {
         const result = await this.requestJson<ModelConnection>(
            `/model-connections/${id}`,
            {
               method: "PUT",
               headers: { "Content-Type": "application/json" },
               body: JSON.stringify(provider)
            }
         );
         return result;
      });
   }

   async deleteModelProvider(id: string): Promise<ApiResult<void>> {
      return this.wrap(async () => {
         await this.requestJson<void>(`/model-connections/${id}`, {
            method: "DELETE"
         });
         return undefined;
      });
   }
}
