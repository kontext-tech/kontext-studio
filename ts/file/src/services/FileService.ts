import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import {
   ApiResult,
   DataApiBaseService,
   logger,
   parseApiErrorPayload
} from "@kontext-labs/common";
import { getDataApiUrl } from "@kontext-labs/common/utils";
import type {
   CreateMultipleFilesResponse,
   FileFormatType,
   FileModel,
   InlineData,
   PaginatedFileResponse,
   PythonExecutionResult
} from "@kontext-labs/schema";
import type { FileServiceContract, FileUpdateRequest } from "../types";
import { generateUniqueFilename } from "../utils/fileUtils";

export interface FileUploadRequest {
   projectId: string;
   file: Blob | File;
   name?: string;
   prefix?: string;
}

export interface MultipleFileUploadRequest {
   projectId: string;
   files: Array<Blob | File>;
   allowOverwrite?: boolean;
   prefix?: string;
}

export class FileService
   extends DataApiBaseService
   implements FileServiceContract
{
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async getFileById(
      fileId: string,
      projectId: string
   ): Promise<ApiResult<FileModel | null>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/file/{fileId}", {
               params: {
                  path: { fileId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         if (this.getErrorStatus(error) === 404) {
            return ApiResult.success(null);
         }
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async getPaginatedFiles(
      projectId: string,
      pageIndex?: number,
      pageSize?: number,
      filterString?: string,
      fileTypes?: FileFormatType[],
      myFilesOnly?: boolean,
      prefix?: string,
      includeSystemPrefixes?: boolean
   ): Promise<ApiResult<PaginatedFileResponse>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/file", {
               params: {
                  query: {
                     projectId,
                     myFilesOnly,
                     includeSystemPrefixes,
                     pageIndex,
                     pageSize,
                     filterString,
                     fileTypes,
                     prefix
                  }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async createFile(
      request: FileUploadRequest
   ): Promise<ApiResult<{ file: FileModel; location?: string }>> {
      try {
         const formData = new FormData();
         formData.append("file", request.file);
         const { data, response } = await this.requestResponse(
            this.apiClient.POST("/file/upload", {
               params: {
                  query: {
                     projectId: request.projectId,
                     name: request.name,
                     prefix: request.prefix
                  }
               },
               body: formData as unknown as { file: string }
            })
         );
         const location = response.headers.get("location") || undefined;
         return ApiResult.success({
            file: data.file!,
            location
         });
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async createMultipleFiles(
      request: MultipleFileUploadRequest
   ): Promise<ApiResult<CreateMultipleFilesResponse>> {
      try {
         const formData = new FormData();
         request.files.forEach((file) => formData.append("files", file));
         const result = await this.request(
            this.apiClient.POST("/file/upload-multiple", {
               params: {
                  query: {
                     projectId: request.projectId,
                     allowOverwrite: request.allowOverwrite,
                     prefix: request.prefix
                  }
               },
               body: formData as unknown as { files: string[] }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async updateFile(request: FileUpdateRequest): Promise<ApiResult<FileModel>> {
      try {
         if (request.file) {
            const formData = new FormData();
            // The multipart filename is the file's new name and the content
            // update persists it. A follow-up metadata rename is redundant —
            // and fails whenever the name already exists (including for
            // system-prefixed assets such as charts and notebooks).
            if (request.name === undefined) {
               formData.append("file", request.file);
            } else {
               formData.append("file", request.file, request.name);
            }

            return ApiResult.success(
               await this.request(
                  this.apiClient.PUT("/file/{fileId}/upload", {
                     params: {
                        path: { fileId: request.fileId },
                        query: { projectId: request.projectId }
                     },
                     body: formData as unknown as { file: string }
                  })
               )
            );
         }

         if (request.name === undefined) {
            throw new Error("No update performed");
         }

         return ApiResult.success(
            await this.request(
               this.apiClient.PUT("/file/{fileId}", {
                  params: {
                     path: { fileId: request.fileId },
                     query: { projectId: request.projectId }
                  },
                  body: { name: request.name }
               })
            )
         );
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async uploadImage(
      projectId: string,
      blob: Blob | File
   ): Promise<ApiResult<{ file: FileModel; url: string }>> {
      try {
         let name: string;
         if (blob instanceof File) {
            name = generateUniqueFilename(blob.name);
         } else {
            name = `image-${Date.now()}`;
         }
         const result = await this.createFile({
            projectId,
            name,
            file: blob
         });

         if (!result.succeed || !result.data?.file?.id) {
            return ApiResult.failure({
               title: "Image Upload Failed",
               status: 400,
               messages: ["Failed to upload image"],
               error: result.error
            });
         }

         const imageUrl = this.getFileUrl(result.data.file.id);
         return ApiResult.success({
            file: result.data.file,
            url: imageUrl
         });
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async executeNotebookPythonBlock(
      fileId: string,
      blockId: string,
      projectId: string,
      codeOverride?: string,
      runId?: string
   ): Promise<ApiResult<PythonExecutionResult>> {
      try {
         const result = await this.request(
            this.apiClient.POST(
               "/file/{fileId}/notebook/blocks/{blockId}/execute-python",
               {
                  params: {
                     path: { fileId, blockId },
                     query: { projectId }
                  },
                  body:
                     codeOverride !== undefined || runId !== undefined
                        ? {
                             ...(codeOverride !== undefined
                                ? { codeOverride }
                                : {}),
                             ...(runId !== undefined ? { runId } : {})
                          }
                        : undefined
               }
            )
         );
         return ApiResult.success(result as PythonExecutionResult);
      } catch (error) {
         // Notebook Python failures render in the block's output, so do not
         // raise the global error modal.
         const errorResult = await this.handleInlineApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async getPaginatedImageFiles(
      projectId: string,
      pageIndex: number,
      pageSize: number,
      search: string
   ): Promise<ApiResult<PaginatedFileResponse>> {
      return this.getPaginatedFiles(projectId, pageIndex, pageSize, search, [
         "Image"
      ] as FileFormatType[]);
   }

   async downloadFile(
      fileId: string,
      projectId: string,
      onProgress?: (progress: number) => void
   ): Promise<ApiResult<{ blob: Blob; filename: string }>> {
      try {
         const cacheBuster = Date.now();
         const { error, response } = await this.apiClient.GET(
            "/file/{fileId}/download",
            {
               params: {
                  path: { fileId },
                  query: { projectId }
               },
               parseAs: "stream",
               headers: {
                  "Cache-Control": "no-cache, no-store, must-revalidate",
                  "Pragma": "no-cache",
                  "Expires": "0",
                  "X-Cache-Buster": cacheBuster.toString()
               }
            }
         );
         if (!response.ok) {
            // openapi-fetch consumes the body to build `error`, so parse the
            // payload via the shared handler. Failures are returned inline
            // (not routed to the global error handler) because expired or
            // missing files are ordinary outcomes here.
            const errorResult = parseApiErrorPayload({
               status: response.status,
               statusText: response.statusText,
               body: error
            });
            return ApiResult.failure({
               ...errorResult,
               title: "Download Failed"
            });
         }

         let filename = `file-${fileId}`;
         const disposition = response.headers.get("content-disposition");
         if (disposition) {
            const utf8Match = disposition.match(/filename\*=UTF-8''([^;\n]+)/i);
            if (utf8Match && utf8Match[1]) {
               filename = decodeURIComponent(utf8Match[1]);
            } else {
               const match = disposition.match(/filename="?([^";]+)"?/);
               if (match && match[1]) {
                  filename = match[1];
               }
            }
         }

         if (onProgress && response.body) {
            const contentLength = Number(
               response.headers.get("content-length")
            );
            const reader = response.body.getReader();
            let received = 0;
            const chunks: Uint8Array[] = [];
            while (true) {
               const { done, value } = await reader.read();
               if (done) break;
               if (value) {
                  chunks.push(value);
                  received += value.length;
                  if (contentLength) {
                     onProgress(Math.min(received / contentLength, 1));
                  }
               }
            }
            const blob = new Blob(chunks as BlobPart[]);
            return ApiResult.success({ blob, filename });
         }

         const blob = await response.blob();
         return ApiResult.success({ blob, filename });
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async deleteFile(
      fileId: string,
      projectId: string
   ): Promise<ApiResult<void>> {
      try {
         await this.request(
            this.apiClient.DELETE("/file/{fileId}", {
               params: {
                  path: { fileId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(undefined);
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   getFileUrl(fileId: string): string {
      if (!fileId) return "";
      const apiUrl = getDataApiUrl();
      return `${apiUrl}/file/${fileId}/download`;
   }

   async getDataTableRows(
      fileId: string,
      projectId: string,
      offset: number,
      limit: number
   ): Promise<ApiResult<InlineData>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/file/{fileId}/rows", {
               params: {
                  path: { fileId },
                  query: { projectId, offset, limit }
               }
            })
         );
         return ApiResult.success(result);
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }

   async getDataTableFile(
      fileId: string,
      projectId: string
   ): Promise<ApiResult<InlineData>> {
      try {
         logger.debug("[FileService] Loading InlineData from file:", fileId);

         const downloadResult = await this.downloadFile(fileId, projectId);
         if (!downloadResult.succeed || !downloadResult.data) {
            logger.error(
               "[FileService] Download failed:",
               downloadResult.error
            );
            return ApiResult.failure(
               downloadResult.error ?? {
                  title: "Failed to load file content",
                  status: 400,
                  messages: ["Could not retrieve file content"]
               }
            );
         }

         const blob = downloadResult.data.blob;
         let parsed: unknown;
         try {
            const text = await blob.text();
            logger.debug("[FileService] Downloaded text:", {
               length: text.length,
               preview: text.substring(0, 300)
            });
            parsed = JSON.parse(text);
            logger.debug("[FileService] Parsed InlineData:", parsed);
         } catch (e) {
            logger.error("[FileService] Parse error:", e);
            return ApiResult.failure({
               title: "Invalid Data Table",
               status: 422,
               messages: [
                  "File content is not valid InlineData JSON",
                  e instanceof Error ? e.message : String(e)
               ]
            });
         }

         return ApiResult.success(parsed as InlineData);
      } catch (error) {
         const errorResult = await this.handleApiError(error);
         return ApiResult.failure(errorResult);
      }
   }
}
