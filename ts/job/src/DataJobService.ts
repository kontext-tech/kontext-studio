import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, DataApiBaseService } from "@kontext-tech/common";
import type {
   CreateJobRequest,
   ExecuteJobNowRequest,
   JobModel,
   JobRunModel,
   PaginatedListOfJobModel,
   UnifiedJobTypeModel,
   UpdateJobRequest
} from "@kontext-tech/schema";

/**
 * Service for managing project-scoped jobs via the Data API.
 * This service handles Python jobs stored in project-scoped SQLite databases.
 */
export class DataJobService extends DataApiBaseService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async getJobTypes(
      projectId: string
   ): Promise<ApiResult<UnifiedJobTypeModel[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/jobs/types", {
               params: { query: { projectId } }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getJobType(
      projectId: string,
      jobType: string
   ): Promise<ApiResult<UnifiedJobTypeModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/jobs/types/{jobType}", {
               params: {
                  path: { jobType },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getJobs(
      projectId: string,
      params: {
         pageIndex?: number;
         pageSize?: number;
         filterString?: string;
         isEnabled?: boolean;
      } = {}
   ): Promise<ApiResult<PaginatedListOfJobModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/jobs", {
               params: {
                  query: {
                     projectId,
                     pageIndex: params.pageIndex,
                     pageSize: params.pageSize,
                     filterString: params.filterString,
                     isEnabled: params.isEnabled
                  }
               }
            })
         );
         return ApiResult.success(result as PaginatedListOfJobModel);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getJob(
      projectId: string,
      jobId: string
   ): Promise<ApiResult<JobModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/jobs/{jobId}", {
               params: {
                  path: { jobId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async createJob(
      projectId: string,
      job: CreateJobRequest
   ): Promise<ApiResult<JobModel>> {
      try {
         const result = await this.request(
            this.apiClient.POST("/jobs", {
               params: { query: { projectId } },
               body: job
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async updateJob(
      projectId: string,
      jobId: string,
      job: UpdateJobRequest
   ): Promise<ApiResult<JobModel>> {
      try {
         const result = await this.request(
            this.apiClient.PUT("/jobs/{jobId}", {
               params: {
                  path: { jobId },
                  query: { projectId }
               },
               body: job
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async deleteJob(projectId: string, jobId: string): Promise<ApiResult<void>> {
      try {
         await this.request(
            this.apiClient.DELETE("/jobs/{jobId}", {
               params: {
                  path: { jobId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async scheduleJob(
      projectId: string,
      jobId: string,
      request?: ExecuteJobNowRequest
   ): Promise<ApiResult<JobRunModel>> {
      try {
         const result = await this.request(
            this.apiClient.POST("/jobs/{jobId}/schedule", {
               params: {
                  path: { jobId },
                  query: { projectId }
               },
               body: request
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
