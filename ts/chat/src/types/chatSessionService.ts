import type {
   Artifact,
   ChatMessage,
   ChatSessionModel,
   CreateChatSessionRequest,
   ExecutePythonScriptRequest,
   PaginatedChatSessionResponse,
   PythonExecutionResult,
   UpdateChatSessionRequest
} from "@kontext-tech/schema";
import type { AIChatStreamOptions } from "./aiChat";
import type { ApiResult } from "@kontext-tech/common";

/**
 * Service interface for chat session management.
 */
export interface ChatSessionService {
   createChatSession(
      input: CreateChatSessionRequest
   ): Promise<ApiResult<ChatSessionModel>>;

   updateChatSession(
      chatSessionId: string,
      projectId: string,
      input: UpdateChatSessionRequest
   ): Promise<ApiResult<ChatSessionModel>>;

   getChatSession(
      chatSessionId: string,
      projectId: string
   ): Promise<ApiResult<ChatSessionModel>>;

   deleteChatSession(
      chatSessionId: string,
      projectId: string
   ): Promise<ApiResult<void>>;

   getFilteredChatSessions(
      projectId: string,
      filter?: string,
      pageIndex?: number,
      pageSize?: number,
      mySessionsOnly?: boolean
   ): Promise<ApiResult<PaginatedChatSessionResponse>>;

   getChatSessionMessages(
      chatSessionId: string,
      projectId: string
   ): Promise<ApiResult<ChatMessage[]>>;

   getChatSessionArtifacts(
      chatSessionId: string,
      projectId: string
   ): Promise<ApiResult<Artifact[]>>;

   executePythonScript(
      chatSessionId: string,
      projectId: string,
      input: ExecutePythonScriptRequest
   ): Promise<ApiResult<PythonExecutionResult>>;

   /**
    * Stream chat messages. Optional for providers that don't support streaming.
    */
   chatStream?(
      projectId: string,
      sessionId: string,
      message: string,
      options?: AIChatStreamOptions
   ): Promise<ApiResult<void>>;
}
