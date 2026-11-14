import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, DataApiBaseService } from "@kontext-tech/common";
import type {
   CreateQuerySessionRequest,
   PaginatedListOfQuerySessionModel,
   QuerySessionModel,
   SessionInitRequest,
   SessionInitResponse,
   UpdateQuerySessionRequest
} from "@kontext-tech/schema";
import type { QuerySessionServiceContract } from "./types/querySessionService";

/**
 * Service for managing query sessions via the Data-AI API.
 * Query sessions are used for DuckDB-based data querying within projects.
 */
export class QuerySessionService
   extends DataApiBaseService
   implements QuerySessionServiceContract
{
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   // ===== QUERY SESSION OPERATIONS =====

   /**
    * Create a new query session for a project.
    * This creates the session record with INITIALIZING status.
    */
   async createSession(
      request: CreateQuerySessionRequest
   ): Promise<ApiResult<QuerySessionModel>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.POST("/session", {
               body: request
            })
         );
         return result as QuerySessionModel;
      });
   }

   /** Initialize a query session with catalog context. */
   async initializeSession(
      request: SessionInitRequest
   ): Promise<ApiResult<SessionInitResponse>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.POST("/session/init", {
               body: request
            })
         );
         return result as SessionInitResponse;
      });
   }

   /**
    * Get a query session by ID
    */
   async getSession(
      projectId: string,
      sessionId: string
   ): Promise<ApiResult<QuerySessionModel>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/session/{sessionId}", {
               params: {
                  path: { sessionId },
                  query: { projectId }
               }
            })
         );
         return result as QuerySessionModel;
      });
   }

   /**
    * Update an existing query session
    */
   async updateSession(
      projectId: string,
      sessionId: string,
      request: UpdateQuerySessionRequest
   ): Promise<ApiResult<QuerySessionModel>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.PATCH("/session/{sessionId}", {
               params: {
                  path: { sessionId },
                  query: { projectId }
               },
               body: request
            })
         );
         return result as QuerySessionModel;
      });
   }

   /**
    * Close/delete a query session
    */
   async closeSession(
      projectId: string,
      sessionId: string
   ): Promise<ApiResult<void>> {
      return this.wrap(async () => {
         await this.request(
            this.apiClient.DELETE("/session/{sessionId}", {
               params: {
                  path: { sessionId },
                  query: { projectId }
               }
            })
         );
         return undefined;
      });
   }

   /**
    * Get all query sessions for the authorized project
    */
   async listSessions(
      projectId: string,
      pageIndex?: number,
      pageSize?: number
   ): Promise<ApiResult<PaginatedListOfQuerySessionModel>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/session", {
               params: {
                  query: { projectId, pageIndex, pageSize }
               }
            })
         );
         return result as PaginatedListOfQuerySessionModel;
      });
   }

   /**
    * Get query execution history for a session
    */
   async getSessionQueryHistory(
      projectId: string,
      sessionId: string,
      pageIndex?: number,
      pageSize?: number
   ): Promise<ApiResult<{ queries: unknown[]; total: number }>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/query/sessions/{sessionId}/history", {
               params: {
                  path: { sessionId },
                  query: { projectId, pageIndex, pageSize }
               }
            })
         );
         return result as { queries: unknown[]; total: number };
      });
   }
}
