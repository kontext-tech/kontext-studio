import type { ApiResult, PaginatedResult } from "@kontext-labs/common/types";
import type {
   FileModel,
   InlineData,
   PythonExecutionResult,
   UpdateFileRequest
} from "@kontext-labs/schema";

export type DownloadProgressCallback = (progress: number) => void;

export interface ResourceData {
   url: string;
   blob: Blob;
   filename: string;
}

export type FileUpdateRequest = Pick<UpdateFileRequest, "name"> & {
   fileId: string;
   projectId: string;
   file?: Blob | File;
};

export interface FileServiceContract {
   getDataTableFile(
      fileId: string,
      projectId: string
   ): Promise<ApiResult<InlineData>>;
   getDataTableRows(
      fileId: string,
      projectId: string,
      offset: number,
      limit: number
   ): Promise<ApiResult<InlineData>>;
   uploadImage(
      projectId: string,
      file: File | Blob
   ): Promise<ApiResult<{ file: FileModel; url: string }>>;
   getPaginatedImageFiles(
      projectId: string,
      pageIndex: number,
      pageSize: number,
      search: string
   ): Promise<ApiResult<PaginatedResult<FileModel>>>;
   downloadFile(
      fileId: string,
      projectId: string,
      onProgress?: DownloadProgressCallback
   ): Promise<ApiResult<{ blob: Blob }>>;
   executeNotebookPythonBlock(
      fileId: string,
      blockId: string,
      projectId: string,
      codeOverride?: string,
      runId?: string
   ): Promise<ApiResult<PythonExecutionResult>>;
   getFileUrl(fileId: string): string;
}
