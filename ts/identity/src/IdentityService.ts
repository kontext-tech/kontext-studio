import type {
   ApiAuthContext,
   ApiErrorResult
} from "@kontext-labs/common/types";
import { ApiResult } from "@kontext-labs/common/types";
import { HttpApiService } from "@kontext-labs/common/services";
import { API_BASE_PATH } from "@kontext-labs/common/utils";
import { HostClient } from "@kontext-labs/host-api";
import type { UserWithRolesModel } from "@kontext-labs/schema";

export class IdentityService extends HttpApiService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      customBasePath?: string
   ) {
      super(authContext, errorHandler, customBasePath);
   }

   async getCurrentUser(): Promise<ApiResult<UserWithRolesModel>> {
      try {
         const response = await this.createHostClient().me();
         if (!response.user) {
            return ApiResult.failure({
               title: "Not authenticated",
               status: 401,
               messages: ["Host did not return an authenticated user."],
               isAuthError: true
            });
         }
         return ApiResult.success(response.user);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   getUserAvatarUrl(userId: string, version: string): string {
      return `${API_BASE_PATH}/account/avatar/${userId}?v=${version}`;
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
