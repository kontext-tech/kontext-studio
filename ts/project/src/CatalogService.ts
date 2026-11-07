import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, DataApiBaseService } from "@kontext-tech/common";
import type {
   CatalogConnection,
   CatalogConnectionRequest,
   CatalogConnectionValidationResult,
   CatalogEntitySummary,
   CatalogNamespaceSummary,
   CatalogProviderDefinition,
   CatalogSyncStatus
} from "@kontext-tech/schema";

/**
 * Wraps the catalog endpoints behind the `ApiResult` contract used across the
 * app. Same pattern as `KnowledgeService`.
 */
export class CatalogService extends DataApiBaseService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async listProviders(
      projectId: string
   ): Promise<ApiResult<CatalogProviderDefinition[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/catalog/providers", {
               params: { query: { projectId } }
            })
         );
         return ApiResult.success(result as CatalogProviderDefinition[]);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async listConnections(
      projectId: string
   ): Promise<ApiResult<CatalogConnection[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/catalog/connections", {
               params: { query: { projectId } }
            })
         );
         return ApiResult.success(result as CatalogConnection[]);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async createConnection(
      projectId: string,
      request: CatalogConnectionRequest
   ): Promise<ApiResult<CatalogConnection>> {
      try {
         const result = await this.request(
            this.apiClient.POST("/catalog/connections", {
               params: { query: { projectId } },
               body: request
            })
         );
         return ApiResult.success(result as CatalogConnection);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async updateConnection(
      projectId: string,
      connectionId: string,
      request: CatalogConnectionRequest
   ): Promise<ApiResult<CatalogConnection>> {
      try {
         const result = await this.request(
            this.apiClient.PUT("/catalog/connections/{connectionId}", {
               params: {
                  path: { connectionId },
                  query: { projectId }
               },
               body: request
            })
         );
         return ApiResult.success(result as CatalogConnection);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async deleteConnection(
      projectId: string,
      connectionId: string
   ): Promise<ApiResult<void>> {
      try {
         await this.request(
            this.apiClient.DELETE("/catalog/connections/{connectionId}", {
               params: {
                  path: { connectionId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async validateConnection(
      projectId: string,
      connectionId: string
   ): Promise<ApiResult<CatalogConnectionValidationResult>> {
      try {
         const result = await this.request(
            this.apiClient.POST(
               "/catalog/connections/{connectionId}/validate",
               {
                  params: {
                     path: { connectionId },
                     query: { projectId }
                  }
               }
            )
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async syncConnection(
      projectId: string,
      connectionId: string
   ): Promise<ApiResult<CatalogSyncStatus>> {
      try {
         const result = await this.request(
            this.apiClient.POST("/catalog/connections/{connectionId}/sync", {
               params: {
                  path: { connectionId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async listNamespaces(
      projectId: string,
      connectionId?: string
   ): Promise<ApiResult<CatalogNamespaceSummary[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/catalog/namespaces", {
               params: {
                  query: { projectId, connectionId }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async listEntities(
      projectId: string,
      connectionId?: string,
      namespaceName?: string
   ): Promise<ApiResult<CatalogEntitySummary[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/catalog/entities", {
               params: {
                  query: { projectId, connectionId, namespaceName }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
