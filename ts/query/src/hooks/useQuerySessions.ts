import { useUserStore } from "@kontext-tech/identity";
import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import type {
   CreateQuerySessionRequest,
   QueryExecRequest,
   QueryModel,
   QueryResponse,
   QuerySessionModel,
   TriggerActorModel,
   UpdateQuerySessionRequest
} from "@kontext-tech/schema";
import { QuerySessionStatus, TriggerActorType } from "@kontext-tech/schema";
import { useCallback, useEffect, useMemo } from "react";
import { useQuerySessionStore } from "../stores";

interface CreateSessionParams {
   sessionName?: string;
}

/**
 * Project-bound version of query sessions hook.
 * Simplifies usage by binding all operations to a specific projectId.
 */
export interface UseProjectQuerySessionsReturn {
   // State
   isLoading: boolean;
   error: string | null;
   authContext: ApiAuthContext;

   // Project-specific data
   sessions: QuerySessionModel[];
   activeSessions: QuerySessionModel[];
   selectedSession: QuerySessionModel | null;
   effectiveSession: QuerySessionModel | null;
   hasActiveSessions: boolean;

   // Bound getters
   isSessionReady: (sessionId: string) => boolean;
   getSession: (sessionId: string) => QuerySessionModel | null;

   // Bound actions (projectId pre-applied)
   createSession: (
      params?: CreateSessionParams
   ) => Promise<QuerySessionModel | null>;
   selectSession: (sessionId: string) => void;
   refreshSessions: () => Promise<void>;
   initializeSession: (sessionId: string) => Promise<QuerySessionModel | null>;
   ensureSession: (
      params?: CreateSessionParams
   ) => Promise<QuerySessionModel | null>;
   updateSession: (
      sessionId: string,
      updates: UpdateQuerySessionRequest
   ) => Promise<QuerySessionModel | null>;
   executeQuery: (
      sessionId: string,
      sqlQuery: string,
      triggeredBy?: TriggerActorModel,
      storeResultThresholdRows?: number,
      queryTimeoutSeconds?: number,
      storeResultAsResource?: boolean,
      chatSessionId?: string,
      parentRunId?: string,
      notebookContext?: { notebookId: string; blockId: string }
   ) => Promise<QueryResponse | null>;
   closeSession: (
      sessionId: string
   ) => Promise<{ succeed: boolean; error?: { messages?: string[] } }>;
   getQueries: (sessionId: string) => Promise<QueryModel[] | null>;
   clearSessions: () => void;
}

export const useProjectQuerySessions = (
   projectId?: string,
   errorHandler?: (error: ApiErrorResult) => Promise<void>
): UseProjectQuerySessionsReturn => {
   // Get auth context from userStore
   const tokens = useUserStore((state) => state.tokens);
   const user = useUserStore((state) => state.user);

   // Create auth context for service calls
   const authContext: ApiAuthContext = useMemo(
      () => ({
         accessToken: tokens?.accessToken
      }),
      [tokens?.accessToken]
   );

   // Use Zustand selectors to avoid object reference changes
   const sessions = useQuerySessionStore((state) => state.sessions);
   const isLoading = useQuerySessionStore((state) => state.isLoading);
   const error = useQuerySessionStore((state) => state.error);

   const storeCreateSession = useQuerySessionStore(
      (state) => state.createSession
   );
   const storeSetSelectedSession = useQuerySessionStore(
      (state) => state.setSelectedSession
   );
   const storeRefreshSessions = useQuerySessionStore(
      (state) => state.refreshSessions
   );
   const storeInitializeSession = useQuerySessionStore(
      (state) => state.initializeSession
   );
   const storeUpdateSession = useQuerySessionStore(
      (state) => state.updateSession
   );
   const storeExecuteQuery = useQuerySessionStore(
      (state) => state.executeQuery
   );
   const storeCloseSession = useQuerySessionStore(
      (state) => state.closeSession
   );
   const storeGetQueries = useQuerySessionStore((state) => state.getQueries);
   const storeClearSessionsFor = useQuerySessionStore(
      (state) => state.clearSessionsFor
   );
   const storeGetEffectiveSession = useQuerySessionStore(
      (state) => state.getEffectiveSession
   );

   const selectSession = useCallback(
      (sessionId: string) => {
         if (!projectId) return;
         storeSetSelectedSession(projectId, sessionId);
      },
      [projectId, storeSetSelectedSession]
   );

   // Project-specific data (memoized)
   const projectSessions = useMemo((): QuerySessionModel[] => {
      if (!projectId) return [];
      return sessions.filter(
         (session: QuerySessionModel) =>
            session.projectId === projectId &&
            (!user?.id || session.ownerId === user.id)
      );
   }, [projectId, sessions, user]);

   const activeSessions = useMemo((): QuerySessionModel[] => {
      if (!projectId) return [];
      return sessions.filter(
         (session: QuerySessionModel) =>
            session.projectId === projectId &&
            (session.status === QuerySessionStatus.Active ||
               session.status === QuerySessionStatus.Initializing) &&
            (!user?.id || session.ownerId === user.id)
      );
   }, [projectId, sessions, user]);

   const selectedSession = useQuerySessionStore((state) =>
      projectId ? state.getSelectedSession(projectId, user?.id) : null
   );

   const effectiveSession = useQuerySessionStore((state) =>
      projectId ? state.getEffectiveSession(projectId, user?.id) : null
   );

   const hasActiveSessions = useMemo(
      () => activeSessions.length > 0,
      [activeSessions]
   );

   const getSession = useCallback(
      (sessionId: string): QuerySessionModel | null => {
         if (!sessionId) return null;
         return sessions.find((s) => s.id === sessionId) || null;
      },
      [sessions]
   );

   const isSessionReady = useCallback(
      (sessionId: string): boolean => {
         if (!sessionId) return false;
         const session = sessions.find((s) => s.id === sessionId);
         return session?.status === QuerySessionStatus.Active;
      },
      [sessions]
   );

   // Bound Actions
   const createSession = useCallback(
      async (
         params?: CreateSessionParams
      ): Promise<QuerySessionModel | null> => {
         if (!projectId) return null;

         const request: CreateQuerySessionRequest = {
            projectId,
            sessionName:
               params?.sessionName || `Session ${new Date().toLocaleString()}`
         };

         return storeCreateSession(request, authContext, errorHandler);
      },
      [projectId, storeCreateSession, authContext, errorHandler]
   );

   const refreshSessions = useCallback(async (): Promise<void> => {
      if (!projectId) return;
      return storeRefreshSessions(projectId, authContext, errorHandler);
   }, [projectId, storeRefreshSessions, authContext, errorHandler]);

   // Refresh sessions automatically when project/auth changes
   useEffect(() => {
      if (projectId && authContext.accessToken) {
         refreshSessions();
      }
   }, [projectId, authContext.accessToken, refreshSessions]);

   const initializeSession = useCallback(
      async (sessionId: string): Promise<QuerySessionModel | null> => {
         if (!sessionId) return null;
         return storeInitializeSession(sessionId, authContext, errorHandler);
      },
      [storeInitializeSession, authContext, errorHandler]
   );

   const ensureSession = useCallback(
      async (
         params?: CreateSessionParams
      ): Promise<QuerySessionModel | null> => {
         if (!projectId) return null;

         const currentSession = storeGetEffectiveSession(projectId, user?.id);
         if (currentSession?.status === QuerySessionStatus.Active) {
            return currentSession;
         }

         if (currentSession?.id) {
            return initializeSession(currentSession.id);
         }

         const newSession = await createSession(params);
         if (!newSession?.id) {
            return null;
         }

         if (newSession.status === QuerySessionStatus.Active) {
            return newSession;
         }

         return initializeSession(newSession.id);
      },
      [
         projectId,
         storeGetEffectiveSession,
         user?.id,
         initializeSession,
         createSession
      ]
   );

   const updateSession = useCallback(
      async (
         sessionId: string,
         updates: UpdateQuerySessionRequest
      ): Promise<QuerySessionModel | null> => {
         if (!projectId || !sessionId) return null;
         return storeUpdateSession(
            projectId,
            sessionId,
            updates,
            authContext,
            errorHandler
         );
      },
      [projectId, storeUpdateSession, authContext, errorHandler]
   );

   const executeQuery = useCallback(
      async (
         sessionId: string,
         sqlQuery: string,
         triggeredBy: TriggerActorModel = {
            type: TriggerActorType.System,
            id: "ui"
         },
         storeResultThresholdRows?: number,
         queryTimeoutSeconds?: number,
         storeResultAsResource = false,
         chatSessionId?: string,
         parentRunId?: string,
         notebookContext?: { notebookId: string; blockId: string }
      ): Promise<QueryResponse | null> => {
         if (!projectId || !sessionId) return null;

         const request: QueryExecRequest = {
            projectId,
            sessionId,
            sqlQuery,
            triggeredBy,
            chatSessionId,
            parentRunId,
            storeResultThresholdRows,
            queryTimeoutSeconds,
            storeResultAsResource,
            ...(notebookContext
               ? {
                    notebookId: notebookContext.notebookId,
                    blockId: notebookContext.blockId
                 }
               : {})
         };

         return storeExecuteQuery(request, authContext, errorHandler);
      },
      [projectId, storeExecuteQuery, authContext, errorHandler]
   );

   const closeSession = useCallback(
      async (sessionId: string) => {
         if (!projectId || !sessionId) {
            return {
               succeed: false,
               error: { messages: ["Project ID and Session ID are required"] }
            };
         }
         return storeCloseSession(
            projectId,
            sessionId,
            authContext,
            errorHandler
         );
      },
      [projectId, storeCloseSession, authContext, errorHandler]
   );

   const getQueries = useCallback(
      async (sessionId: string): Promise<QueryModel[] | null> => {
         if (!projectId || !sessionId) return null;
         return storeGetQueries(
            projectId,
            sessionId,
            authContext,
            errorHandler
         );
      },
      [projectId, storeGetQueries, authContext, errorHandler]
   );

   const clearSessions = useCallback(() => {
      if (!projectId) return;
      storeClearSessionsFor(projectId);
   }, [projectId, storeClearSessionsFor]);

   return {
      // State
      isLoading,
      error,
      authContext,

      // Project-specific data
      sessions: projectSessions,
      activeSessions,
      selectedSession,
      effectiveSession,
      hasActiveSessions,

      // Bound Getters
      isSessionReady,
      getSession,

      // Bound Actions
      createSession,
      selectSession,
      refreshSessions,
      initializeSession,
      ensureSession,
      updateSession,
      executeQuery,
      closeSession,
      getQueries,
      clearSessions
   };
};
