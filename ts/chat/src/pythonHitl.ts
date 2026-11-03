/**
 * Python HITL (human-in-the-loop) control flow for externally-executed tools.
 *
 * Framework-free: `useChat` composes the ports (chat service, notebook store,
 * approval modal) and this module owns the decision/execution logic —
 * approval resolution, tool-output shaping, and notebook-state updates.
 */

import { notebookInstanceId } from "@kontext-labs/common";
import {
   AgentToolNames,
   type PendingPythonExecutionRequest,
   type PythonExecutionApprovalMode,
   type PythonExecutionResult,
   type RunPausedEventData,
   type SimpleRunEvent,
   type ToolCall
} from "@kontext-labs/schema";

import { isExternalExecutionTool } from "./utils/toolNameUtils";

export interface PythonHitlExecutionOutcome {
   succeed: boolean;
   data?: PythonExecutionResult;
   error?: { title?: string; messages?: string[] };
}

export interface NotebookHitlPort {
   getCodeBlock(
      blockId: string,
      instanceId: string
   ): { data?: { code?: string } } | undefined;
   markBlockExecuting(blockId: string, instanceId: string): void;
   writeOutputs(blockId: string, instanceId: string, outputs: unknown[]): void;
   markFailureTextOutput(
      blockId: string,
      instanceId: string,
      message: string
   ): void;
   getDocument(instanceId: string): unknown;
}

export interface PythonHitlPorts {
   /** Approval mode pinned for *new* sessions (pre-creation). */
   approvalMode?: PythonExecutionApprovalMode;
   /** Approval mode of the active session (from the chat store). */
   getCurrentApprovalMode?: () => PythonExecutionApprovalMode | undefined;
   requestApproval?: (request: PendingPythonExecutionRequest) => Promise<{
      approved: boolean;
      reason?: string;
      autoApproveFutureRuns?: boolean;
   }>;
   onAutoApproveFutureRuns?: (mode: PythonExecutionApprovalMode) => void;
   executeSessionPython: (code: string) => Promise<PythonHitlExecutionOutcome>;
   executeNotebookPython: (
      notebookId: string,
      blockId: string,
      /**
       * Code override for a draft run. When undefined, the stored block is
       * executed and the backend records its execution state on the notebook.
       */
      code: string | undefined
   ) => Promise<PythonHitlExecutionOutcome>;
   saveNotebook: (notebookId: string, document: unknown) => Promise<void>;
   notebook: NotebookHitlPort;
}

function buildRejectedToolOutput({
   toolCallId,
   toolName,
   targetType,
   reason
}: {
   toolCallId?: string | null;
   toolName?: string | null;
   targetType: "notebook" | "session";
   reason?: string;
}): ToolCall {
   return {
      toolCallId,
      toolName,
      toolCallError: reason || "Python execution rejected by user.",
      result: {
         type: "python_execution",
         success: false,
         message: "Python execution rejected by user.",
         error: reason || "Python execution rejected by user.",
         targetType,
         outputs: []
      }
   };
}

function buildExecutionFailureToolOutput({
   toolCallId,
   toolName,
   targetType,
   errorMessage
}: {
   toolCallId?: string | null;
   toolName?: string | null;
   targetType: "notebook" | "session";
   errorMessage: string;
}): ToolCall {
   return {
      toolCallId,
      toolName,
      toolCallError: errorMessage,
      result: {
         type: "python_execution",
         success: false,
         message: "Execution failed",
         error: errorMessage,
         targetType,
         outputs: []
      }
   };
}

function executionErrorMessage(outcome: PythonHitlExecutionOutcome): string {
   return (
      outcome.error?.messages?.[0] ||
      outcome.error?.title ||
      "Python execution failed"
   );
}

function buildSuccessToolOutput(
   toolCallId: string | undefined,
   toolName: string | undefined,
   data: PythonExecutionResult
): ToolCall {
   return {
      toolCallId,
      toolName,
      ...(data.success ? {} : { toolCallError: data.error || data.message }),
      result: data
   };
}

/**
 * Builds the `onRunPaused` handler: resolves approval for each externally
 * executed tool call, runs it through the injected execution ports, and
 * returns tool outputs for the resume round-trip.
 */
export function createPythonHitlResolver(
   ports: PythonHitlPorts
): (event: SimpleRunEvent) => Promise<ToolCall[] | void> {
   const {
      approvalMode,
      getCurrentApprovalMode,
      requestApproval,
      onAutoApproveFutureRuns,
      executeSessionPython,
      executeNotebookPython,
      saveNotebook,
      notebook
   } = ports;

   const askForApproval = async (
      request: PendingPythonExecutionRequest
   ): Promise<{
      approved: boolean;
      reason?: string;
   }> => {
      // Never fall back to a globally-remembered mode: the persisted value is
      // a composer default, and the approval checkbox is scoped "in this chat".
      // With no active session mode, default to asking.
      const mode = approvalMode || getCurrentApprovalMode?.() || "always_ask";

      if (mode === "auto_approve") {
         return { approved: true };
      }

      if (!requestApproval) {
         return {
            approved: false,
            reason: "Python execution approval UI is not available."
         };
      }

      const decision = await requestApproval(request);
      if (decision.approved && decision.autoApproveFutureRuns) {
         onAutoApproveFutureRuns?.("auto_approve");
      }
      return decision;
   };

   const resolveSessionExecution = async (
      toolCallId: string | undefined,
      toolName: string | undefined,
      args: Record<string, unknown>
   ): Promise<ToolCall> => {
      const code = args?.code as string | undefined;
      if (!code?.trim()) {
         return {
            toolCallId,
            toolName,
            toolCallError: "Missing code parameter"
         };
      }

      const approval = await askForApproval({
         toolCallId,
         toolName: toolName || AgentToolNames.executePythonScript,
         targetType: "session",
         code
      });
      if (!approval.approved) {
         return buildRejectedToolOutput({
            toolCallId,
            toolName,
            targetType: "session",
            reason: approval.reason
         });
      }

      try {
         const result = await executeSessionPython(code);
         if (!result.succeed || !result.data) {
            return buildExecutionFailureToolOutput({
               toolCallId,
               toolName,
               targetType: "session",
               errorMessage: executionErrorMessage(result)
            });
         }
         return buildSuccessToolOutput(toolCallId, toolName, result.data);
      } catch (error) {
         return buildExecutionFailureToolOutput({
            toolCallId,
            toolName,
            targetType: "session",
            errorMessage: error instanceof Error ? error.message : String(error)
         });
      }
   };

   const resolveNotebookExecution = async (
      toolCallId: string | undefined,
      toolName: string | undefined,
      args: Record<string, unknown>
   ): Promise<ToolCall> => {
      const blockId = args?.block_id as string | undefined;
      const notebookId = args?.notebook_id as string | undefined;
      const codeOverride = args?.code as string | undefined;
      // A blank override means "execute the stored block" — it must NOT be
      // passed as a codeOverride, or the backend treats the run as a draft
      // and skips recording the block's execution state.
      const hasOverride =
         typeof codeOverride === "string" && codeOverride.trim().length > 0;

      if (!notebookId) {
         return {
            toolCallId,
            toolName,
            toolCallError: "Missing notebook_id parameter"
         };
      }
      if (!blockId) {
         return {
            toolCallId,
            toolName,
            toolCallError: "Missing block_id parameter"
         };
      }

      const instanceId = notebookInstanceId(notebookId);
      const block = notebook.getCodeBlock(blockId, instanceId);
      const code = hasOverride ? codeOverride : block?.data?.code;

      if (!code) {
         return {
            toolCallId,
            toolName,
            toolCallError: `Cannot find the code block for id ${blockId}`
         };
      }

      const approval = await askForApproval({
         toolCallId,
         toolName: toolName || AgentToolNames.executePythonCode,
         targetType: "notebook",
         code,
         notebookId,
         blockId
      });
      if (!approval.approved) {
         return buildRejectedToolOutput({
            toolCallId,
            toolName,
            targetType: "notebook",
            reason: approval.reason
         });
      }

      try {
         notebook.markBlockExecuting(blockId, instanceId);

         const result = await executeNotebookPython(
            notebookId,
            blockId,
            hasOverride ? codeOverride : undefined
         );

         if (!result.succeed || !result.data) {
            throw new Error(executionErrorMessage(result));
         }

         notebook.writeOutputs(blockId, instanceId, result.data.outputs ?? []);

         // When the backend already recorded the block's execution state
         // (persisted mode: a stored-block run with no override), it is the
         // source of truth — skip the client-side document save so a possibly
         // stale local document cannot overwrite the server state.
         const executionMode = (
            result.data as { executionMode?: string } | undefined
         )?.executionMode;
         if (executionMode !== "persisted") {
            const document = notebook.getDocument(instanceId);
            if (document) {
               try {
                  await saveNotebook(notebookId, document);
               } catch (saveError) {
                  console.error(
                     "Failed to persist notebook execution result:",
                     saveError
                  );
               }
            }
         }

         return buildSuccessToolOutput(toolCallId, toolName, result.data);
      } catch (error) {
         const errorMessage =
            error instanceof Error ? error.message : String(error);
         notebook.markFailureTextOutput(blockId, instanceId, errorMessage);
         return buildExecutionFailureToolOutput({
            toolCallId,
            toolName,
            targetType: "notebook",
            errorMessage
         });
      }
   };

   const resolvePausedToolCall = async (
      toolCall: ToolCall
   ): Promise<ToolCall> => {
      const toolCallId = toolCall.toolCallId ?? undefined;
      const toolName = toolCall.toolName ?? undefined;
      const args = toolCall.toolArgs as Record<string, unknown>;

      if (!isExternalExecutionTool(toolName)) {
         return {
            toolCallId,
            toolName,
            toolCallError: `Unsupported external tool: ${toolName}`
         };
      }

      if (toolName === AgentToolNames.executePythonScript) {
         return resolveSessionExecution(toolCallId, toolName, args);
      }
      return resolveNotebookExecution(toolCallId, toolName, args);
   };

   return async (event: SimpleRunEvent) => {
      const pauseData = event.eventData as RunPausedEventData;
      if (!pauseData?.toolCalls || pauseData.toolCalls.length === 0) {
         return;
      }

      return await Promise.all(pauseData.toolCalls.map(resolvePausedToolCall));
   };
}
