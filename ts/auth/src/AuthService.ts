import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import { ApiResult, HttpApiService } from "@kontext-labs/common";
import { HostClient, type HostAuthBootstrap } from "@kontext-labs/host-api";
import type { AccessTokenResponse, LoginRequest } from "@kontext-labs/schema";

export class AuthService extends HttpApiService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      customBasePath?: string
   ) {
      super(authContext, errorHandler, customBasePath);
   }

   async login(
      loginRequest: LoginRequest,
      captchaCode?: string,
      captchaHash?: string
   ): Promise<ApiResult<AccessTokenResponse | null>> {
      void loginRequest;
      void captchaCode;
      void captchaHash;

      try {
         const bootstrap = await this.createHostClient().bootstrap();
         if (!bootstrap.accessToken) {
            return ApiResult.failure({
               title: "Login failed",
               status: 400,
               messages: ["Host did not return an access token."]
            });
         }
         return ApiResult.success(bootstrap.accessToken);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async bootstrap(): Promise<ApiResult<AccessTokenResponse | null>> {
      try {
         const bootstrap = await this.createHostClient().bootstrap();
         if (!bootstrap.accessToken) {
            return ApiResult.success(null);
         }
         return ApiResult.success(bootstrap.accessToken);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getHostBootstrap(): Promise<ApiResult<HostAuthBootstrap>> {
      try {
         return ApiResult.success(await this.createHostClient().bootstrap());
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async refreshToken(
      refreshToken: string,
      errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
   ): Promise<ApiResult<AccessTokenResponse>> {
      void refreshToken;
      try {
         const bootstrap = await this.createHostClient().refresh();
         if (!bootstrap.accessToken) {
            return ApiResult.failure({
               title: "Refresh failed",
               status: 401,
               messages: ["Host did not return a refreshed access token."],
               isAuthError: true
            });
         }
         return ApiResult.success(bootstrap.accessToken);
      } catch (error) {
         const errorResult = await this.parseApiError(error);
         if (errorHandler) {
            await errorHandler(errorResult);
         } else {
            await this.errorHandler?.(errorResult);
         }
         return ApiResult.failure(errorResult);
      }
   }

   async logout(): Promise<ApiResult<boolean>> {
      try {
         await this.createHostClient().logout();
         return ApiResult.success(true);
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
