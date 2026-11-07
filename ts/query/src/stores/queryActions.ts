import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ServiceContainer } from "@kontext-tech/common";
import type {
   CreateQuerySessionRequest,
   QueryExecRequest,
   QueryModel,
   QueryResponse,
   QuerySessionModel,
   SessionInitRequest,
   UpdateQuerySessionRequest
} from "@kontext-tech/schema";
import { QueryService } from "../QueryService";
import { QuerySessionService } from "../QuerySessionService";
import type {
   QueryExecutionService,
   QuerySessionServiceContract
} from "../types/querySessionService";
import type { QueryStoreContext } from "./storeContextTypes";

/**
 * Business-logic actions for the query session store.
 *
 * Extracted from `querySessionStore.ts` following the same pattern as the chat
 * package: the store owns state and the simple setters, this module owns
 * everything that talks to a service. The service containers live here because
 * only these actions use them.
 */
const querySessionContainer = new ServiceContainer();
const queryExecutionContainer = new ServiceContainer();

export interface QuerySessionActions {
   createSession: (
      request: CreateQuerySessionRequest,
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<QuerySessionModel | null>;
   initializeSession: (
      sessionId: string,
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<QuerySessionModel | null>;
   updateSession: (
      projectId: string,
      sessionId: string,
      updates: UpdateQuerySessionRequest,
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<QuerySessionModel | null>;
   refreshSessions: (
      projectId: string,
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<void>;
   closeSession: (
      projectId: string,
      sessionId: string,
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<{ succeed: boolean; error?: { messages?: string[] } }>;
   getQueries: (
      projectId: string,
      sessionId: string,
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<QueryModel[] | null>;
   executeQuery: (
      request: QueryExecRequest,
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<QueryResponse | null>;
}

/**
 * Builds the query-session business actions against the provided store context.
 */
export function createQuerySessionActions(
   ctx: QueryStoreContext
): QuerySessionActions {
   const { get, set } = ctx;

   const updateSessionInState = (updatedSession: QuerySessionModel) => {
      set(
         (state) => ({
            sessions: state.sessions.map((session) =>
               session.id === updatedSession.id ? updatedSession : session
            )
         }),
         false,
         "updateSessionInState"
      );
   };

   // Helper function to get session service with auth context
   const getSessionService = (
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ): QuerySessionServiceContract => {
      const { serviceOverrides } = get();

      if (serviceOverrides) {
         return serviceOverrides.sessionService as QuerySessionServiceContract;
      }

      querySessionContainer.setAuthContext(authContext);
      querySessionContainer.setErrorHandler(errorHandler);
      return querySessionContainer.getOrCreate(
         "session-service",
         (c) =>
            new QuerySessionService(c.createAuthContext(), c.getErrorHandler())
      );
   };

   // Helper function to get query execution service
   const getQueryService = (
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ): QueryExecutionService => {
      queryExecutionContainer.setAuthContext(authContext);
      queryExecutionContainer.setErrorHandler(errorHandler);
      return queryExecutionContainer.getOrCreate(
         "query-service",
         (c) => new QueryService(c.createAuthContext(), c.getErrorHandler())
      );
   };

   return {
      createSession: async (request, authContext, errorHandler) => {
         try {
            set({ isLoading: true }, false, "createSession:start");

            const sessionService = getSessionService(authContext, errorHandler);
            const result = await sessionService.createSession(request);

            if (result.succeed && result.data) {
               const newSession = result.data;
               get().addSession(newSession);
               if (newSession.projectId && newSession.id) {
                  get().setSelectedSession(newSession.projectId, newSession.id);
               }
               return newSession;
            }

            return null;
         } catch (error) {
            console.error("Failed to create session:", error);
            set(
               { error: "Failed to create session" },
               false,
               "createSession:error"
            );
            return null;
         } finally {
            set({ isLoading: false }, false, "createSession:end");
         }
      },

      initializeSession: async (sessionId, authContext, errorHandler) => {
         try {
            set({ isLoading: true }, false, "initializeSession:start");

            // First get the session details to gather required information
            const session = get().getSession(sessionId);
            if (!session) {
               console.error("Session not found in store for initialization");
               set(
                  { error: "Session not found for initialization" },
                  false,
                  "initializeSession:error"
               );
               return null;
            }

            const sessionService = getSessionService(authContext, errorHandler);

            const initRequest: SessionInitRequest = {
               sessionId: session.id || sessionId, // Use session.id if available, fallback to parameter
               projectId: session.projectId,
               catalogConnectionId: session.catalogConnectionId || undefined,
               defaultNamespace: session.defaultNamespace || undefined,
               defaultEntityId: session.defaultEntityId || undefined,
               userId: undefined, // User ID is now determined server-side from auth context
               persistent: true // Assuming sessions are persistent by default
            };

            // Server now handles polling - this call blocks until session is ready
            const result = await sessionService.initializeSession(initRequest);

            if (result.succeed && result.data?.success && result.data.session) {
               // Server-side polling completed successfully
               updateSessionInState(result.data.session);
               return result.data.session;
            }

            // Initialization failed
            const errorMessage =
               result.data?.errorMessage || "Failed to initialize session";
            console.error(errorMessage);
            set({ error: errorMessage }, false, "initializeSession:error");
            return null;
         } catch (error) {
            console.error("Failed to initialize session:", error);
            set(
               { error: "Failed to initialize session" },
               false,
               "initializeSession:error"
            );
            return null;
         } finally {
            set({ isLoading: false }, false, "initializeSession:end");
         }
      },

      updateSession: async (
         projectId,
         sessionId,
         updates,
         authContext,
         errorHandler
      ) => {
         try {
            const sessionService = getSessionService(authContext, errorHandler);
            const result = await sessionService.updateSession(
               projectId,
               sessionId,
               updates
            );
            if (result.succeed && result.data) {
               updateSessionInState(result.data);
               return result.data;
            }
            return null;
         } catch (error) {
            console.error("Failed to update session:", error);
            return null;
         }
      },

      refreshSessions: async (projectId, authContext, errorHandler) => {
         // Prevent concurrent refreshes for the same project
         if (get().refreshingProjects.includes(projectId)) {
            return;
         }

         try {
            set(
               (state) => ({
                  refreshingProjects: [...state.refreshingProjects, projectId],
                  isLoading: true
               }),
               false,
               "refreshSessions:start"
            );

            // Use real session service
            const sessionService = getSessionService(authContext, errorHandler);
            const result = await sessionService.listSessions(
               projectId,
               undefined,
               undefined
            );

            if (result.succeed && result.data) {
               // Replace project sessions while keeping others
               // Filter locally by projectId since API uses auth context
               const sessions = result.data.items || [];
               const projectSessions = sessions.filter(
                  (s: QuerySessionModel) => s.projectId === projectId
               );
               set(
                  (state) => ({
                     sessions: [
                        ...state.sessions.filter(
                           (s) => s.projectId !== projectId
                        ),
                        ...projectSessions
                     ]
                  }),
                  false,
                  "refreshSessions:success"
               );
            }
         } catch (error) {
            console.error("Failed to refresh sessions:", error);
            set(
               { error: "Failed to refresh sessions" },
               false,
               "refreshSessions:error"
            );
         } finally {
            set(
               (state) => ({
                  refreshingProjects: state.refreshingProjects.filter(
                     (p) => p !== projectId
                  ),
                  isLoading: false
               }),
               false,
               "refreshSessions:end"
            );
         }
      },

      closeSession: async (projectId, sessionId, authContext, errorHandler) => {
         try {
            const sessionService = getSessionService(authContext, errorHandler);
            const result = await sessionService.closeSession(
               projectId,
               sessionId
            );
            if (result.succeed) {
               get().removeSession(sessionId);
            }
            return result;
         } catch (error) {
            console.error("Failed to close session:", error);
            return {
               succeed: false,
               error: { messages: ["Failed to close session"] }
            };
         }
      },

      getQueries: async (projectId, sessionId, authContext, errorHandler) => {
         try {
            const sessionService = getSessionService(authContext, errorHandler);
            const result = await sessionService.getSessionQueryHistory(
               projectId,
               sessionId
            );
            // Extract queries from the paginated response
            return result.succeed
               ? (result.data?.queries as QueryModel[]) || []
               : null;
         } catch (error) {
            console.error("Failed to get session queries:", error);
            return null;
         }
      },

      executeQuery: async (request, authContext, errorHandler) => {
         try {
            const { serviceOverrides } = get();

            if (serviceOverrides) {
               const result =
                  await serviceOverrides.queryService.executeQuery(request);

               return result.succeed ? result.data || null : null;
            }

            // Execute the query using the Data QueryService
            const queryService = getQueryService(authContext, errorHandler);
            const result = await queryService.executeQuery(request);

            // Check if API call succeeded and response data is valid
            if (result.succeed && result.data) {
               // Check if the query execution itself was successful
               if (result.data.success !== false) {
                  // Update session's last accessed time for successful queries
                  const session = get().getSession(request.sessionId);
                  if (session) {
                     updateSessionInState({
                        ...session,
                        lastAccessedAt: new Date().toISOString()
                     } as QuerySessionModel);
                  }
                  return result.data;
               } else {
                  // Query execution failed (200 response but success: false) - show error message from response
                  if (errorHandler) {
                     const errorResult: ApiErrorResult = {
                        title: "Query Execution Failed",
                        status: 400,
                        messages: [
                           result.data.errorMessage || "Query execution failed"
                        ]
                     };
                     await errorHandler(errorResult);
                  }
                  return result.data; // Return the failed result so caller can access error details
               }
            }

            // For non-200 responses, the API service handles them automatically
            return result.data || null;
         } catch (error) {
            console.error("Failed to execute query:", error);

            // Handle unexpected errors
            if (errorHandler) {
               const errorResult: ApiErrorResult = {
                  title: "Query Execution Error",
                  status: 500,
                  messages: [
                     "An unexpected error occurred while executing the query"
                  ],
                  error: {
                     messages: [
                        "An unexpected error occurred while executing the query"
                     ]
                  }
               };
               await errorHandler(errorResult);
            }

            return null;
         }
      }
   };
}
