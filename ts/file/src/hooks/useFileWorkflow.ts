import { useUiApp } from "@kontext-tech/ui";
import type { ApiErrorResult } from "@kontext-tech/common/types";
import type { DownloadProgressCallback, ResourceData } from "../types";
import { downloadBlob } from "../utils/fileUtils";
import { useFileOperations, type FileListState } from "./useFileOperations";
import type {
   CreateMultipleFilesResponse,
   FileFormatType,
   FileModel,
   InlineData,
   PaginatedFileResponse
} from "@kontext-tech/schema";
import { useCallback, useState } from "react";

export interface UseFileWorkflowOptions {
   projectId?: string;
   enableListManagement?: boolean;
   initialPageSize?: number;
   myFilesOnly?: boolean;
   includeSystemPrefixes?: boolean;
}

export interface UseFileWorkflowReturn {
   listState: FileListState;
   loadFiles: (options?: {
      pageIndex?: number;
      pageSize?: number;
      filterString?: string;
      fileTypes?: FileFormatType[];
      prefix?: string;
   }) => Promise<void>;
   refreshFiles: () => Promise<void>;
   updateListState: (updates: Partial<FileListState>) => void;
   fetchFile: (fileId: string) => Promise<FileModel | null>;
   findFiles: (options: {
      pageIndex: number;
      pageSize: number;
      search: string;
      fileType?: string;
   }) => Promise<PaginatedFileResponse | null>;
   downloadFile: (file: FileModel) => Promise<void>;
   deleteFile: (file: FileModel) => Promise<boolean>;
   deleteMultipleFiles: (files: FileModel[]) => Promise<{
      successCount: number;
      failureCount: number;
   }>;
   createMultipleFiles: (
      files: Array<{ name: string; file: File }>,
      allowOverwrite?: boolean,
      prefix?: string
   ) => Promise<{
      success: boolean;
      response?: CreateMultipleFilesResponse;
      error?: ApiErrorResult;
   }>;
   createFile: (request: {
      projectId: string;
      name: string;
      file: Blob | File;
      prefix?: string;
   }) => Promise<{
      success: boolean;
      file?: FileModel;
      location?: string;
      error?: ApiErrorResult;
   }>;
   updateFile: (request: {
      fileId: string;
      name?: string;
      file?: Blob | File;
   }) => Promise<{
      success: boolean;
      file?: FileModel;
      error?: ApiErrorResult;
   }>;
   getFileData: (
      fileId: string,
      onProgress?: DownloadProgressCallback
   ) => Promise<ResourceData | null>;
   getInlineDataFile: (fileId: string) => Promise<InlineData | null>;
   getFileUrl: (fileId: string) => string;
   getFileBlob: (fileId: string) => Promise<Blob | null>;
   uploadImage: (file: File) => Promise<string | null>;
   fetchImageFiles: (
      pageIndex: number,
      pageSize: number,
      search: string
   ) => Promise<{ items: FileModel[]; totalCount: number }>;
   downloadImageFile: (
      fileId: string,
      onProgress?: (progress: number) => void
   ) => Promise<Blob | null>;
   downloadProgress: number | null;
   isDownloading: boolean;
   downloadModalVisible: boolean;
   downloadModalText: string;
   closeDownloadModal: () => void;
}

export const useFileWorkflow = (
   options: UseFileWorkflowOptions = {}
): UseFileWorkflowReturn => {
   const {
      projectId,
      enableListManagement = false,
      initialPageSize = 10,
      myFilesOnly = false,
      includeSystemPrefixes = true
   } = options;

   const { message, modal } = useUiApp();
   const {
      listState,
      loadFiles,
      refreshFiles,
      updateListState,
      fetchFile,
      findFiles,
      deleteFileById,
      deleteMultipleFilesById,
      createMultipleFiles,
      createFile,
      updateFile,
      getFileData,
      getInlineDataFile,
      getFileUrl,
      getFileBlob,
      uploadImage,
      fetchImageFiles,
      downloadImageFile
   } = useFileOperations({
      projectId,
      enableListManagement,
      initialPageSize,
      myFilesOnly,
      includeSystemPrefixes
   });

   const [downloadProgress, setDownloadProgress] = useState<number | null>(
      null
   );
   const [isDownloading, setIsDownloading] = useState<boolean>(false);
   const [downloadModalVisible, setDownloadModalVisible] =
      useState<boolean>(false);
   const [downloadModalText, setDownloadModalText] = useState<string>("");

   const downloadFile = useCallback(
      async (file: FileModel): Promise<void> => {
         if (!file.id || !projectId) return;

         setIsDownloading(true);
         setDownloadProgress(0);
         setDownloadModalText(`Downloading "${file.name}"...`);
         setDownloadModalVisible(true);

         try {
            const result = await getFileData(file.id, (progress: number) =>
               setDownloadProgress(progress)
            );

            if (!result) {
               message.error("Failed to download file");
               return;
            }

            downloadBlob(result.blob, file.name);
            // `getFileData` also creates an object URL for preview use; revoke
            // it here because this path only needs the blob.
            window.URL.revokeObjectURL(result.url);
            message.success("Download completed");
         } catch (error) {
            console.error("Download failed:", error);
            message.error("Failed to download file");
         } finally {
            setIsDownloading(false);
            setDownloadProgress(null);
            setDownloadModalVisible(false);
         }
      },
      [getFileData, message, projectId]
   );

   const deleteFile = useCallback(
      async (file: FileModel): Promise<boolean> => {
         return new Promise((resolve) => {
            modal.confirm({
               title: "Delete File",
               content: `Are you sure you want to delete "${file.name}"? This action cannot be undone.`,
               okText: "Delete",
               okType: "danger",
               cancelText: "Cancel",
               onOk: async () => {
                  if (!file.id) {
                     resolve(false);
                     return;
                  }

                  const success = await deleteFileById(file.id);
                  if (success) {
                     message.success("File deleted successfully");
                     resolve(true);
                  } else {
                     message.error("Failed to delete file");
                     resolve(false);
                  }
               },
               onCancel: () => {
                  resolve(false);
               }
            });
         });
      },
      [deleteFileById, message, modal]
   );

   const deleteMultipleFiles = useCallback(
      async (
         files: FileModel[]
      ): Promise<{ successCount: number; failureCount: number }> => {
         const validFiles = files.filter((file) => file.id);

         if (!projectId || validFiles.length === 0) {
            return { successCount: 0, failureCount: validFiles.length };
         }

         return new Promise((resolve) => {
            modal.confirm({
               title: "Delete Files",
               content: `Are you sure you want to delete ${validFiles.length} selected file(s)? This action cannot be undone.`,
               okText: "Delete",
               okType: "danger",
               cancelText: "Cancel",
               onOk: async () => {
                  const { successCount, failureCount } =
                     await deleteMultipleFilesById(
                        validFiles.map((file) => file.id!)
                     );

                  if (successCount > 0 && failureCount === 0) {
                     message.success(
                        `${successCount} file${successCount === 1 ? "" : "s"} deleted successfully`
                     );
                  } else if (successCount > 0 && failureCount > 0) {
                     message.warning(
                        `${successCount} deleted, ${failureCount} failed`
                     );
                  } else {
                     message.error("Failed to delete selected files");
                  }

                  resolve({ successCount, failureCount });
               },
               onCancel: () => {
                  resolve({ successCount: 0, failureCount: 0 });
               }
            });
         });
      },
      [deleteMultipleFilesById, message, modal, projectId]
   );

   const closeDownloadModal = useCallback(() => {
      setDownloadModalVisible(false);
      setDownloadProgress(null);
   }, []);

   return {
      listState,
      loadFiles,
      refreshFiles,
      updateListState,
      fetchFile,
      findFiles,
      downloadFile,
      deleteFile,
      deleteMultipleFiles,
      createFile,
      updateFile,
      createMultipleFiles,
      getFileData,
      getInlineDataFile,
      getFileUrl,
      getFileBlob,
      uploadImage,
      fetchImageFiles,
      downloadImageFile,
      downloadProgress,
      isDownloading,
      downloadModalVisible,
      downloadModalText,
      closeDownloadModal
   };
};
