import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import { ApiResult, DataApiBaseService } from "@kontext-labs/common";
import type {
   ChatUploadPreparationStatus,
   SeedChatAttachmentContextRequest,
   StartChatUploadPreparationResponse
} from "@kontext-labs/schema";

/**
 * API service for chat attachment upload preparation. Uses the shared
 * openapi-fetch transport with `ChatService`.
 */
export class ChatUploadPreparationService extends DataApiBaseService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async startUploadPreparation(
      projectId: string,
      files: File[],
      allowOverwrite: boolean = false
   ): Promise<ApiResult<StartChatUploadPreparationResponse>> {
      try {
         const formData = new FormData();
         files.forEach((file) => formData.append("files", file));
         const result = await this.request(
            this.apiClient.POST("/ai/chat/upload-preparations", {
               params: {
                  query: { projectId, allowOverwrite }
               },
               body: formData as unknown as { files: string[] }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getUploadPreparationStatus(
      projectId: string,
      runId: string
   ): Promise<ApiResult<ChatUploadPreparationStatus>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/ai/chat/upload-preparations/{runId}", {
               params: {
                  path: { runId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async seedChatAttachmentContext(
      projectId: string,
      chatSessionId: string,
      uploadPreparationRunId: string
   ): Promise<ApiResult<void>> {
      try {
         const request: SeedChatAttachmentContextRequest = {
            uploadPreparationRunId
         };
         await this.request(
            this.apiClient.POST(
               "/ai/chat/session/{chatSessionId}/attachment-context",
               {
                  params: {
                     path: { chatSessionId },
                     query: { projectId }
                  },
                  body: request
               }
            )
         );
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
