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
      return this.wrap(async () => {
         const cultures = await this.createHostClient().getCulture();
         return cultures;
      });
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
