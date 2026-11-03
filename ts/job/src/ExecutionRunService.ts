import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import { ApiResult, DataApiBaseService } from "@kontext-labs/common";
import type { ExecutionRunModel } from "@kontext-labs/schema";

/**
 * Service for the unified execution-run surface (`/runs`).
 *
 * Job runs and execution runs share an id, so `cancelRun` accepts a job-run id
 * directly. Kept separate from {@link DataJobRunService} because it is bound to
 * the `/runs` endpoints.
 */
export class ExecutionRunService extends DataApiBaseService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async cancelRun(
      runId: string,
      projectId: string,
      reason?: string
   ): Promise<ApiResult<ExecutionRunModel>> {
      try {
         const result = await this.request(
            this.apiClient.POST("/runs/{runId}/cancel", {
               params: {
                  path: { runId },
                  query: { projectId }
               },
               body: reason ? { reason } : undefined
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
