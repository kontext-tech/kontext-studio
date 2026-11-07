import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, HttpApiService } from "@kontext-tech/common";
import { HostClient } from "@kontext-tech/host-api";
import type { CultureInfoModel } from "@kontext-tech/schema";

export interface SiteCultureServiceContract {
   getCultures(): Promise<ApiResult<CultureInfoModel[]>>;
}

export class SiteCultureService
   extends HttpApiService
   implements SiteCultureServiceContract
{
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      customBasePath?: string
   ) {
      super(authContext, errorHandler, customBasePath);
   }

   async getCultures(): Promise<ApiResult<CultureInfoModel[]>> {
      try {
         const cultures = await this.createHostClient().getCulture();
         return ApiResult.success(cultures);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   private createHostClient(): HostClient {
      const config = this.getApiClientConfiguration();
      return new HostClient({
         basePath: config.basePath,
         accessToken: this.currentAuthContext.accessToken,
         credentials: config.credentials as RequestCredentials,
         headers: config.headers
      });
   }
}
