import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import { ApiResult, HttpApiService } from "@kontext-labs/common";
import type {
   PythonEnvironmentInfo,
   UpdateUserProfileRequest,
   UserWithRolesModel
} from "@kontext-labs/schema";

export class AccountService extends HttpApiService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      customBasePath?: string
   ) {
      super(authContext, errorHandler, customBasePath);
   }

   async updateUserProfile(
      updateUserProfileRequest: UpdateUserProfileRequest
   ): Promise<ApiResult<UserWithRolesModel>> {
      try {
         const response = await this.requestJson<UserWithRolesModel>(
            "/account/profile",
            {
               method: "POST",
               headers: { "Content-Type": "application/json" },
               body: JSON.stringify(updateUserProfileRequest)
            }
         );
         return ApiResult.success(response);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getPythonEnvironment(): Promise<ApiResult<PythonEnvironmentInfo>> {
      try {
         const response = await this.requestJson<PythonEnvironmentInfo>(
            "/account/python-environment"
         );
         return ApiResult.success(response);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async preparePythonEnvironment(): Promise<ApiResult<PythonEnvironmentInfo>> {
      try {
         const response = await this.requestJson<PythonEnvironmentInfo>(
            "/account/python-environment/prepare",
            {
               method: "POST"
            }
         );
         return ApiResult.success(response);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
