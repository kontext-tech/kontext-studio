import type { ApiErrorResult } from "@kontext-labs/common/types";
import type {
   CreateMultipleFilesResponse,
   FileModel,
   InlineData,
   PaginatedFileResponse
} from "@kontext-labs/schema";
import { FileFormatType } from "@kontext-labs/schema";
import { useCallback, useEffect, useRef, useState } from "react";
import { type DownloadProgressCallback, type ResourceData } from "../types";
import { useFileService } from "./useFileService";

export interface UseFileOperationsOptions {
   projectId?: string;
   enableListManagement?: boolean;
   initialPageSize?: number;
   myFilesOnly?: boolean;
   includeSystemPrefixes?: boolean;
}

export interface FileListState {
   files: FileModel[];
   totalCount: number;
   pageIndex: number;
   pageSize: number;
   isLoading: boolean;
   searchValue: string;
   selectedFileTypes: FileFormatType[];
   prefix: string;
}

export interface UseFileOperationsResult {
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
   deleteFileById: (fileId: string) => Promise<boolean>;
   deleteMultipleFilesById: (fileIds: string[]) => Promise<{
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
}

export function useFileOperations(
   options: UseFileOperationsOptions = {}
): UseFileOperationsResult {
   const {
      projectId,
      enableListManagement = false,
      initialPageSize = 10,
      myFilesOnly = false,
      includeSystemPrefixes = true
   } = options;

   const fileService = useFileService();

   const [listState, setListState] = useState<FileListState>({
      files: [],
      totalCount: 0,
      pageIndex: 1,
      pageSize: initialPageSize,
      isLoading: false,
      searchValue: "",
      selectedFileTypes: [],
      prefix: ""
   });

   const listStateRef = useRef(listState);
   useEffect(() => {
      listStateRef.current = listState;
   }, [listState]);

   const loadFiles = useCallback(
      async (loadOptions?: {
         pageIndex?: number;
         pageSize?: number;
         filterString?: string;
         fileTypes?: FileFormatType[];
         prefix?: string;
      }) => {
         if (!projectId) return;

         const currentState = listStateRef.current;
         const requestedPageIndex =
            loadOptions?.pageIndex ?? currentState.pageIndex;
         const requestedPageSize =
            loadOptions?.pageSize ?? currentState.pageSize;
         const filterString =
            loadOptions?.filterString ?? currentState.searchValue;
         const prefix = loadOptions?.prefix ?? currentState.prefix;

         let fileTypes: FileFormatType[] | undefined;
         if (loadOptions?.fileTypes !== undefined) {
            fileTypes =
               loadOptions.fileTypes.length > 0
                  ? loadOptions.fileTypes
                  : undefined;
         } else if (currentState.selectedFileTypes.length > 0) {
            fileTypes = currentState.selectedFileTypes;
         }

         setListState((prev) => ({ ...prev, isLoading: true }));

         try {
            const result = await fileService.getPaginatedFiles(
               projectId,
               requestedPageIndex,
               requestedPageSize,
               filterString,
               fileTypes,
               myFilesOnly,
               prefix,
               includeSystemPrefixes
            );

            if (result.succeed && result.data) {
               const data = result.data;
               setListState((prev) => ({
                  ...prev,
                  files: data.items || [],
                  totalCount: data.totalCount || 0,
                  pageIndex: requestedPageIndex,
                  pageSize: requestedPageSize,
                  prefix,
                  isLoading: false
               }));
            } else {
               console.error("Failed to fetch files:", result.error);
               setListState((prev) => ({
                  ...prev,
                  files: [],
                  totalCount: 0,
                  isLoading: false
               }));
            }
         } catch (error) {
            console.error("Error loading files:", error);
            setListState((prev) => ({
               ...prev,
               files: [],
               totalCount: 0,
               isLoading: false
            }));
         }
      },
      [fileService, includeSystemPrefixes, myFilesOnly, projectId]
   );

   const refreshFiles = useCallback(async () => {
      await loadFiles();
   }, [loadFiles]);

   const updateListState = useCallback((updates: Partial<FileListState>) => {
      setListState((prev) => ({ ...prev, ...updates }));
   }, []);

   const fetchFile = useCallback(
      async (fileId: string): Promise<FileModel | null> => {
         if (!projectId) {
            console.error("No project ID available for fetching file");
            return null;
         }
         try {
            const result = await fileService.getFileById(fileId, projectId);

            if (result.succeed && result.data) {
               return result.data;
            }

            if (result.succeed && result.data === null) {
               return null;
            }

            throw new Error(
               result.error?.messages?.[0] || "Failed to load file"
            );
         } catch (error) {
            console.error("Error fetching file:", error);
            return null;
         }
      },
      [fileService, projectId]
   );

   const findFiles = useCallback(
      async (queryOptions: {
         pageIndex: number;
         pageSize: number;
         search: string;
         fileType?: string;
      }): Promise<PaginatedFileResponse | null> => {
         try {
            const fileTypes: FileFormatType[] = queryOptions.fileType
               ? [queryOptions.fileType as FileFormatType]
               : [];

            const result = await fileService.getPaginatedFiles(
               projectId || "",
               queryOptions.pageIndex,
               queryOptions.pageSize,
               queryOptions.search,
               fileTypes.length > 0 ? fileTypes : undefined,
               myFilesOnly,
               undefined,
               includeSystemPrefixes
            );

            if (result.succeed && result.data) {
               return result.data;
            }

            console.error("Error finding files:", result.error);
            return null;
         } catch (error) {
            console.error("Error finding files:", error);
            return null;
         }
      },
      [fileService, includeSystemPrefixes, myFilesOnly, projectId]
   );

   const deleteFileById = useCallback(
      async (fileId: string): Promise<boolean> => {
         if (!fileId || !projectId) {
            return false;
         }

         const result = await fileService.deleteFile(fileId, projectId);
         if (result.succeed) {
            if (enableListManagement) {
               await refreshFiles();
            }
            return true;
         }

         return false;
      },
      [enableListManagement, fileService, projectId, refreshFiles]
   );

   const deleteMultipleFilesById = useCallback(
      async (fileIds: string[]) => {
         if (!projectId || fileIds.length === 0) {
            return { successCount: 0, failureCount: fileIds.length };
         }

         let successCount = 0;
         let failureCount = 0;

         for (const fileId of fileIds) {
            const result = await fileService.deleteFile(fileId, projectId);
            if (result.succeed) {
               successCount += 1;
            } else {
               failureCount += 1;
            }
         }

         if (enableListManagement && successCount > 0) {
            await refreshFiles();
         }

         return { successCount, failureCount };
      },
      [enableListManagement, fileService, projectId, refreshFiles]
   );

   const createFile = useCallback(
      async (request: {
         projectId: string;
         name: string;
         file: Blob | File;
         prefix?: string;
      }) => {
         try {
            const result = await fileService.createFile({
               projectId: request.projectId,
               name: request.name,
               file: request.file as Blob,
               prefix: request.prefix
            });

            if (result.succeed && result.data) {
               if (enableListManagement) {
                  await refreshFiles();
               }

               return {
                  success: true,
                  file: result.data.file,
                  location: result.data.location
               };
            }

            // Surface the typed failure (duplicate-name 400s etc.) instead of
            // dropping it silently.
            return { success: false, error: result.error };
         } catch (error) {
            console.error("Failed to create file:", error);
            return { success: false };
         }
      },
      [enableListManagement, fileService, refreshFiles]
   );

   const updateFile = useCallback(
      async (request: {
         fileId: string;
         name?: string;
         file?: Blob | File;
      }) => {
         if (!projectId) {
            console.error("No project ID available for updating file");
            return { success: false };
         }
         try {
            const result = await fileService.updateFile({
               fileId: request.fileId,
               projectId,
               name: request.name,
               file: request.file
            });

            if (result.succeed && result.data) {
               if (enableListManagement) {
                  await refreshFiles();
               }

               return {
                  success: true,
                  file: result.data
               };
            }

            return { success: false, error: result.error };
         } catch (error) {
            console.error("Failed to update file:", error);
            return { success: false };
         }
      },
      [enableListManagement, fileService, projectId, refreshFiles]
   );

   const createMultipleFiles = useCallback(
      async (
         files: Array<{ name: string; file: File }>,
         allowOverwrite: boolean = false,
         prefix?: string
      ) => {
         if (!projectId) {
            return { success: false };
         }

         try {
            const result = await fileService.createMultipleFiles({
               projectId,
               files: files.map((file) => file.file),
               allowOverwrite,
               prefix
            });

            if (result.succeed && result.data) {
               if (enableListManagement) {
                  await refreshFiles();
               }

               return { success: true, response: result.data };
            }

            // Surface the typed failure instead of dropping it silently.
            return { success: false, error: result.error };
         } catch (error) {
            console.error("Failed to create multiple files:", error);
            return { success: false };
         }
      },
      [enableListManagement, fileService, projectId, refreshFiles]
   );

   const getFileData = useCallback(
      async (
         fileId: string,
         onProgress?: DownloadProgressCallback
      ): Promise<ResourceData | null> => {
         if (!projectId) {
            console.error("No project ID available for getting file data");
            return null;
         }

         try {
            const result = await fileService.downloadFile(
               fileId,
               projectId,
               onProgress
            );

            if (result.succeed && result.data) {
               const url = window.URL.createObjectURL(result.data.blob);
               return {
                  url,
                  blob: result.data.blob,
                  filename: result.data.filename
               };
            }

            throw new Error(
               result.error?.messages?.[0] || "Failed to load file"
            );
         } catch (error) {
            console.error("Error fetching file:", error);
            return null;
         }
      },
      [fileService, projectId]
   );

   const getInlineDataFile = useCallback(
      async (fileId: string): Promise<InlineData | null> => {
         if (!projectId) {
            console.error(
               "No project ID available for getting data table data"
            );
            return null;
         }
         try {
            const result = await fileService.getDataTableFile(
               fileId,
               projectId
            );
            return result.succeed ? result.data || null : null;
         } catch (error) {
            console.error("Error loading data table data:", error);
            return null;
         }
      },
      [fileService, projectId]
   );

   const getFileUrl = useCallback(
      (fileId: string): string => fileService.getFileUrl(fileId),
      [fileService]
   );

   const uploadImage = useCallback(
      async (file: File): Promise<string | null> => {
         if (!projectId) return null;

         try {
            const result = await fileService.uploadImage(projectId, file);
            if (result.succeed && result.data) {
               return result.data.url;
            }
            return null;
         } catch (error) {
            console.error("Error uploading image:", error);
            return null;
         }
      },
      [fileService, projectId]
   );

   const fetchImageFiles = useCallback(
      async (pageIndex: number, pageSize: number, search: string) => {
         if (!projectId) {
            return { items: [], totalCount: 0 };
         }

         try {
            const result = await fileService.getPaginatedFiles(
               projectId,
               pageIndex,
               pageSize,
               search,
               [FileFormatType.Image],
               myFilesOnly
            );

            if (result.succeed && result.data) {
               return {
                  items: result.data.items || [],
                  totalCount: result.data.totalCount || 0
               };
            }

            return { items: [], totalCount: 0 };
         } catch (error) {
            console.error("Error fetching image files:", error);
            return { items: [], totalCount: 0 };
         }
      },
      [fileService, myFilesOnly, projectId]
   );

   const downloadImageFile = useCallback(
      async (
         fileId: string,
         onProgress?: (progress: number) => void
      ): Promise<Blob | null> => {
         try {
            if (!projectId) {
               console.error(
                  `[useFileOperations] No project ID available for file: ${fileId}`
               );
               return null;
            }

            const result = await fileService.downloadFile(
               fileId,
               projectId,
               onProgress
            );

            return result.succeed && result.data ? result.data.blob : null;
         } catch (error) {
            console.error(
               `[useFileOperations] Error downloading image file: ${fileId}`,
               error
            );
            return null;
         }
      },
      [fileService, projectId]
   );

   const getFileBlob = useCallback(
      async (fileId: string): Promise<Blob | null> => {
         if (!projectId) {
            console.error("No project ID available for getting file blob");
            return null;
         }

         try {
            const result = await fileService.downloadFile(fileId, projectId);
            return result.succeed && result.data ? result.data.blob : null;
         } catch (error) {
            console.error("Error getting file blob:", error);
            return null;
         }
      },
      [fileService, projectId]
   );

   return {
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
   };
}
