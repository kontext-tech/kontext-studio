import type { ApiResult } from "@kontext-tech/common";
import type {
   ChatMessage,
   ChatSessionModel,
   PaginatedChatSessionResponse,
   PythonExecutionApprovalMode,
   UpdateChatSessionRequest
} from "@kontext-tech/schema";
import type { ChatSessionService } from "../types/chatSessionService";
import type { StoreContext } from "./storeContextTypes";

const RECENT_SESSIONS_CACHE_TTL_MS = 30_000;
const SIDEBAR_RECENT_SESSIONS_LIMIT = 5;

const notInitializedError =
   "Chat service not initialized. Call initializeChatService first.";

const toErrorMessage = (error: unknown): string =>
   error instanceof Error ? error.message : "Unknown error";

interface ReadyChatServiceScope {
   chatService: ChatSessionService;
   projectId: string;
}

/**
 * Shared guard for the stateful session actions: returns the ready service
 * scope, or records the initialization failure in the store and yields null.
 */
const readyChatServiceScope = (
   ctx: Pick<StoreContext, "get" | "set">
): ReadyChatServiceScope | null => {
   const { chatService, projectId } = ctx.get();
   if (!chatService) {
      ctx.set({ error: notInitializedError });
      return null;
   }
   if (!projectId) {
      ctx.set({ error: "Project not initialized" });
      return null;
   }
   return { chatService, projectId };
};

export interface SessionActions {
   createChatSession: (
      sessionName: string,
      modelSelectionId?: string,
      scope?: {
         defaultCatalogConnectionId?: string;
         defaultNamespace?: string;
         defaultEntityId?: string;
         pythonExecutionApprovalMode?: PythonExecutionApprovalMode;
      }
   ) => Promise<ChatSessionModel | null>;
   updateChatSession: (
      sessionId: string,
      updates: UpdateChatSessionRequest
   ) => Promise<boolean>;
   loadChatSession: (sessionId: string) => Promise<boolean>;
   deleteChatSession: (sessionId: string) => Promise<boolean>;
   setPythonExecutionApprovalMode: (
      mode: PythonExecutionApprovalMode
   ) => Promise<boolean>;
   fetchRecentSessions: (
      mySessionsOnly?: boolean,
      options?: { force?: boolean }
   ) => Promise<void>;
   getFilteredChatSessions: (
      filter?: string,
      pageIndex?: number,
      pageSize?: number,
      mySessionsOnly?: boolean
   ) => Promise<ApiResult<PaginatedChatSessionResponse>>;
}

/**
 * Builds the session-management actions against the provided store context.
 *
 * Keeps the recent-sessions cache inside this factory's closure, matching the
 * original behavior where it was per-store-instance state.
 */
export function createSessionActions(ctx: StoreContext): SessionActions {
   const { get, set, recentSessionsCache } = ctx;

   const refreshRecentSessions = () => {
      void get().fetchRecentSessions(get().mySessionsOnly, { force: true });
   };

   return {
      createChatSession: async (sessionName, modelSelectionId, scope) => {
         const ready = readyChatServiceScope(ctx);
         if (!ready) {
            return null;
         }
         const { chatService, projectId } = ready;

         try {
            set({ error: null, isMessagesLoading: true });

            const result = await chatService.createChatSession({
               projectId,
               sessionName,
               modelSelectionId: modelSelectionId || get().modelSelectionId,
               defaultCatalogConnectionId: scope?.defaultCatalogConnectionId,
               defaultNamespace: scope?.defaultNamespace,
               defaultEntityId: scope?.defaultEntityId,
               pythonExecutionApprovalMode:
                  scope?.pythonExecutionApprovalMode ?? "always_ask"
            });

            if (result.succeed && result.data) {
               set({
                  chatSession: result.data,
                  isMessagesLoading: false
               });
               refreshRecentSessions();
               return result.data;
            } else {
               set({
                  error: result.error?.title || "Failed to create chat session",
                  isMessagesLoading: false
               });
               return null;
            }
         } catch (error) {
            set({ error: toErrorMessage(error), isMessagesLoading: false });
            return null;
         }
      },

      updateChatSession: async (sessionId, updates) => {
         const ready = readyChatServiceScope(ctx);
         if (!ready) {
            return false;
         }
         const { chatService, projectId } = ready;

         try {
            set({ error: null });

            const result = await chatService.updateChatSession(
               sessionId,
               projectId,
               updates
            );

            if (result.succeed && result.data) {
               set({ chatSession: result.data });
               refreshRecentSessions();
               return true;
            } else {
               set({
                  error: result.error?.title || "Failed to update chat session"
               });
               return false;
            }
         } catch (error) {
            set({ error: toErrorMessage(error) });
            return false;
         }
      },

      loadChatSession: async (sessionId) => {
         const ready = readyChatServiceScope(ctx);
         if (!ready) {
            return false;
         }
         const { chatService, projectId } = ready;

         try {
            // Use a dedicated flag for session/messages fetch so streaming can still use isLoading
            set({ isMessagesLoading: true, error: null });

            // Fetch session details, messages, and artifacts first.
            const [sessionResult, messagesResult, artifactsResult] =
               await Promise.all([
                  chatService.getChatSession(sessionId, projectId),
                  chatService.getChatSessionMessages(sessionId, projectId),
                  chatService.getChatSessionArtifacts(sessionId, projectId)
               ]);

            if (sessionResult.succeed && sessionResult.data) {
               const messages = messagesResult.succeed
                  ? (messagesResult.data as ChatMessage[])
                  : [];

               // Use artifacts from API if available
               const artifacts =
                  artifactsResult.succeed && artifactsResult.data
                     ? artifactsResult.data
                     : [];
               const loadedSession = sessionResult.data;

               set({
                  chatSession: loadedSession,
                  messages,
                  artifacts,
                  artifactRuntimeById: {},
                  isMessagesLoading: false,
                  error: null
               });
               return true;
            } else {
               set({
                  error:
                     sessionResult.error?.title ||
                     "Failed to load chat session",
                  isMessagesLoading: false
               });
               return false;
            }
         } catch (error) {
            set({
               error: toErrorMessage(error),
               isMessagesLoading: false
            });
            return false;
         }
      },

      deleteChatSession: async (sessionId) => {
         const ready = readyChatServiceScope(ctx);
         if (!ready) {
            return false;
         }
         const { chatService, projectId } = ready;

         try {
            set({ isMessagesLoading: true, error: null });

            const result = await chatService.deleteChatSession(
               sessionId,
               projectId
            );

            if (result.succeed) {
               const state = get();
               // Only clear active session if it's the one being deleted
               if (state.chatSession?.id === sessionId) {
                  set({
                     chatSession: null,
                     messages: [],
                     artifacts: [],
                     artifactRuntimeById: {},
                     isMessagesLoading: false
                  });
               } else {
                  set({ isMessagesLoading: false });
               }
               refreshRecentSessions();
               return true;
            } else {
               set({
                  error: result.error?.title || "Failed to delete chat session",
                  isMessagesLoading: false
               });
               return false;
            }
         } catch (error) {
            set({ error: toErrorMessage(error), isMessagesLoading: false });
            return false;
         }
      },

      setPythonExecutionApprovalMode: async (mode) => {
         const sessionId = get().chatSession?.id;
         if (!sessionId) {
            set({
               error: "Active chat session is required to update Python approval mode."
            });
            return false;
         }
         return get().updateChatSession(sessionId, {
            pythonExecutionApprovalMode: mode
         });
      },

      fetchRecentSessions: async (mySessionsOnly = false, options = {}) => {
         const { chatService, projectId } = get();
         if (!chatService || !projectId) {
            console.warn(
               "[ChatSessionStore] Chat service or project not initialized, skipping fetchRecentSessions"
            );
            return;
         }

         const requestKey = `${projectId}:${mySessionsOnly}`;
         const now = Date.now();
         const shouldUseCache =
            !options.force &&
            recentSessionsCache.key === requestKey &&
            now - recentSessionsCache.fetchedAt < RECENT_SESSIONS_CACHE_TTL_MS;

         if (shouldUseCache) {
            return;
         }

         if (
            recentSessionsCache.request &&
            recentSessionsCache.key === requestKey &&
            !options.force
         ) {
            return recentSessionsCache.request;
         }

         recentSessionsCache.key = requestKey;
         recentSessionsCache.request = (async () => {
            const result = await chatService.getFilteredChatSessions(
               projectId,
               undefined,
               1,
               SIDEBAR_RECENT_SESSIONS_LIMIT,
               mySessionsOnly
            );

            if (result.succeed && result.data) {
               recentSessionsCache.fetchedAt = Date.now();
               set({
                  recentSessions: result.data.items || [],
                  totalSessions: result.data.totalCount || 0,
                  mySessionsOnly
               });
            }
         })();

         try {
            await recentSessionsCache.request;
         } finally {
            if (recentSessionsCache.key === requestKey) {
               recentSessionsCache.request = null;
            }
         }
      },

      getFilteredChatSessions: async (
         filter,
         pageIndex,
         pageSize,
         mySessionsOnly
      ) => {
         const { chatService, projectId } = get();
         if (!chatService || !projectId) {
            return {
               succeed: false,
               error: {
                  title: "Chat service or project not initialized",
                  status: 500,
                  messages: [],
                  isAuthError: false
               }
            };
         }
         return await chatService.getFilteredChatSessions(
            projectId,
            filter,
            pageIndex,
            pageSize,
            mySessionsOnly
         );
      }
   };
}
