import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, HttpApiService } from "@kontext-tech/common";
import { HostClient } from "@kontext-tech/host-api";
import type { ProjectRole } from "@kontext-tech/auth";
import type {
   CreateProjectRequest,
   FoundationModel,
   PaginatedListOfProjectModel,
   PaginatedListOfUserWithProjectRolesModel,
   ProjectModel,
   UpdateProjectRequest
} from "@kontext-tech/schema";

export class ProjectService extends HttpApiService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      customBasePath?: string
   ) {
      super(authContext, errorHandler, customBasePath);
   }

   async getUserProjects(
      userId: string,
      filter?: string
   ): Promise<ApiResult<ProjectModel[]>> {
      void userId;
      try {
         const result = await this.createHostClient().getProjects({ filter });
         return ApiResult.success(result.items || []);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getProject(projectId: string): Promise<ApiResult<ProjectModel>> {
      try {
         const result = await this.requestJson<ProjectModel>(
            `/project/${encodeURIComponent(projectId)}`
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async createProject(
      project: CreateProjectRequest
   ): Promise<ApiResult<ProjectModel>> {
      try {
         const result = await this.requestJson<ProjectModel>("/project", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(project)
         });
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async updateProject(
      projectId: string,
      project: UpdateProjectRequest
   ): Promise<ApiResult<void>> {
      try {
         await this.requestJson<ProjectModel>(
            `/project/${encodeURIComponent(projectId)}`,
            {
               method: "PUT",
               headers: { "Content-Type": "application/json" },
               body: JSON.stringify(project)
            }
         );
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getFilteredProjects(
      filter?: string,
      pageIndex: number = 1,
      pageSize: number = 10,
      roleFilters?: string[],
      includePublic: boolean = true,
      includePrivate: boolean = true,
      includeDeleted: boolean = false
   ): Promise<ApiResult<PaginatedListOfProjectModel>> {
      try {
         const result = await this.createHostClient().getProjects({
            filter,
            roleFilters,
            includePublic,
            includePrivate,
            includeDeleted,
            pageIndex,
            pageSize
         });
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getProjectByCode(
      projectCode: string
   ): Promise<ApiResult<ProjectModel>> {
      try {
         const result =
            await this.createHostClient().getProjectByCode(projectCode);
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getProjectUsers(
      projectId: string,
      filter?: string,
      pageIndex: number = 1,
      pageSize: number = 20
   ): Promise<ApiResult<PaginatedListOfUserWithProjectRolesModel>> {
      // There is no project-membership endpoint yet. Returning an empty
      // successful page made the UI claim the project has no members, so fail
      // explicitly until the backend contract exists.
      void projectId;
      void filter;
      void pageIndex;
      void pageSize;
      return ApiResult.failure({
         title: "Not implemented",
         status: 501,
         messages: ["Project membership is not available in this deployment."]
      });
   }

   async updateUserProjectRoles(
      projectId: string,
      userId: string,
      roles: ProjectRole[] | null
   ): Promise<ApiResult<void>> {
      void projectId;
      void userId;
      void roles;
      return ApiResult.failure({
         title: "Not implemented",
         status: 501,
         messages: ["Project membership is not available in this deployment."]
      });
   }

   async deleteProject(projectId: string): Promise<ApiResult<void>> {
      try {
         await this.requestJson<void>(
            `/project/${encodeURIComponent(projectId)}`,
            {
               method: "DELETE"
            }
         );
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getFoundationModels(): Promise<ApiResult<FoundationModel[]>> {
      try {
         const result = await this.requestJson<FoundationModel[]>(
            this.buildPath("/project/foundation-models")
         );
         return ApiResult.success(result);
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
