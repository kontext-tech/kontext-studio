import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import type {
   CreateQuerySessionRequest,
   QueryModel,
   QuerySessionModel,
   UpdateQuerySessionRequest
} from "@kontext-labs/schema";
import {
   QuerySessionStatus,
   type QueryExecRequest,
   type QueryResponse
} from "@kontext-labs/schema";
import { create } from "zustand";
import { devtools } from "zustand/middleware";
import type {
   QueryExecutionService,
   QuerySessionServiceContract
} from "../types/querySessionService";
import { createQuerySessionActions } from "./queryActions";

interface QuerySessionStoreState {
   sessions: QuerySessionModel[];
   selectedSession: Record<string, string>; // projectId -> sessionId
   isLoading: boolean;
   refreshingProjects: string[]; // List of project IDs currently being refreshed
   error: string | null;
   serviceOverrides?: {
      sessionService: QuerySessionServiceContract;
      queryService: QueryExecutionService;
   };
}

interface QuerySessionStoreActions {
   // Basic store actions
   setSessions: (sessions: QuerySessionModel[]) => void;
   clearSessions: () => void;
   setLoading: (loading: boolean) => void;
   setError: (error: string | null) => void;
   getSession: (sessionId: string) => QuerySessionModel | null;
   addSession: (session: QuerySessionModel) => void;
   removeSession: (sessionId: string) => void;
   getActiveSessions: (
      projectId?: string,
      ownerId?: string
   ) => QuerySessionModel[];

   setServiceOverrides: (
      overrides: {
         sessionService: QuerySessionServiceContract;
         queryService: QueryExecutionService;
      } | null
   ) => void;

   // Project-specific actions
   setSelectedSession: (projectId: string, sessionId: string | null) => void;
   getSelectedSession: (
      projectId: string,
      ownerId?: string
   ) => QuerySessionModel | null;
   getEffectiveSession: (
      projectId: string,
      ownerId?: string
   ) => QuerySessionModel | null;
   clearSessionsFor: (projectId: string) => void;
   hasActiveSessions: (projectId: string, ownerId?: string) => boolean;

   // Business logic actions (now accept auth context and optional error handler)
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

type QuerySessionStore = QuerySessionStoreState & QuerySessionStoreActions;

export const useQuerySessionStore = create<QuerySessionStore>()(
   devtools(
      (set, get) => {
         const getSessionTimestamp = (session: QuerySessionModel) =>
            new Date(
               session.lastAccessedAt ||
                  session.updatedAt ||
                  session.createdAt ||
                  0
            ).getTime();

         const isActiveSession = (session: QuerySessionModel) =>
            session.status === QuerySessionStatus.Active ||
            session.status === QuerySessionStatus.Initializing;

         const matchesProjectOwner = (
            session: QuerySessionModel,
            projectId?: string,
            ownerId?: string
         ) => {
            if (projectId && session.projectId !== projectId) {
               return false;
            }

            if (ownerId && session.ownerId && session.ownerId !== ownerId) {
               return false;
            }

            return true;
         };

         // Return the initial store state and actions
         return {
            // Initial state
            sessions: [],
            selectedSession: {},
            isLoading: false,
            refreshingProjects: [],
            error: null,
            serviceOverrides: undefined,

            // Actions
            setError: (error) => set({ error }, false, "setError"),

            setSessions: (sessions: QuerySessionModel[]) =>
               set({ sessions }, false, "setSessions"),

            setLoading: (loading: boolean) =>
               set({ isLoading: loading }, false, "setLoading"),

            clearSessions: () =>
               set(
                  {
                     sessions: [],
                     selectedSession: {},
                     isLoading: false,
                     error: null
                  },
                  false,
                  "clearSessions"
               ),

            setServiceOverrides: (serviceOverrides) =>
               set(
                  {
                     serviceOverrides: serviceOverrides || undefined
                  },
                  false,
                  "setServiceOverrides"
               ),

            getSession: (sessionId) => {
               const { sessions } = get();
               return (
                  sessions.find((session) => session.id === sessionId) || null
               );
            },

            addSession: (session) =>
               set(
                  (state) => ({
                     sessions: [...state.sessions, session]
                  }),
                  false,
                  "addSession"
               ),

            removeSession: (sessionId) =>
               set(
                  (state) => ({
                     sessions: state.sessions.filter(
                        (session) => session.id !== sessionId
                     )
                  }),
                  false,
                  "removeSession"
               ),

            getActiveSessions: (projectId, ownerId) => {
               const { sessions } = get();
               return sessions.filter((s) => {
                  return (
                     matchesProjectOwner(s, projectId, ownerId) &&
                     isActiveSession(s)
                  );
               });
            },

            // Project-specific actions
            setSelectedSession: (projectId, sessionId) =>
               set(
                  (state) => {
                     const newSelected = { ...state.selectedSession };
                     if (sessionId) {
                        newSelected[projectId] = sessionId;
                     } else {
                        delete newSelected[projectId];
                     }
                     return { selectedSession: newSelected };
                  },
                  false,
                  "setSelectedSession"
               ),

            getSelectedSession: (projectId, ownerId) => {
               const { selectedSession } = get();
               const sessionId = selectedSession[projectId];
               if (!sessionId) return null;

               // Get the session from store
               const session = get().getSession(sessionId);
               if (!session) {
                  // Session doesn't exist in store, clear the stale selection
                  get().setSelectedSession(projectId, null);
                  return null;
               }

               // Validate that session still belongs to the correct project
               if (
                  !matchesProjectOwner(session, projectId, ownerId) ||
                  session.status === QuerySessionStatus.Closed ||
                  session.status === QuerySessionStatus.Deleted
               ) {
                  // Session was moved or changed, clear the stale selection
                  get().setSelectedSession(projectId, null);
                  return null;
               }

               return session;
            },

            getEffectiveSession: (projectId, ownerId) => {
               const selected = get().getSelectedSession(projectId, ownerId);
               if (selected) {
                  return selected;
               }

               const activeSessions = get()
                  .getActiveSessions(projectId, ownerId)
                  .sort((left, right) => {
                     if (left.status !== right.status) {
                        if (left.status === QuerySessionStatus.Active) {
                           return -1;
                        }
                        if (right.status === QuerySessionStatus.Active) {
                           return 1;
                        }
                     }

                     return (
                        getSessionTimestamp(right) - getSessionTimestamp(left)
                     );
                  });

               return activeSessions[0] || null;
            },

            clearSessionsFor: (projectId: string) =>
               set(
                  (state) => {
                     const newSelected = { ...state.selectedSession };
                     delete newSelected[projectId];
                     return {
                        sessions: state.sessions.filter(
                           (session) => session.projectId !== projectId
                        ),
                        selectedSession: newSelected
                     };
                  },
                  false,
                  "clearSessionsFor"
               ),

            hasActiveSessions: (projectId, ownerId) => {
               return get().getActiveSessions(projectId, ownerId).length > 0;
            },

            // Business logic actions live in `queryActions.ts`; they are bound to
            // this store's `get`/`set` here so the store stays a state container.
            ...createQuerySessionActions({ get, set })
         };
      },
      {
         name: "query-session-store"
      }
   )
);
