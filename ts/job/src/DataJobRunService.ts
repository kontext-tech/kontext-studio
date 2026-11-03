import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import { ApiResult, DataApiBaseService } from "@kontext-labs/common";
import type {
   JobResetResponse,
   JobRunLogModel,
   JobRunModel,
   PaginatedListOfJobRunModel
} from "@kontext-labs/schema";

/**
 * Service for managing project-scoped job runs via the Data API.
 * This service handles Python job runs stored in project-scoped SQLite databases.
 */
export class DataJobRunService extends DataApiBaseService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async getJobRuns(
      projectId: string,
      params: {
         jobId?: string;
         status?: string;
         pageIndex?: number;
         pageSize?: number;
      } = {}
   ): Promise<ApiResult<PaginatedListOfJobRunModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/job-runs", {
               params: {
                  query: {
                     projectId,
                     pageIndex: params.pageIndex,
                     pageSize: params.pageSize,
                     jobId: params.jobId,
                     status: params.status
                  }
               }
            })
         );
         return ApiResult.success(result as PaginatedListOfJobRunModel);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getJobRunsByJob(
      projectId: string,
      jobId: string,
      params: {
         status?: string;
         pageIndex?: number;
         pageSize?: number;
      } = {}
   ): Promise<ApiResult<PaginatedListOfJobRunModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/job-runs/job/{jobId}", {
               params: {
                  path: { jobId },
                  query: {
                     projectId,
                     pageIndex: params.pageIndex,
                     pageSize: params.pageSize,
                     status: params.status
                  }
               }
            })
         );
         return ApiResult.success(result as PaginatedListOfJobRunModel);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getJobRun(
      projectId: string,
      runId: string
   ): Promise<ApiResult<JobRunModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/job-runs/{runId}", {
               params: {
                  path: { runId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getJobRunLogs(
      projectId: string,
      runId: string,
      limit?: number
   ): Promise<ApiResult<JobRunLogModel[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/job-runs/{runId}/logs", {
               params: {
                  path: { runId },
                  query: { projectId, limit }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async resetJobRuns(params: {
      projectId: string;
      jobRunIds: string[];
      reason: string;
   }): Promise<ApiResult<JobResetResponse>> {
      try {
         const result = await this.request(
            this.apiClient.POST("/job-runs/reset", {
               params: { query: { projectId: params.projectId } },
               body: {
                  jobRunIds: params.jobRunIds,
                  reason: params.reason
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
