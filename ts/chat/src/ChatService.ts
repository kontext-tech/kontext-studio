import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, DataApiBaseService } from "@kontext-tech/common";
import {
   SimpleRunEventStreamSchema,
   type Artifact,
   type ChatMessage,
   type ChatRequest,
   type ChatSessionModel,
   type CreateChatSessionRequest,
   type ExecutePythonScriptRequest,
   type PaginatedChatSessionResponse,
   type ProjectDailyTokenUsageResponse,
   type ProjectTokenUsageResponse,
   type PythonExecutionResult,
   type UpdateChatSessionRequest
} from "@kontext-tech/schema";
import type { AIChatStreamOptions, SimpleRunEvent } from "./types/aiChat";
import type { ChatSessionService } from "./types/chatSessionService";
import { consumeNdjsonStream } from "./utils/ndjsonStream";

const sanitizeNulls = <T>(value: T): T => {
   if (value === null) {
      return undefined as T;
   }

   if (Array.isArray(value)) {
      return value.map((item) => sanitizeNulls(item)) as T;
   }

   if (value instanceof Date || typeof value !== "object") {
      return value;
   }

   return Object.fromEntries(
      Object.entries(value).flatMap(([key, entryValue]) => {
         const sanitizedValue = sanitizeNulls(entryValue);
         return sanitizedValue === undefined ? [] : [[key, sanitizedValue]];
      })
   ) as T;
};

const toChatRequest = (request: ChatRequest): ChatRequest => ({
   projectId: request.projectId,
   sessionId: request.sessionId,
   message: request.message,
   toolOutputs: request.toolOutputs
      ? (sanitizeNulls(request.toolOutputs) as ChatRequest["toolOutputs"])
      : undefined,
   runId: request.runId ?? undefined
});

/**
 * API-based implementation of chat session service.
 * Uses the shared openapi-fetch client to communicate with the backend.
 */
export class ChatService
   extends DataApiBaseService
   implements ChatSessionService
{
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   // ---------------- Chat session management ----------------

   async createChatSession(
      input: CreateChatSessionRequest
   ): Promise<ApiResult<ChatSessionModel>> {
      try {
         const result = await this.request(
            this.apiClient.POST("/ai/chat/session", {
               body: input
            })
         );
         return ApiResult.success(result as ChatSessionModel);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async updateChatSession(
      chatSessionId: string,
      projectId: string,
      input: UpdateChatSessionRequest
   ): Promise<ApiResult<ChatSessionModel>> {
      try {
         const result = await this.request(
            this.apiClient.PUT("/ai/chat/session/{chatSessionId}", {
               params: {
                  path: { chatSessionId },
                  query: { projectId }
               },
               body: input
            })
         );
         return ApiResult.success(result as ChatSessionModel);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getChatSession(
      chatSessionId: string,
      projectId: string
   ): Promise<ApiResult<ChatSessionModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/ai/chat/session/{chatSessionId}", {
               params: {
                  path: { chatSessionId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result as ChatSessionModel);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async deleteChatSession(
      chatSessionId: string,
      projectId: string
   ): Promise<ApiResult<void>> {
      try {
         await this.request(
            this.apiClient.DELETE("/ai/chat/session/{chatSessionId}", {
               params: {
                  path: { chatSessionId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getProjectTokenUsage(
      projectId: string
   ): Promise<ApiResult<ProjectTokenUsageResponse>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/ai/chat/usage", {
               params: { query: { projectId } }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getProjectDailyTokenUsage(
      projectId: string,
      month?: string
   ): Promise<ApiResult<ProjectDailyTokenUsageResponse>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/ai/chat/usage/daily", {
               params: { query: { projectId, month } }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getFilteredChatSessions(
      projectId: string,
      filter?: string,
      pageIndex?: number,
      pageSize?: number,
      mySessionsOnly?: boolean
   ): Promise<ApiResult<PaginatedChatSessionResponse>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/ai/chat/session/filtered", {
               params: {
                  query: {
                     projectId,
                     filter,
                     pageIndex: pageIndex,
                     pageSize,
                     mySessionsOnly
                  }
               }
            })
         );
         return ApiResult.success(result as PaginatedChatSessionResponse);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getChatSessionMessages(
      chatSessionId: string,
      projectId: string
   ): Promise<ApiResult<ChatMessage[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/ai/chat/session/{chatSessionId}/messages", {
               params: {
                  path: { chatSessionId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result as ChatMessage[]);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getChatSessionArtifacts(
      chatSessionId: string,
      projectId: string
   ): Promise<ApiResult<Artifact[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/ai/chat/session/{chatSessionId}/artifacts", {
               params: {
                  path: { chatSessionId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result.artifacts ?? []);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async executePythonScript(
      chatSessionId: string,
      projectId: string,
      input: ExecutePythonScriptRequest
   ): Promise<ApiResult<PythonExecutionResult>> {
      try {
         const result = await this.request(
            this.apiClient.POST(
               "/ai/chat/session/{chatSessionId}/execute-python",
               {
                  params: {
                     path: { chatSessionId },
                     query: { projectId }
                  },
                  body: input
               }
            )
         );
         return ApiResult.success(result as PythonExecutionResult);
      } catch (error) {
         // Execution failures are surfaced inline in the conversation (tool-call
         // card + agent explanation), so do not raise the global error modal.
         return ApiResult.failure(await this.handleInlineApiError(error));
      }
   }

   // ---------------- AI chat streaming ----------------

   async chatStream(
      projectId: string,
      sessionId: string,
      message: string,
      options: AIChatStreamOptions = {}
   ): Promise<ApiResult<void>> {
      const { onEvent, onError, onComplete, signal, toolOutputs, runId } =
         options;

      try {
         const request: ChatRequest = {
            projectId,
            sessionId,
            message,
            toolOutputs,
            runId
         };

         const { data: stream } = await this.requestResponse(
            this.apiClient.POST("/ai/chat/stream", {
               body: toChatRequest(request),
               parseAs: "stream",
               ...(signal ? { signal } : {})
            })
         );

         if (!stream) {
            throw new Error("Response body is null");
         }

         await consumeNdjsonStream({
            stream,
            schema: SimpleRunEventStreamSchema,
            onValue: async (event) => {
               await onEvent?.(event as SimpleRunEvent);
            }
         });

         onComplete?.();
         return ApiResult.success(undefined);
      } catch (error) {
         const apiError = await this.handleApiError(error);
         const errorToReport =
            (apiError.error as Error) ||
            new Error(
               apiError.messages[0] || apiError.title || "An error occurred"
            );
         onError?.(errorToReport);
         return ApiResult.failure(apiError);
      }
   }
}
