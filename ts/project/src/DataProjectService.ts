import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, DataApiBaseService } from "@kontext-tech/common";
import type { ProjectStatsModel } from "@kontext-tech/schema";

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
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/project/{projectId}/stats", {
               params: { path: { projectId } }
            })
         );
         return result as ProjectStatsModel;
      });
   }
}
