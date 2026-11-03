import { isDelegationTool } from "../utils/toolNameUtils";
import { RunEvent } from "@kontext-labs/schema";
import type {
   ArtifactEventData,
   ChatMessage,
   ChatToolCallSegment,
   RunPausedEventData,
   SimpleRunEvent,
   ToolCall,
   ToolCallCompletedEventData,
   ToolCallStartedEventData
} from "@kontext-labs/schema";
import type { StoreContext } from "./storeContextTypes";
import { reduceArtifactEvent } from "./artifactRuntimeReducer";
import {
   isReasoningSegment,
   isTextSegment,
   isToolCallSegment
} from "../types/chat";
import {
   createErrorSegment,
   createReasoningSegment,
   createTextSegment
} from "./messageSegments";

export type SendMessage = (
   message: string,
   options?: {
      onRunPaused?: (
         event: SimpleRunEvent
      ) => Promise<ToolCall | ToolCall[] | void>;
   }
) => Promise<void>;

/**
 * Builds the `sendMessage` streaming action against the provided store context.
 */
export function createSendMessage(ctx: StoreContext): SendMessage {
   const { get, set } = ctx;

   return async (message, options) => {
      if (!message.trim()) {
         return;
      }

      const trimmedMessage = message.trim();
      const state = get();

      // Add to history
      state.addToHistory(trimmedMessage);

      // Add user message to chat
      const userMessage: ChatMessage = {
         id: `user-${Date.now()}`,
         type: "user",
         segments: [createTextSegment(trimmedMessage)],
         status: "completed"
      };

      state.addMessage(userMessage);

      // Add initial loading message for AI response
      const aiMessageId = `ai-${Date.now()}`;
      const loadingMessage: ChatMessage = {
         id: aiMessageId,
         type: "assistant",
         status: "loading",
         segments: []
      };

      state.addMessage(loadingMessage);
      state.setLoading(true);

      try {
         const { chatService, projectId, chatSession } = get();
         if (!chatService) {
            throw new Error(
               "Chat service not initialized.  Call initializeChatService first."
            );
         }
         if (!projectId) {
            throw new Error("Project not initialized");
         }

         const sessionId = chatSession?.id;
         if (!sessionId) {
            throw new Error(
               "Chat session is required to send messages. Please create a session first."
            );
         }

         let nextToolOutputs: ToolCall[] | undefined = undefined;
         let nextRunId: string | undefined = undefined;
         let iteration = 0;

         const getAiMessage = () =>
            get().messages.find((m: ChatMessage) => m.id === aiMessageId);

         const ensureStreamingStatus = () => {
            const current = getAiMessage();
            if (current?.status === "loading") {
               state.updateMessage(aiMessageId, {
                  status: "streaming"
               });
            }
         };

         const updateAiSegments = (segments: ChatMessage["segments"]) => {
            state.updateMessage(aiMessageId, { segments });
         };

         // Stack of tool call IDs that are currently "open" for delegation
         const delegationStack: string[] = [];

         const handleRunContent = (event: SimpleRunEvent) => {
            const currentMessage = getAiMessage();
            if (!currentMessage) {
               return;
            }

            const parentId =
               delegationStack.length > 0
                  ? delegationStack[delegationStack.length - 1]
                  : undefined;

            const newContent = event.content || "";
            const reasoningContent = event.reasoning || "";

            if (!newContent && !reasoningContent) return;

            const result = [...currentMessage.segments];

            if (newContent) {
               const last = result[result.length - 1];
               if (last && isTextSegment(last) && last.parentId === parentId) {
                  result[result.length - 1] = {
                     ...last,
                     content: last.content + newContent
                  };
               } else {
                  result.push(
                     createTextSegment(newContent, undefined, parentId)
                  );
               }
            }

            if (reasoningContent) {
               const last = result[result.length - 1];
               if (
                  last &&
                  isReasoningSegment(last) &&
                  last.parentId === parentId
               ) {
                  result[result.length - 1] = {
                     ...last,
                     content: last.content + reasoningContent
                  };
               } else {
                  result.push(
                     createReasoningSegment(
                        reasoningContent,
                        undefined,
                        parentId
                     )
                  );
               }
            }

            updateAiSegments(result);
         };

         const handleRunError = (event: SimpleRunEvent) => {
            const errorDetails = event.errorDetails;
            const errorMessage =
               errorDetails || event.content || "An error occurred";
            console.error("AI streaming error:", errorMessage);

            const currentMessage = getAiMessage();
            if (!currentMessage) return;

            const parentId =
               delegationStack.length > 0
                  ? delegationStack[delegationStack.length - 1]
                  : undefined;

            const segments = [...currentMessage.segments];
            segments.push(
               createErrorSegment(errorMessage, undefined, parentId)
            );

            state.updateMessage(aiMessageId, {
               segments,
               status: "error",
               error: errorMessage
            });
            state.setLoading(false);
         };

         const handleToolCallStarted = (
            toolCallData: ToolCallStartedEventData
         ) => {
            const tool = toolCallData?.tool;
            if (!tool) return;

            const currentMessage = getAiMessage();
            if (!currentMessage) return;

            const parentId =
               delegationStack.length > 0
                  ? delegationStack[delegationStack.length - 1]
                  : undefined;

            const toolCallId =
               tool.toolCallId ||
               `tool-${Date.now()}-${iteration}-${
                  currentMessage.segments.length
               }`;

            const toolCall: ChatToolCallSegment = {
               segmentType: "tool_call",
               parentId,
               toolCallId,
               toolName: tool.toolName || "unknown tool",
               toolArgs: tool.toolArgs,
               status: "started"
            };

            // If it's a delegation tool, push to stack
            if (isDelegationTool(tool.toolName)) {
               delegationStack.push(toolCallId);
            }

            updateAiSegments([...currentMessage.segments, toolCall]);
         };

         const handleToolCallCompleted = (
            toolCallData: ToolCallCompletedEventData
         ) => {
            const tool = toolCallData?.tool;
            if (!tool) return;

            const currentMessage = getAiMessage();
            if (!currentMessage) return;

            const {
               toolCallId: completedId,
               toolName: completedName,
               toolCallError,
               toolArgs,
               result
            } = tool;

            const status = toolCallError
               ? ("error" as const)
               : ("completed" as const);

            // If it's on the stack, pop it
            if (completedId && delegationStack.includes(completedId)) {
               const idx = delegationStack.indexOf(completedId);
               if (idx !== -1) {
                  delegationStack.splice(idx, 1);
               }
            }

            const updated = currentMessage.segments.map((s) => {
               if (isToolCallSegment(s)) {
                  const isMatch = completedId
                     ? s.toolCallId === completedId
                     : s.toolName === completedName && s.status === "started";

                  if (isMatch) {
                     return {
                        ...s,
                        status,
                        toolCallError,
                        toolArgs: toolArgs || s.toolArgs,
                        result
                     };
                  }
               }
               return s;
            });

            updateAiSegments(updated);
         };

         const handleArtifactEvent = (artifactEventData: ArtifactEventData) => {
            set((currentState) =>
               reduceArtifactEvent(currentState, artifactEventData)
            );
         };

         while (true) {
            // Force streaming status on subsequent iterations (e.g. after tool execution)
            if (iteration > 0) {
               state.updateMessage(aiMessageId, {
                  status: "streaming"
               });
            }

            const toolOutputsToUse = nextToolOutputs;
            const runIdToUse = nextRunId;
            nextToolOutputs = undefined; // Reset for this iteration
            nextRunId = undefined; // Reset for this iteration

            if (!chatService.chatStream) {
               throw new Error(
                  "Chat streaming is not supported by this service"
               );
            }

            await chatService.chatStream(
               projectId,
               sessionId,
               iteration === 0 ? trimmedMessage : "",
               {
                  toolOutputs: toolOutputsToUse,
                  runId: runIdToUse,
                  onEvent: async (event: SimpleRunEvent) => {
                     ensureStreamingStatus();

                     switch (event.eventType) {
                        case RunEvent.RunContent:
                           handleRunContent(event);
                           break;
                        case RunEvent.RunCompleted:
                           state.updateMessage(aiMessageId, {
                              status: "completed"
                           });
                           break;
                        case RunEvent.RunPaused: {
                           const pauseData =
                              event.eventData as RunPausedEventData;

                           // Ensure tool-call segments exist for externally-executed tools.
                           // Depending on backend streaming ordering, ToolCallStarted may not arrive
                           // before RunPaused, so we render them here as well.
                           if (pauseData?.toolCalls?.length) {
                              const currentMessage = getAiMessage();
                              if (currentMessage) {
                                 const existingIds = new Set(
                                    currentMessage.segments
                                       .filter(isToolCallSegment)
                                       .map((s) => s.toolCallId)
                                       .filter((id): id is string => !!id)
                                 );

                                 const parentId =
                                    delegationStack.length > 0
                                       ? delegationStack[
                                            delegationStack.length - 1
                                         ]
                                       : undefined;

                                 let didAdd = false;
                                 const result = [...currentMessage.segments];
                                 const toolCalls = pauseData?.toolCalls || [];

                                 for (const toolCall of toolCalls) {
                                    const toolCallId = toolCall.toolCallId;
                                    if (
                                       toolCallId &&
                                       existingIds.has(toolCallId)
                                    ) {
                                       continue;
                                    }

                                    const toolCallSegment: ChatToolCallSegment =
                                       {
                                          segmentType: "tool_call",
                                          parentId,
                                          toolCallId:
                                             toolCallId ||
                                             `tool-${Date.now()}-${iteration}`,
                                          toolName:
                                             toolCall.toolName ||
                                             "unknown tool",
                                          toolArgs: toolCall.toolArgs,
                                          status: "started"
                                       };
                                    result.push(toolCallSegment);
                                    didAdd = true;
                                 }

                                 if (didAdd) {
                                    updateAiSegments(result);
                                 }
                              }
                           }

                           if (pauseData && options?.onRunPaused) {
                              // Capture run ID for resume
                              if (pauseData.runId) {
                                 nextRunId = pauseData.runId;
                              }

                              const result = await options.onRunPaused(event);
                              if (result) {
                                 nextToolOutputs = Array.isArray(result)
                                    ? result
                                    : [result];

                                 // Optimistic UI: mark the tool call segment(s) as completed/error
                                 // immediately after client-side execution finishes.
                                 const currentMessage = getAiMessage();
                                 if (currentMessage) {
                                    const outputs = nextToolOutputs;
                                    const updated = currentMessage.segments.map(
                                       (segment) => {
                                          if (!isToolCallSegment(segment)) {
                                             return segment;
                                          }

                                          const match = outputs.find(
                                             (o) =>
                                                o.toolCallId &&
                                                segment.toolCallId ===
                                                   o.toolCallId
                                          );
                                          if (match) {
                                             const toolStatus =
                                                match.toolCallError
                                                   ? ("error" as const)
                                                   : ("completed" as const);

                                             return {
                                                ...segment,
                                                status: toolStatus,
                                                toolCallError:
                                                   match.toolCallError,
                                                result: match.result
                                             };
                                          }

                                          return segment;
                                       }
                                    );

                                    updateAiSegments(updated);
                                 }
                              }
                           }
                           break;
                        }
                        case RunEvent.RunError:
                           handleRunError(event);
                           break;
                        case RunEvent.RunCancelled:
                           state.updateMessage(aiMessageId, {
                              status: "completed"
                           });
                           break;
                        case RunEvent.ToolCallStarted:
                           handleToolCallStarted(
                              event.eventData as ToolCallStartedEventData
                           );
                           break;
                        case RunEvent.ToolCallCompleted: {
                           const toolCallData =
                              event.eventData as ToolCallCompletedEventData;
                           handleToolCallCompleted(toolCallData);
                           break;
                        }
                        case RunEvent.ArtifactEvent: {
                           const artifactEventData =
                              event.eventData as ArtifactEventData;
                           if (artifactEventData?.artifact) {
                              handleArtifactEvent(artifactEventData);
                           }
                           break;
                        }
                        default:
                           break;
                     }
                  },

                  onError: (error: Error) => {
                     const currentState = get();
                     const currentMessage = currentState.messages.find(
                        (m: ChatMessage) => m.id === aiMessageId
                     );
                     if (currentMessage) {
                        state.updateMessage(aiMessageId, {
                           segments: [
                              ...currentMessage.segments,
                              createErrorSegment(error.message)
                           ],
                           status: "error",
                           error: error.message
                        });
                     } else {
                        state.updateMessage(aiMessageId, {
                           segments: [createErrorSegment(error.message)],
                           status: "error",
                           error: error.message
                        });
                     }
                     state.setLoading(false);
                     state.setError(error.message);
                  }
               }
            );

            if (!nextToolOutputs) {
               break;
            }

            iteration++;
         }

         state.setLoading(false);
      } catch (error) {
         console.error("Error sending message:", error);
         const currentState = get();
         const currentMessage = currentState.messages.find(
            (m: ChatMessage) => m.id === aiMessageId
         );
         const errMsg =
            error instanceof Error
               ? error.message
               : "An unexpected error occurred";
         if (currentMessage) {
            state.updateMessage(aiMessageId, {
               segments: [
                  ...currentMessage.segments,
                  createErrorSegment(errMsg)
               ],
               status: "error",
               error: errMsg
            });
         } else {
            state.updateMessage(aiMessageId, {
               segments: [createErrorSegment(errMsg)],
               status: "error",
               error: errMsg
            });
         }
         state.setLoading(false);
         state.setError(errMsg);
      }
   };
}
