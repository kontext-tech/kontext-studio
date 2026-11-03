import type { ApiErrorResult } from "@kontext-labs/common";
import { useFileService, useFileWorkflow } from "@kontext-labs/file";
import { useUserStore } from "@kontext-labs/identity";
import {
   type NotebookDocument,
   useNotebookFileHelpers,
   useNotebookStore
} from "@kontext-labs/notebook";
import { createPythonHitlResolver } from "./pythonHitl";
import {
   type PendingPythonExecutionRequest,
   ProjectFeature,
   type Artifact,
   type ChatSessionModel,
   type CodeBlock,
   type PythonExecutionApprovalMode,
   type ProjectModel,
   type SimpleRunEvent,
   type UpdateChatSessionRequest
} from "@kontext-labs/schema";
import { useCallback, useEffect, useMemo } from "react";
import { useShallow } from "zustand/react/shallow";
import {
   useChatSessionStore,
   useChatSessionStoreApi
} from "./stores/chatSessionStore";
import type { ChatMessage } from "./types/chat";
import {
   persistRememberedPythonApprovalMode,
   type PythonExecutionApprovalDecision
} from "./hooks/usePythonExecutionApprovalModal";

function isChatAvailable(project: ProjectModel): boolean {
   const featureEnabled =
      project.configuration?.features?.includes(ProjectFeature.Chat) ?? true;
   return featureEnabled && !!project.id;
}

export interface UseChatOptions {
   sessionId?: string;
   modelSelectionId?: string;
   pythonExecutionApprovalMode?: PythonExecutionApprovalMode;
   requestPythonExecutionApproval?: (
      request: PendingPythonExecutionRequest
   ) => Promise<PythonExecutionApprovalDecision>;
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>;
}

export interface UseChatReturn {
   messages: ChatMessage[];
   isLoading: boolean;
   isMessagesLoading: boolean;
   error: string | null;
   messageHistory: string[];
   historyIndex: number;
   chatSession: ChatSessionModel | null;
   artifacts: Artifact[];
   isSidebarOpen: boolean;
   sendMessage: (message: string) => Promise<void>;
   navigateHistory: (direction: "up" | "down") => string | null;
   clearMessages: () => void;
   addMessage: (message: ChatMessage) => void;
   updateMessage: (messageId: string, updates: Partial<ChatMessage>) => void;
   isAvailable: boolean;
   isOwner: boolean;
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
      updates: string | UpdateChatSessionRequest
   ) => Promise<boolean>;
   loadChatSession: (sessionId: string) => Promise<boolean>;
   deleteChatSession: (sessionId: string) => Promise<boolean>;
   setPythonExecutionApprovalMode: (
      mode: PythonExecutionApprovalMode
   ) => Promise<boolean>;
   clearArtifacts: () => void;
   removeArtifact: (artifactId: string) => void;
   setActiveArtifact: (artifactId: string | null) => void;
   setSidebarOpen: (open: boolean) => void;
   setModelSelectionId: (modelSelectionId: string | undefined) => void;
}

export function useChat(
   project: ProjectModel,
   options?: UseChatOptions
): UseChatReturn {
   const {
      sessionId,
      modelSelectionId,
      pythonExecutionApprovalMode,
      requestPythonExecutionApproval,
      errorHandler
   } = options || {};

   const store = useChatSessionStore(
      useShallow((state) => ({
         // Data slices read by the hook's render output. Actions stay
         // individually selected below (stable references, no re-renders);
         // subscribing to the whole state here would re-render on every
         // unrelated mutation.
         messages: state.messages,
         isLoading: state.isLoading,
         error: state.error,
         chatSession: state.chatSession,
         messageHistory: state.messageHistory,
         historyIndex: state.historyIndex,
         artifacts: state.artifacts,
         isSidebarOpen: state.isSidebarOpen,
         isMessagesLoading: state.isMessagesLoading
      }))
   );
   const storeApi = useChatSessionStoreApi();
   const clearActiveSessionMethod = useChatSessionStore(
      (state) => state.clearActiveSession
   );
   const fileWorkflow = useFileWorkflow({
      projectId: project.id
   });
   const fileService = useFileService(errorHandler);
   const { saveNotebook } = useNotebookFileHelpers(fileWorkflow);
   const navigateHistory = useChatSessionStore(
      (state) => state.navigateHistory
   );
   const clearMessages = useChatSessionStore((state) => state.clearMessages);
   const addMessage = useChatSessionStore((state) => state.addMessage);
   const updateMessage = useChatSessionStore((state) => state.updateMessage);
   const clearArtifacts = useChatSessionStore((state) => state.clearArtifacts);
   const removeArtifact = useChatSessionStore((state) => state.removeArtifact);
   const setActiveArtifact = useChatSessionStore(
      (state) => state.setActiveArtifact
   );
   const setSidebarOpen = useChatSessionStore((state) => state.setSidebarOpen);
   const setModelSelectionId = useChatSessionStore(
      (state) => state.setModelSelectionId
   );
   const sendMessageMethod = useChatSessionStore((state) => state.sendMessage);
   const createChatSessionMethod = useChatSessionStore(
      (state) => state.createChatSession
   );
   const updateChatSessionMethod = useChatSessionStore(
      (state) => state.updateChatSession
   );
   const setPythonExecutionApprovalModeMethod = useChatSessionStore(
      (state) => state.setPythonExecutionApprovalMode
   );
   const loadChatSessionMethod = useChatSessionStore(
      (state) => state.loadChatSession
   );
   const deleteChatSessionMethod = useChatSessionStore(
      (state) => state.deleteChatSession
   );

   const user = useUserStore((state) => state.user);
   const isOwner = useMemo(() => {
      if (!store.chatSession?.ownerId || !user?.id) {
         return true;
      }

      return store.chatSession.ownerId === user.id;
   }, [store.chatSession, user]);

   useEffect(() => {
      // The provider owns service initialization (per-project store instance);
      // here we only sync an optional per-page model selection into the store.
      if (modelSelectionId !== undefined) {
         setModelSelectionId(modelSelectionId);
      }
   }, [modelSelectionId, setModelSelectionId]);

   useEffect(() => {
      if (project.id && !sessionId) {
         clearActiveSessionMethod();
      }
   }, [project.id, sessionId, clearActiveSessionMethod]);

   const onRunPaused = useCallback(
      async (event: SimpleRunEvent) => {
         const hitl = createPythonHitlResolver({
            approvalMode: pythonExecutionApprovalMode,
            getCurrentApprovalMode: () =>
               storeApi.getState().chatSession?.pythonExecutionApprovalMode,
            requestApproval: requestPythonExecutionApproval,
            onAutoApproveFutureRuns: (mode) => {
               persistRememberedPythonApprovalMode(mode);
               void setPythonExecutionApprovalModeMethod(mode);
            },
            executeSessionPython: (code) => {
               const activeChatService = storeApi.getState().chatService;
               const activeSessionId =
                  storeApi.getState().chatSession?.id || sessionId;
               if (!activeChatService || !activeSessionId) {
                  return Promise.reject(
                     new Error("Chat session is not ready for Python execution")
                  );
               }
               return activeChatService.executePythonScript(
                  activeSessionId,
                  project.id,
                  { code }
               );
            },
            executeNotebookPython: (notebookId, blockId, code) =>
               fileService.executeNotebookPythonBlock(
                  notebookId,
                  blockId,
                  project.id,
                  code
               ),
            saveNotebook: async (notebookId, document) => {
               await saveNotebook(notebookId, document as NotebookDocument);
            },
            notebook: {
               getCodeBlock: (blockId, instanceId) =>
                  useNotebookStore.getState().getCodeBlock(blockId, instanceId),
               markBlockExecuting: (blockId, instanceId) =>
                  useNotebookStore
                     .getState()
                     .updateBlockData<CodeBlock>(
                        blockId,
                        { isExecuting: true, outputs: [] },
                        instanceId,
                        { markDirty: false }
                     ),
               writeOutputs: (blockId, instanceId, outputs) =>
                  useNotebookStore.getState().updateBlockData<CodeBlock>(
                     blockId,
                     {
                        outputs:
                           outputs as unknown as CodeBlock["data"]["outputs"],
                        isExecuting: false
                     },
                     instanceId,
                     { markDirty: false }
                  ),
               markFailureTextOutput: (blockId, instanceId, message) =>
                  useNotebookStore.getState().updateBlockData<CodeBlock>(
                     blockId,
                     {
                        isExecuting: false,
                        outputs: [
                           {
                              type: "text",
                              mimeType: "text/plain",
                              content: message
                           }
                        ]
                     },
                     instanceId,
                     { markDirty: false }
                  ),
               getDocument: (instanceId) =>
                  useNotebookStore.getState().getInstanceState(instanceId)
                     ?.document
            }
         });

         return await hitl(event);
      },
      [
         fileService,
         project.id,
         pythonExecutionApprovalMode,
         requestPythonExecutionApproval,
         saveNotebook,
         sessionId,
         setPythonExecutionApprovalModeMethod,
         storeApi
      ]
   );

   const sendMessage = useCallback(
      async (message: string) => {
         await sendMessageMethod(message, { onRunPaused });
      },
      [sendMessageMethod, onRunPaused]
   );

   const createChatSession = useCallback(
      async (
         sessionName: string,
         modelSelectionIdParam?: string,
         scope?: {
            defaultCatalogConnectionId?: string;
            defaultNamespace?: string;
            defaultEntityId?: string;
            pythonExecutionApprovalMode?: PythonExecutionApprovalMode;
         }
      ) => {
         if (!project.id) {
            throw new Error("Project ID is required to create a chat");
         }

         const session = await createChatSessionMethod(
            sessionName,
            modelSelectionIdParam || modelSelectionId,
            scope
         );

         if (session) {
            setModelSelectionId(modelSelectionIdParam || modelSelectionId);
         }

         return session;
      },
      [
         createChatSessionMethod,
         modelSelectionId,
         project.id,
         setModelSelectionId
      ]
   );

   const updateChatSession = useCallback(
      async (updates: string | UpdateChatSessionRequest) => {
         const currentSession = storeApi.getState().chatSession;
         if (!currentSession) {
            throw new Error("No active chat to update");
         }

         if (!project.id) {
            throw new Error("No project ID available");
         }

         return updateChatSessionMethod(
            currentSession.id,
            typeof updates === "string" ? { sessionName: updates } : updates
         );
      },
      [project.id, storeApi, updateChatSessionMethod]
   );

   const loadChatSession = useCallback(
      async (sessionIdValue: string) => {
         if (!project.id) {
            throw new Error("Project ID is required to load a chat");
         }

         return loadChatSessionMethod(sessionIdValue);
      },
      [loadChatSessionMethod, project.id]
   );

   const deleteChatSession = useCallback(
      async (sessionIdValue: string) => {
         if (!project.id) {
            throw new Error("Project ID is required to delete a chat");
         }

         return deleteChatSessionMethod(sessionIdValue);
      },
      [deleteChatSessionMethod, project.id]
   );

   const setPythonExecutionApprovalMode = useCallback(
      async (mode: PythonExecutionApprovalMode) => {
         return setPythonExecutionApprovalModeMethod(mode);
      },
      [setPythonExecutionApprovalModeMethod]
   );

   return {
      messages: store.messages,
      isLoading: store.isLoading,
      error: store.error,
      chatSession: store.chatSession,
      messageHistory: store.messageHistory,
      historyIndex: store.historyIndex,
      artifacts: store.artifacts,
      isSidebarOpen: store.isSidebarOpen,
      sendMessage,
      navigateHistory,
      clearMessages,
      addMessage,
      updateMessage,
      createChatSession,
      updateChatSession,
      loadChatSession,
      deleteChatSession,
      setPythonExecutionApprovalMode,
      clearArtifacts,
      removeArtifact,
      setActiveArtifact,
      setSidebarOpen,
      setModelSelectionId,
      isAvailable: isChatAvailable(project),
      isOwner,
      isMessagesLoading: store.isMessagesLoading
   };
}
