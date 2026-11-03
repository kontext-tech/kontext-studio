import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult } from "@kontext-tech/common";
import { ServiceContainer } from "@kontext-tech/common/container";
import type {
   Artifact,
   ChatMessage,
   ChatSessionModel,
   PaginatedChatSessionResponse,
   PythonExecutionApprovalMode,
   ProjectModel,
   SimpleRunEvent,
   ToolCall,
   UpdateChatSessionRequest
} from "@kontext-tech/schema";
import { createContext, useContext } from "react";
import { createStore, useStore, type StoreApi } from "zustand";
import { devtools } from "zustand/middleware";
import { ChatService } from "../ChatService";
import type { ArtifactRuntimeEntry } from "./artifactRuntimeReducer";
import type { ChatSessionService } from "../types/chatSessionService";
import { reduceArtifactRemoval } from "./artifactActions";
import { appendHistory, navigateHistory } from "./messageHistory";
import type { StoreContext } from "./storeContextTypes";
import { createSessionActions } from "./sessionActions";
import { createSendMessage } from "./sendMessage";

export interface ChatSessionState {
   // State
   messages: ChatMessage[];
   isLoading: boolean;
   error: string | null;
   chatSession: ChatSessionModel | null;
   messageHistory: string[];
   historyIndex: number;
   artifacts: Artifact[];
   artifactRuntimeById: Record<string, ArtifactRuntimeEntry>;
   activeArtifactId: string | null;
   isSidebarOpen: boolean;
   // Recent chat sessions for the project
   recentSessions: ChatSessionModel[];
   totalSessions: number;
   // Selected model selection for the project/session
   modelSelectionId?: string;
   // Current project ID
   projectId?: string;
   // Whether messages/session are currently being loaded from the server
   isMessagesLoading: boolean;
   // Whether to show only current user's sessions
   mySessionsOnly: boolean;

   // Configured chat service instance
   chatService: ChatSessionService | null;

   // Actions
   addMessage: (message: ChatMessage) => void;
   updateMessage: (messageId: string, updates: Partial<ChatMessage>) => void;
   clearMessages: () => void;
   setLoading: (loading: boolean) => void;
   setError: (error: string | null) => void;
   setChatSession: (session: ChatSessionModel | null) => void;
   clearActiveSession: () => void;
   setModelSelectionId: (modelSelectionId: string | undefined) => void;

   // Chat service management
   /**
    * Initialize the chat service for API-based operations.
    * Creates a ChatService instance configured with auth context.
    */
   initializeChatService: (
      project: ProjectModel,
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => void;
   /**
    * Set a custom chat service implementation.
    */
   setChatService: (service: ChatSessionService | null) => void;

   // Artifact actions
   removeArtifact: (artifactId: string) => void;
   clearArtifacts: () => void;
   setActiveArtifact: (artifactId: string | null) => void;
   setSidebarOpen: (open: boolean) => void;

   // Message history
   addToHistory: (message: string) => void;
   navigateHistory: (direction: "up" | "down") => string | null;

   // Session management
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

   // Message sending
   sendMessage: (
      message: string,
      options?: {
         onRunPaused?: (
            event: SimpleRunEvent
         ) => Promise<ToolCall | ToolCall[] | void>;
      }
   ) => Promise<void>;

   // Reset
   reset: () => void;

   // Fetch recent sessions
   fetchRecentSessions: (
      mySessionsOnly?: boolean,
      options?: {
         force?: boolean;
      }
   ) => Promise<void>;
   getFilteredChatSessions: (
      filter?: string,
      pageIndex?: number,
      pageSize?: number,
      mySessionsOnly?: boolean
   ) => Promise<ApiResult<PaginatedChatSessionResponse>>;
}

const initialState = {
   messages: [],
   isLoading: false,
   isMessagesLoading: false,
   error: null,
   chatSession: null,
   messageHistory: [],
   historyIndex: -1,
   artifacts: [],
   artifactRuntimeById: {},
   activeArtifactId: null,
   isSidebarOpen: false,
   recentSessions: [],
   totalSessions: 0,
   mySessionsOnly: false,
   modelSelectionId: undefined,
   projectId: undefined,
   chatService: null as ChatSessionService | null
};

export type ChatSessionStoreApi = StoreApi<ChatSessionState>;

/**
 * Shared reset slices for the "start over" actions, composed below so the
 * paths can never silently drift apart as new state is added.
 */
const clearedBlocks = () => ({
   messages: [],
   artifacts: [],
   artifactRuntimeById: {},
   activeArtifactId: null
});

const clearedHistory = () => ({
   messageHistory: [],
   historyIndex: -1
});

/**
 * Creates a chat session store instance for one project.
 *
 * The store owns no project-scoping logic itself: state lives exactly as long
 * as the instance that holds it. Consumers get the instance from
 * {@link ChatSessionStoreProvider} (mounted per project in the app layout), so
 * switching projects swaps in a fresh store instead of reaching a global reset
 * action.
 */
export function createChatSessionStore(): ChatSessionStoreApi {
   return createStore<ChatSessionState>()(
      devtools(
         (set, get) => {
            const chatServiceContainer = new ServiceContainer();

            // Shared store context handed to the extracted action factories.
            const ctx: StoreContext = {
               get: get as StoreContext["get"],
               set: set as StoreContext["set"],
               recentSessionsCache: {
                  request: null,
                  key: null,
                  fetchedAt: 0
               }
            };

            const sessionActions = createSessionActions(ctx);
            const sendMessage = createSendMessage(ctx);

            return {
               ...initialState,

               // Basic state setters
               addMessage: (message) =>
                  set((state) => ({
                     messages: [...state.messages, message]
                  })),
               updateMessage: (messageId, updates) =>
                  set((state) => ({
                     messages: state.messages.map((msg) =>
                        msg.id === messageId ? { ...msg, ...updates } : msg
                     )
                  })),
               clearMessages: () =>
                  set(() => ({
                     ...clearedBlocks(),
                     isLoading: false,
                     isMessagesLoading: false,
                     error: null,
                     isSidebarOpen: false
                     // Keep chatSession and the typed-input history.
                  })),
               setLoading: (loading) => set({ isLoading: loading }),
               setError: (error) => set({ error }),
               setChatSession: (chatSession) => set({ chatSession }),
               setModelSelectionId: (modelSelectionId) =>
                  set({ modelSelectionId }),

               // Chat service management
               initializeChatService: (project, authContext, errorHandler) => {
                  if (!project.id) {
                     set({
                        error: "Project must have an id to initialize API-based chat service"
                     });
                     return;
                  }
                  chatServiceContainer.setAuthContext(authContext);
                  chatServiceContainer.setErrorHandler(errorHandler);
                  const service = chatServiceContainer.getOrCreate(
                     `chat-service:${project.id}`,
                     (c) =>
                        new ChatService(
                           c.createAuthContext(),
                           c.getErrorHandler()
                        )
                  );
                  set({ chatService: service, projectId: project.id });
               },
               setChatService: (service) => set({ chatService: service }),

               // Artifact management
               removeArtifact: (artifactId) =>
                  set((state) => reduceArtifactRemoval(state, artifactId)),
               clearArtifacts: () =>
                  set({
                     artifacts: [],
                     artifactRuntimeById: {},
                     activeArtifactId: null,
                     isSidebarOpen: false
                  }),
               setActiveArtifact: (activeArtifactId) =>
                  set({ activeArtifactId }),
               setSidebarOpen: (isSidebarOpen) => set({ isSidebarOpen }),

               // Message history management
               addToHistory: (message) =>
                  set((state) => appendHistory(state.messageHistory, message)),
               navigateHistory: (direction) => {
                  const state = get();
                  const result = navigateHistory(
                     state.messageHistory,
                     state.historyIndex,
                     direction
                  );
                  if (result.index !== state.historyIndex) {
                     set({ historyIndex: result.index });
                  }
                  return result.message;
               },

               // Session management (delegated to sessionActions factory)
               createChatSession: sessionActions.createChatSession,
               updateChatSession: sessionActions.updateChatSession,
               loadChatSession: sessionActions.loadChatSession,
               deleteChatSession: sessionActions.deleteChatSession,
               setPythonExecutionApprovalMode:
                  sessionActions.setPythonExecutionApprovalMode,

               // Message sending
               sendMessage,

               reset: () =>
                  set(() => ({
                     ...initialState,
                     ...clearedBlocks(),
                     ...clearedHistory(),
                     recentSessions: []
                     // Always fresh instances so no later mutation can leak
                     // into the shared initial snapshot.
                  })),

               fetchRecentSessions: sessionActions.fetchRecentSessions,
               getFilteredChatSessions: sessionActions.getFilteredChatSessions,
               clearActiveSession: () => {
                  set((state) => ({
                     chatSession: null,
                     ...clearedBlocks(),
                     ...clearedHistory(),
                     error: null,
                     isMessagesLoading: false,
                     modelSelectionId: state.modelSelectionId
                  }));
               }
            };
         },
         {
            name: "ChatSessionStore"
         }
      )
   );
}

export const ChatSessionStoreContext =
   createContext<ChatSessionStoreApi | null>(null);

const selectFullState = (state: ChatSessionState) => state;

/**
 * React hook bound to the project-scoped chat session store.
 *
 * Must be used inside a {@link ChatSessionStoreProvider}. Accepts an optional
 * zustand selector; omitting it subscribes to the whole state (identical to
 * the legacy module-singleton hook).
 */
export function useChatSessionStore<T = ChatSessionState>(
   selector?: (state: ChatSessionState) => T
): T {
   const store = useChatSessionStoreApi();
   return useStore(
      store,
      (selector ?? selectFullState) as (state: ChatSessionState) => T
   );
}

/**
 * Access the project-scoped store instance itself (`getState`/`setState` for
 * imperative reads and writes, e.g. inside callbacks). Must be used inside a
 * {@link ChatSessionStoreProvider}.
 */
export function useChatSessionStoreApi(): ChatSessionStoreApi {
   const store = useContext(ChatSessionStoreContext);
   if (!store) {
      throw new Error(
         "useChatSessionStore must be used within a ChatSessionStoreProvider"
      );
   }
   return store;
}
