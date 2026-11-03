import type { ChatSessionState } from "./chatSessionStore";

/**
 * Shared mutable box for the recent-sessions cache.
 *
 * Historically these lived as closure variables inside the zustand creator.
 * Extracting the async actions into factory modules required externalizing
 * them so the factories can share the same cache instance across the store.
 */
export interface RecentSessionsCache {
   request: Promise<void> | null;
   key: string | null;
   fetchedAt: number;
}

/**
 * Minimal context handed to extracted action factories.
 *
 * `get`/`set` are the zustand store primitives; the cache is a mutable box so
 * `fetchRecentSessions` (in `sessionActions`) and project switches (which swap
 * in a fresh store instance) can reset it without exposing raw closure
 * variables.
 */
export interface StoreContext {
   get: () => ChatSessionState;
   set: (
      partial:
         | Partial<ChatSessionState>
         | ((state: ChatSessionState) => Partial<ChatSessionState>)
   ) => void;
   recentSessionsCache: RecentSessionsCache;
}
