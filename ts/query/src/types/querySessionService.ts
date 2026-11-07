import type {
   CreateQuerySessionRequest,
   PaginatedListOfQuerySessionModel,
   QueryExecRequest,
   QueryResponse,
   QuerySessionModel,
   SessionInitRequest,
   SessionInitResponse,
   UpdateQuerySessionRequest
} from "@kontext-tech/schema";
import type { ApiResult } from "@kontext-tech/common";

/**
 * Interface for query execution service operations.
 * Used by notebook components for executing SQL queries.
 */
export interface QueryExecutionService {
   /**
    * Execute a SQL query within a session
    */
   executeQuery(request: QueryExecRequest): Promise<ApiResult<QueryResponse>>;
}

/**
 * Interface for query session service operations.
 * This service now uses the Data-AI API (Python FastAPI).
 */
export interface QuerySessionServiceContract {
   /**
    * Create a new query session for a project.
    * This creates the session record with INITIALIZING status.
    */
   createSession(
      request: CreateQuerySessionRequest
   ): Promise<ApiResult<QuerySessionModel>>;

   /**
    * Initialize a query session with catalog context.
    */
   initializeSession(
      request: SessionInitRequest
   ): Promise<ApiResult<SessionInitResponse>>;

   /**
    * Get a query session by ID
    */
   getSession(
      projectId: string,
      sessionId: string
   ): Promise<ApiResult<QuerySessionModel>>;

   /**
    * Update an existing query session
    */
   updateSession(
      projectId: string,
      sessionId: string,
      request: UpdateQuerySessionRequest
   ): Promise<ApiResult<QuerySessionModel>>;

   /**
    * Close/delete a query session
    */
   closeSession(projectId: string, sessionId: string): Promise<ApiResult<void>>;

   /**
    * Get all query sessions for a project
    */
   listSessions(
      projectId: string,
      pageIndex?: number,
      pageSize?: number
   ): Promise<ApiResult<PaginatedListOfQuerySessionModel>>;

   /**
    * Get query execution history for a session
    */
   getSessionQueryHistory(
      projectId: string,
      sessionId: string,
      pageIndex?: number,
      pageSize?: number
   ): Promise<ApiResult<{ queries: unknown[]; total: number }>>;
}
