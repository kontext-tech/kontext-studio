import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import { ApiResult, DataApiBaseService } from "@kontext-labs/common";
import type { ProjectStatsModel } from "@kontext-labs/schema";

export class DataProjectService extends DataApiBaseService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async getProjectStats(
      projectId: string
   ): Promise<ApiResult<ProjectStatsModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/project/{projectId}/stats", {
               params: { path: { projectId } }
            })
         );
         return ApiResult.success(result as ProjectStatsModel);
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }
}
