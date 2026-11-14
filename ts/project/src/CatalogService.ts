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
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/catalog/providers", {
               params: { query: { projectId } }
            })
         );
         return result as CatalogProviderDefinition[];
      });
   }

   async listConnections(
      projectId: string
   ): Promise<ApiResult<CatalogConnection[]>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/catalog/connections", {
               params: { query: { projectId } }
            })
         );
         return result as CatalogConnection[];
      });
   }

   async createConnection(
      projectId: string,
      request: CatalogConnectionRequest
   ): Promise<ApiResult<CatalogConnection>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.POST("/catalog/connections", {
               params: { query: { projectId } },
               body: request
            })
         );
         return result as CatalogConnection;
      });
   }

   async updateConnection(
      projectId: string,
      connectionId: string,
      request: CatalogConnectionRequest
   ): Promise<ApiResult<CatalogConnection>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.PUT("/catalog/connections/{connectionId}", {
               params: {
                  path: { connectionId },
                  query: { projectId }
               },
               body: request
            })
         );
         return result as CatalogConnection;
      });
   }

   async deleteConnection(
      projectId: string,
      connectionId: string
   ): Promise<ApiResult<void>> {
      return this.wrap(async () => {
         await this.request(
            this.apiClient.DELETE("/catalog/connections/{connectionId}", {
               params: {
                  path: { connectionId },
                  query: { projectId }
               }
            })
         );
         return undefined;
      });
   }

   async validateConnection(
      projectId: string,
      connectionId: string
   ): Promise<ApiResult<CatalogConnectionValidationResult>> {
      return this.wrap(async () => {
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
         return result;
      });
   }

   async syncConnection(
      projectId: string,
      connectionId: string
   ): Promise<ApiResult<CatalogSyncStatus>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.POST("/catalog/connections/{connectionId}/sync", {
               params: {
                  path: { connectionId },
                  query: { projectId }
               }
            })
         );
         return result;
      });
   }

   async listNamespaces(
      projectId: string,
      connectionId?: string
   ): Promise<ApiResult<CatalogNamespaceSummary[]>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/catalog/namespaces", {
               params: {
                  query: { projectId, connectionId }
               }
            })
         );
         return result;
      });
   }

   async listEntities(
      projectId: string,
      connectionId?: string,
      namespaceName?: string
   ): Promise<ApiResult<CatalogEntitySummary[]>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/catalog/entities", {
               params: {
                  query: { projectId, connectionId, namespaceName }
               }
            })
         );
         return result;
      });
   }
}
