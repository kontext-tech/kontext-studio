import type { QuerySessionModel } from "@kontext-tech/schema";
import type {
   QueryExecutionService,
   QuerySessionServiceContract
} from "../types/querySessionService";

/**
 * Minimal context handed to the extracted query action factory.
 *
 * Mirrors the chat package's `StoreContext` so both stores follow one pattern.
 * Only the fields the actions actually read/write are declared, which keeps the
 * factory decoupled from the store module and avoids an import cycle.
 */
export interface QueryStoreContext {
   get: () => QueryStoreContextState;
   set: (
      partial:
         | Partial<QueryStoreContextState>
         | ((state: QueryStoreContextState) => Partial<QueryStoreContextState>),
      replace?: false,
      actionName?: string
   ) => void;
}

/**
 * The slice of store state the action factory touches. The store's own state
 * type is structurally compatible, so it can be passed directly.
 */
export interface QueryStoreContextState {
   sessions: QuerySessionModel[];
   refreshingProjects: string[];
   isLoading: boolean;
   error: string | null;
   serviceOverrides?: {
      sessionService: QuerySessionServiceContract;
      queryService: QueryExecutionService;
   };
   getSession: (sessionId: string) => QuerySessionModel | null;
   addSession: (session: QuerySessionModel) => void;
   removeSession: (sessionId: string) => void;
   setSelectedSession: (projectId: string, sessionId: string | null) => void;
}
