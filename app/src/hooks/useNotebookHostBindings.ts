import { type ChatSessionStoreApi } from "@kontext-tech/chat";
import type { ApiErrorResult } from "@kontext-tech/common";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import { useFileService } from "@kontext-tech/file";
import { useUserStore } from "@kontext-tech/identity";
import { ExecutionRunService } from "@kontext-tech/job";
import type {
   CellExecutionContext,
   CodeExecutionEngine,
   FileSystemBinding
} from "@kontext-tech/notebook";
import { DEFAULT_STORE_RESULT_THRESHOLD_ROWS } from "@kontext-tech/notebook";
import {
   QuerySessionService,
   useProjectQuerySessions
} from "@kontext-tech/query";
import type {
   CodeExecutionOutput,
   CreateQuerySessionRequest,
   QuerySessionModel,
   SessionInitRequest
} from "@kontext-tech/schema";
import { QuerySessionStatus, TriggerActorType } from "@kontext-tech/schema";
import { useMemo, useRef } from "react";

type NotebookHostCodeExecutionResult = {
   status: "success" | "error";
   outputs: CodeExecutionOutput[];
   error?: string;
   executionRunId?: string;
   executionMode?: "draft" | "persisted";
   executionTimeMs?: number;
};

type NotebookHostCellExecutionResult = {
   status: "success" | "error";
   output?: unknown;
   error?: string;
   executionRunId?: string;
   executionMode?: "draft" | "persisted";
   executionTimeMs?: number;
};

type NotebookChatScope = {
   chatSessionId: string;
   querySessionId?: string | null;
   defaultCatalogConnectionId?: string | null;
   defaultNamespace?: string | null;
   defaultEntityId?: string | null;
};

export function useNotebookHostBindings(
   projectId: string,
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>,
   chatScope?: NotebookChatScope,
   /**
    * Project-scoped chat store access. Required only for chat-scoped notebooks
    * (chatScope provided) so a notebook's query session can be linked back to
    * the active chat session.
    */
   chatSessionStore?: ChatSessionStoreApi
): {
   fileSystem: FileSystemBinding;
   executionEngine: CodeExecutionEngine;
} {
   const accessToken = useUserStore((state) => state.tokens?.accessToken);
   const fileService = useFileService(errorHandler);
   const executionRunService = useDataService(
      ExecutionRunService,
      errorHandler
   );
   const { ensureSession, executeQuery } = useProjectQuerySessions(
      projectId,
      errorHandler
   );
   // Tracks the client-generated run id per (notebook, block) so a running cell
   // can be cancelled deterministically without scanning the job-run list.
   const activeRunIdsRef = useRef<Map<string, string>>(new Map());
   const querySessionService = useMemo(() => {
      if (!accessToken) {
         return null;
      }

      return new QuerySessionService({ accessToken }, errorHandler);
   }, [accessToken, errorHandler]);

   const fileSystem = useMemo<FileSystemBinding>(
      () => ({
         uploadImage: async (
            fileOrProjectId: File | Blob | string,
            file?: File | Blob
         ) => {
            if (typeof fileOrProjectId === "string") {
               return fileService.uploadImage(
                  fileOrProjectId,
                  file ?? new Blob()
               );
            }

            return fileService.uploadImage(projectId, fileOrProjectId);
         },
         getFileUrl: (fileId: string) => fileService.getFileUrl(fileId),
         getInlineData: async (fileId: string, bindingProjectId?: string) => {
            const result = await fileService.getDataTableFile(
               fileId,
               bindingProjectId || projectId
            );

            if (!result.succeed || !result.data?.table) {
               return {
                  succeed: false,
                  error: result.error
               };
            }

            return {
               succeed: true,
               data: result.data.table
            };
         },
         downloadFile: (
            fileId: string,
            bindingProjectId?: string,
            onProgress?: (progress: number) => void
         ) =>
            fileService.downloadFile(
               fileId,
               bindingProjectId || projectId,
               onProgress
            ),
         getPaginatedImageFiles: (
            bindingProjectId?: string,
            pageIndex = 0,
            pageSize = 20,
            search = ""
         ) =>
            fileService.getPaginatedImageFiles(
               bindingProjectId || projectId,
               pageIndex,
               pageSize,
               search
            )
      }),
      [fileService, projectId]
   );

   const executionEngine = useMemo<CodeExecutionEngine>(() => {
      const normalizeScopeValue = (value?: string | null) => value ?? undefined;

      const isCompatibleChatSession = (
         session: QuerySessionModel,
         scope: NotebookChatScope
      ) =>
         (session.catalogConnectionId ?? undefined) ===
            normalizeScopeValue(scope.defaultCatalogConnectionId) &&
         (session.defaultNamespace ?? undefined) ===
            normalizeScopeValue(scope.defaultNamespace) &&
         (session.defaultEntityId ?? undefined) ===
            normalizeScopeValue(scope.defaultEntityId);

      const persistChatQuerySessionId = async (
         scope: NotebookChatScope,
         querySessionId: string
      ) => {
         if (!chatSessionStore) {
            return;
         }
         const store = chatSessionStore.getState();
         const activeChatSession = store.chatSession;

         if (activeChatSession?.id === scope.chatSessionId) {
            store.setChatSession({
               ...activeChatSession,
               querySessionId
            });
         }

         if (!store.chatService) {
            return;
         }

         const result = await store.chatService.updateChatSession(
            scope.chatSessionId,
            projectId,
            { querySessionId }
         );

         if (
            result.succeed &&
            result.data &&
            chatSessionStore.getState().chatSession?.id === scope.chatSessionId
         ) {
            chatSessionStore.getState().setChatSession(result.data);
         }
      };

      const initializeResolvedSession = async (
         session: QuerySessionModel,
         scope: NotebookChatScope
      ): Promise<QuerySessionModel | null> => {
         if (!querySessionService) {
            return null;
         }

         if (session.status === QuerySessionStatus.Active) {
            return session;
         }

         if (
            session.status !== QuerySessionStatus.Initializing ||
            !session.id
         ) {
            return null;
         }

         const request: SessionInitRequest = {
            projectId,
            sessionId: session.id,
            catalogConnectionId: normalizeScopeValue(
               scope.defaultCatalogConnectionId
            ),
            defaultNamespace: normalizeScopeValue(scope.defaultNamespace),
            defaultEntityId: normalizeScopeValue(scope.defaultEntityId),
            persistent: true
         };
         const result = await querySessionService.initializeSession(request);

         return result.succeed && result.data?.success && result.data.session
            ? result.data.session
            : null;
      };

      const createChatScopedSession = async (
         scope: NotebookChatScope
      ): Promise<QuerySessionModel | null> => {
         if (!querySessionService) {
            return null;
         }

         const createRequest: CreateQuerySessionRequest = {
            projectId,
            catalogConnectionId: normalizeScopeValue(
               scope.defaultCatalogConnectionId
            ),
            defaultNamespace: normalizeScopeValue(scope.defaultNamespace),
            defaultEntityId: normalizeScopeValue(scope.defaultEntityId),
            sessionName: "Chat Notebook Session",
            isPersistent: true
         };
         const createResult =
            await querySessionService.createSession(createRequest);

         if (!createResult.succeed || !createResult.data?.id) {
            return null;
         }

         const initializedSession = await initializeResolvedSession(
            createResult.data,
            scope
         );
         const sessionToPersist = initializedSession ?? createResult.data;

         if (sessionToPersist.id) {
            await persistChatQuerySessionId(scope, sessionToPersist.id);
         }

         return sessionToPersist;
      };

      const resolveChatScopedSession = async (
         scope: NotebookChatScope
      ): Promise<QuerySessionModel | null> => {
         if (!querySessionService) {
            return null;
         }

         if (scope.querySessionId) {
            const sessionResult = await querySessionService.getSession(
               projectId,
               scope.querySessionId
            );
            const candidate =
               sessionResult.succeed && sessionResult.data
                  ? sessionResult.data
                  : null;

            if (
               candidate &&
               isCompatibleChatSession(candidate, scope) &&
               (candidate.status === QuerySessionStatus.Active ||
                  candidate.status === QuerySessionStatus.Initializing)
            ) {
               const initialized = await initializeResolvedSession(
                  candidate,
                  scope
               );
               return initialized ?? candidate;
            }
         }

         return createChatScopedSession(scope);
      };

      const executeCell = async (
         language: string,
         code: string,
         context?: CellExecutionContext
      ): Promise<NotebookHostCellExecutionResult> => {
         if (language.toLowerCase() === "sql") {
            if (!code.trim()) {
               return {
                  status: "error",
                  error: "No SQL code to execute"
               };
            }

            const session = chatScope
               ? await resolveChatScopedSession(chatScope)
               : await ensureSession();
            if (!session?.id) {
               return {
                  status: "error",
                  error: "Unable to prepare a query session for this notebook."
               };
            }
            const { user } = useUserStore.getState();

            const triggeredByValue = context?.notebookId
               ? { type: TriggerActorType.Notebook, id: context.notebookId }
               : { type: TriggerActorType.User, id: user?.id || "unknown" };

            const result = await executeQuery(
               session.id,
               code,
               triggeredByValue,
               DEFAULT_STORE_RESULT_THRESHOLD_ROWS,
               undefined,
               true,
               chatScope?.chatSessionId,
               undefined,
               // Server-side alias binding: the response carries the block's
               // notebook-scoped alias so the chip appears immediately.
               context?.notebookId && context?.blockId
                  ? { notebookId: context.notebookId, blockId: context.blockId }
                  : undefined
            );

            if (!result) {
               return {
                  status: "error",
                  error: "Query execution failed - no response received"
               };
            }

            if (result.success === false) {
               return {
                  status: "error",
                  error: result.errorMessage || "Query execution failed",
                  executionTimeMs: result.totalExecutionTimeMs ?? undefined
               };
            }

            return {
               status: "success",
               output: {
                  dataRef: result.dataId
                     ? { dataId: result.dataId }
                     : undefined,
                  inlineData: result.result || undefined,
                  alias: result.alias || undefined
               },
               // The persisted job run id (stamped server-side into the
               // response provenance) so the block can link back to the run.
               executionRunId: result.provenance?.executionRunId ?? undefined,
               executionTimeMs: result.totalExecutionTimeMs ?? undefined
            };
         }

         if (language.toLowerCase() === "python") {
            if (!context?.notebookId || !context.blockId) {
               return {
                  status: "error",
                  error: "Notebook context is required for Python execution."
               };
            }

            const runKey = `${context.notebookId}:${context.blockId}`;
            const runId = crypto.randomUUID();
            activeRunIdsRef.current.set(runKey, runId);

            try {
               const result = await fileService.executeNotebookPythonBlock(
                  context.notebookId,
                  context.blockId,
                  projectId,
                  code,
                  runId
               );

               if (!result.succeed || !result.data) {
                  return {
                     status: "error",
                     error:
                        result.error?.messages?.[0] ||
                        result.error?.title ||
                        "Python execution failed",
                     executionMode: "draft"
                  };
               }

               return {
                  status: result.data.success ? "success" : "error",
                  output: result.data.outputs,
                  error: result.data.error || undefined,
                  executionRunId: result.data.executionRunId || runId,
                  executionMode: result.data.executionMode || undefined
               };
            } finally {
               // Only clear if this run is still the active one for the cell
               // (a newer run may have replaced it).
               if (activeRunIdsRef.current.get(runKey) === runId) {
                  activeRunIdsRef.current.delete(runKey);
               }
            }
         }

         return {
            status: "error",
            error: `${language} execution is not implemented yet.`
         };
      };

      const execute = async (
         code: string,
         context?: CellExecutionContext,
         language = "python"
      ): Promise<NotebookHostCodeExecutionResult> => {
         if (language.toLowerCase() === "sql") {
            const result = await executeCell("sql", code, context);

            if (result.status === "error") {
               return {
                  status: "error",
                  outputs: [
                     {
                        type: "text",
                        mimeType: "text/plain",
                        content: result.error || "SQL execution failed."
                     }
                  ],
                  error: result.error || "SQL execution failed.",
                  executionTimeMs: result.executionTimeMs
               };
            }

            return {
               status: "success",
               outputs: [
                  {
                     type: "text",
                     mimeType: "text/plain",
                     content: "SQL cell executed successfully."
                  }
               ],
               executionTimeMs: result.executionTimeMs
            };
         }

         if (language.toLowerCase() === "python") {
            const result = await executeCell("python", code, context);
            const outputs = Array.isArray(result.output)
               ? (result.output as CodeExecutionOutput[])
               : [];

            return {
               status: result.status,
               outputs:
                  outputs.length > 0
                     ? outputs
                     : result.error
                       ? [
                            {
                               type: "text",
                               mimeType: "text/plain",
                               content: result.error
                            }
                         ]
                       : [],
               error: result.error,
               executionRunId: result.executionRunId,
               executionMode: result.executionMode,
               executionTimeMs: result.executionTimeMs
            };
         }

         const nextError = `${language} execution is not implemented yet.`;
         return {
            status: "error",
            outputs: [
               {
                  type: "text",
                  mimeType: "text/plain",
                  content: nextError
               }
            ],
            error: nextError
         };
      };

      const cancelExecution = async (
         context?: CellExecutionContext
      ): Promise<boolean> => {
         if (!context?.blockId || !context.notebookId) {
            return false;
         }

         const runKey = `${context.notebookId}:${context.blockId}`;
         const runId = activeRunIdsRef.current.get(runKey);
         if (!runId) {
            return false;
         }

         const cancelResult = await executionRunService.cancelRun(
            runId,
            projectId
         );
         return cancelResult.succeed;
      };

      return {
         execute,
         executeCell,
         cancelExecution
      };
   }, [
      chatScope,
      chatSessionStore,
      ensureSession,
      executeQuery,
      fileService,
      executionRunService,
      projectId,
      querySessionService
   ]);

   return {
      fileSystem,
      executionEngine
   };
}
