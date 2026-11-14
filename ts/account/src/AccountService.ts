import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, HttpApiService } from "@kontext-tech/common";
import type {
   PythonEnvironmentInfo,
   UpdateUserProfileRequest,
   UserWithRolesModel
} from "@kontext-tech/schema";

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
      return this.wrap(async () => {
         const response = await this.requestJson<UserWithRolesModel>(
            "/account/profile",
            {
               method: "POST",
               headers: { "Content-Type": "application/json" },
               body: JSON.stringify(updateUserProfileRequest)
            }
         );
         return response;
      });
   }

   async getPythonEnvironment(): Promise<ApiResult<PythonEnvironmentInfo>> {
      return this.wrap(async () => {
         const response = await this.requestJson<PythonEnvironmentInfo>(
            "/account/python-environment"
         );
         return response;
      });
   }

   async preparePythonEnvironment(): Promise<ApiResult<PythonEnvironmentInfo>> {
      return this.wrap(async () => {
         const response = await this.requestJson<PythonEnvironmentInfo>(
            "/account/python-environment/prepare",
            {
               method: "POST"
            }
         );
         return response;
      });
   }
}
