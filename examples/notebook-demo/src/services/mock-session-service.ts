import type { ApiErrorResult } from "@kontext-labs/common";
import { ApiResult } from "@kontext-labs/common";
import type {
   QueryExecutionService,
   QuerySessionServiceContract
} from "@kontext-labs/query";
import type {
   CreateQuerySessionRequest,
   InlineData,
   PaginatedListOfQuerySessionModel,
   QueryExecRequest,
   QueryModel,
   QueryResponse,
   QuerySessionModel,
   SessionInitRequest,
   SessionInitResponse,
   UpdateQuerySessionRequest
} from "@kontext-labs/schema";
import { QuerySessionStatus } from "@kontext-labs/schema";
import type { MockResourceService } from "./mock-resource-service";

/**
 * Mock implementation of QuerySessionServiceContract for testing and demos
 * Also implements QueryExecutionService to provide query execution capabilities
 */
export class MockQuerySessionService
   implements QuerySessionServiceContract, QueryExecutionService
{
   private sessions: QuerySessionModel[] = [];
   private sessionIdCounter = 1;
   private queryIdCounter = 1;
   private mockResourceService?: MockResourceService;

   constructor(mockResourceService?: MockResourceService) {
      this.mockResourceService = mockResourceService;
      // Initialize with some demo sessions for testing
      this.initializeDemoSessions();
   }

   /**
    * Initialize the mock service with pre-created demo sessions
    */
   private initializeDemoSessions(): void {
      const demoProjectId = "550e8400-e29b-41d4-a716-446655440000";

      // Create a demo session
      this.sessions = [
         {
            id: `session-${this.sessionIdCounter++}`,
            sessionName: "Demo Session",
            projectId: demoProjectId,
            status: QuerySessionStatus.Active,
            ownerId: "demo-user",
            createdAt: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
            updatedAt: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
            lastAccessedAt: new Date(Date.now() - 3600000).toISOString(),
            isPersistent: true,
            engineType: "DuckDB"
         }
      ];

      console.log(
         "🎯 MockQuerySessionService initialized with demo session:",
         this.sessions.length
      );
   }

   /**
    * Helper to create consistent error results
    */
   private createError(
      title: string,
      messages: string[],
      status = 404
   ): ApiErrorResult {
      return {
         title,
         status,
         messages
      };
   }

   async createSession(
      request: CreateQuerySessionRequest
   ): Promise<ApiResult<QuerySessionModel>> {
      console.log(
         "🎯 MockQuerySessionService.createSession called with:",
         request
      );

      // For demo purposes, allow multiple active sessions
      // In production, you might want to enforce single active session per project

      const nextId = this.sessionIdCounter++;
      const session: QuerySessionModel = {
         id: `session-${nextId}`,
         sessionName: request.sessionName || `Session ${nextId}`,
         projectId: request.projectId,
         catalogConnectionId: request.catalogConnectionId,
         defaultNamespace: request.defaultNamespace,
         defaultEntityId: request.defaultEntityId,
         status: QuerySessionStatus.Active,
         ownerId: "demo-user",
         createdAt: new Date().toISOString(),
         updatedAt: new Date().toISOString(),
         lastAccessedAt: new Date().toISOString(),
         isPersistent: true,
         engineType: request.engineType || "DuckDB"
      };

      this.sessions.push(session);

      console.log("🎯 MockQuerySessionService.createSession returning:", {
         succeed: true,
         data: session
      });
      return {
         succeed: true,
         data: session
      };
   }

   async getSession(
      _projectId: string,
      sessionId: string
   ): Promise<ApiResult<QuerySessionModel>> {
      const session = this.sessions.find((s) => s.id === sessionId);
      if (!session) {
         return {
            succeed: false,
            error: this.createError("Session Not Found", ["Session not found"])
         };
      }
      return { succeed: true, data: session };
   }

   async updateSession(
      _projectId: string,
      sessionId: string,
      request: UpdateQuerySessionRequest
   ): Promise<ApiResult<QuerySessionModel>> {
      const index = this.sessions.findIndex((s) => s.id === sessionId);
      if (index < 0) {
         return {
            succeed: false,
            error: this.createError("Session Not Found", ["Session not found"])
         };
      }

      this.sessions[index] = {
         ...this.sessions[index],
         sessionName: request.sessionName || this.sessions[index].sessionName,
         updatedAt: new Date().toISOString()
      };

      return { succeed: true, data: this.sessions[index] };
   }

   async closeSession(
      _projectId: string,
      sessionId: string
   ): Promise<ApiResult<void>> {
      const index = this.sessions.findIndex((s) => s.id === sessionId);
      if (index < 0) {
         return {
            succeed: false,
            error: this.createError("Session Not Found", ["Session not found"])
         };
      }

      this.sessions[index] = {
         ...this.sessions[index],
         status: QuerySessionStatus.Closed,
         updatedAt: new Date().toISOString()
      };

      return { succeed: true };
   }

   async initializeSession(
      request: SessionInitRequest
   ): Promise<ApiResult<SessionInitResponse>> {
      const index = this.sessions.findIndex((s) => s.id === request.sessionId);
      if (index < 0) {
         return {
            succeed: false,
            error: this.createError("Session Not Found", ["Session not found"])
         };
      }

      // Simulate initialization delay (async dispatch + polling)
      await new Promise((resolve) => setTimeout(resolve, 1500));

      this.sessions[index] = {
         ...this.sessions[index],
         status: QuerySessionStatus.Active,
         updatedAt: new Date().toISOString()
      };

      // Return mock init response matching SessionInitResponse schema
      // In real async flow, jobRunId would be returned immediately
      // and session status would be polled separately
      const initResponse: SessionInitResponse = {
         success: true,
         session: this.sessions[index],
         jobRunId: crypto.randomUUID() // Mock job run ID for async tracking
      };

      return { succeed: true, data: initResponse };
   }

   async executeQuery(
      request: QueryExecRequest
   ): Promise<ApiResult<QueryResponse>> {
      const { projectId, sessionId, sqlQuery, triggeredBy } = request;
      void projectId;
      const session = this.sessions.find((s) => s.id === sessionId);
      if (!session) {
         return {
            succeed: false,
            error: this.createError("Session Not Found", ["Session not found"])
         };
      }
      console.log("🎯 MockQuerySessionService.executeQuery called with:", {
         sessionId,
         sqlQuery,
         triggeredBy
      });

      if (session.status !== QuerySessionStatus.Active) {
         return {
            succeed: false,
            error: this.createError(
               "Session Not Active",
               ["Session is not active"],
               400
            )
         };
      }

      // Simulate query execution delay
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Generate a mock resource ID for the data table
      const resourceId = `${crypto.randomUUID()}`;

      // Generate mock data based on the SQL query
      let mockResponse: QueryResponse;
      let inlineData: InlineData | null = null;

      if (sqlQuery.toLowerCase().includes("count")) {
         // Mock count query response
         const table = {
            columns: [{ name: "count", type: "INTEGER", isNullable: false }],
            rows: [["42"]],
            rowCount: 1
         };
         mockResponse = {
            success: true,
            result: table,
            totalExecutionTimeMs: 150,
            dataId: resourceId
         };
         inlineData = {
            title: "Query Result",
            table
         };
      } else if (sqlQuery.toLowerCase().includes("error")) {
         // Mock error response for testing
         mockResponse = {
            success: false,
            result: undefined,
            totalExecutionTimeMs: 100,
            errorMessage: "Syntax error in SQL query",
            dataId: undefined
         };
      } else {
         // Mock successful response with sample data
         const table = {
            columns: [
               { name: "id", type: "INTEGER", isNullable: false },
               { name: "name", type: "VARCHAR", isNullable: false },
               { name: "email", type: "VARCHAR", isNullable: true }
            ],
            rows: [
               ["1", "John Doe", "john@example.com"],
               ["2", "Jane Smith", "jane@example.com"],
               ["3", "Bob Johnson", "bob@example.com"]
            ],
            rowCount: 3
         };
         mockResponse = {
            success: true,
            result: table,
            totalExecutionTimeMs: 850,
            dataId: resourceId
         };
         inlineData = {
            title: "Query Result",
            table
         };
      }

      // Store the data table in the mock resource service if available
      if (inlineData && this.mockResourceService) {
         this.mockResourceService.storeInlineData(resourceId, inlineData);
      }

      console.log(
         "🎯 MockQuerySessionService.executeQuery: Generated dataId:",
         resourceId,
         "Stored:",
         !!inlineData
      );

      return { succeed: true, data: mockResponse };
   }

   async listSessions(
      _projectId: string,
      pageIndex?: number,
      pageSize?: number
   ): Promise<ApiResult<PaginatedListOfQuerySessionModel>> {
      const filteredSessions = [...this.sessions];

      // Apply pagination
      const startIndex = ((pageIndex || 1) - 1) * (pageSize || 10);
      const endIndex = pageSize ? startIndex + pageSize : undefined;
      const items = filteredSessions.slice(startIndex, endIndex);

      const totalCount = filteredSessions.length;
      const totalPages = Math.ceil(totalCount / (pageSize || 10));
      const pIndex = pageIndex || 1;

      return {
         succeed: true,
         data: {
            items,
            totalCount,
            pageIndex: pIndex,
            pageSize: pageSize || 10,
            totalPages,
            hasPreviousPage: pIndex > 1,
            hasNextPage: pIndex < totalPages
         }
      };
   }

   async getSessionQueryHistory(
      _projectId: string,
      sessionId: string,
      pageIndex?: number,
      pageSize?: number
   ): Promise<ApiResult<{ queries: unknown[]; total: number }>> {
      const queries: QueryModel[] = [
         {
            id: `query-${this.queryIdCounter++}`,
            code: "SELECT * FROM users WHERE active = 1",
            succeeded: true,
            recordCount: 15,
            ownerId: "demo-user",
            sessionId: sessionId,
            createdAt: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
            durationMs: 250
         },
         {
            id: `query-${this.queryIdCounter++}`,
            code: "SELECT COUNT(*) FROM orders WHERE date > '2024-01-01'",
            succeeded: true,
            recordCount: 1,
            ownerId: "demo-user",
            sessionId: sessionId,
            createdAt: new Date(Date.now() - 1800000).toISOString(), // 30 minutes ago
            durationMs: 500
         }
      ];

      // Apply pagination
      const start = (pageIndex || 0) * (pageSize || 10);
      const end = start + (pageSize || 10);
      const paginatedQueries = queries.slice(start, end);

      return {
         succeed: true,
         data: { queries: paginatedQueries, total: queries.length }
      };
   }
}
