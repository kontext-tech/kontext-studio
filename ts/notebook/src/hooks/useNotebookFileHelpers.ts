import {
   useFileWorkflow,
   useJsonFileHelpers,
   type UseFileWorkflowReturn
} from "@kontext-tech/file";
import type { FileModel } from "@kontext-tech/schema";
import { NotebookDocumentSchema } from "@kontext-tech/schema";
import { useCallback } from "react";
import { NOTEBOOK_FILE_EXTENSION } from "../constants";
import type { NotebookDocument } from "../types/notebook";

type NotebookFileWorkflow = Pick<
   UseFileWorkflowReturn,
   "fetchFile" | "getFileBlob" | "updateFile"
>;

export interface UseNotebookFileHelpersReturn {
   loadNotebook: (
      fileId: string,
      options?: {
         artifactContent?: string | NotebookDocument;
         fallbackTitle?: string;
         createEmptyOnParseError?: boolean;
      }
   ) => Promise<{
      notebook: NotebookDocument | null;
      file: FileModel | null;
      error: string | null;
   }>;
   saveNotebook: (
      fileId: string,
      notebook: NotebookDocument,
      name?: string
   ) => Promise<{
      success: boolean;
      file?: FileModel;
   }>;
}

export const useNotebookFileHelpers = (
   fileWorkflow: NotebookFileWorkflow
): UseNotebookFileHelpersReturn => {
   const { loadJsonFile, saveJsonFile } = useJsonFileHelpers(fileWorkflow);

   const loadNotebook = useCallback(
      async (
         fileId: string,
         options?: {
            artifactContent?: string | NotebookDocument;
            fallbackTitle?: string;
            createEmptyOnParseError?: boolean;
         }
      ) => {
         const { document, file, error } = await loadJsonFile<NotebookDocument>(
            fileId,
            {
               artifactContent: options?.artifactContent,
               createFallbackDocument: options?.createEmptyOnParseError
                  ? ({ file: loadedFile }) => ({
                       title:
                          options?.fallbackTitle ||
                          loadedFile?.name ||
                          "Untitled",
                       created: Date.now(),
                       modified: Date.now(),
                       blocks: []
                    })
                  : undefined,
               parseErrorMessage: "Failed to parse notebook content",
               loadErrorMessage: "Failed to load notebook",
               // Parse through the shared schema so legacy metadata fields
               // are ignored instead of breaking notebook loads.
               parseDocument: (parsed) => NotebookDocumentSchema.parse(parsed)
            }
         );

         return { notebook: document, file, error };
      },
      [loadJsonFile]
   );

   const saveNotebook = useCallback(
      async (fileId: string, notebook: NotebookDocument, name?: string) => {
         return saveJsonFile(fileId, notebook, {
            documentName: name,
            fallbackName: notebook.title || "Untitled Notebook",
            extension: NOTEBOOK_FILE_EXTENSION
         });
      },
      [saveJsonFile]
   );

   return {
      loadNotebook,
      saveNotebook
   };
};

export const useNotebookFileWorkflow = (
   options: Parameters<typeof useFileWorkflow>[0] = {}
): UseFileWorkflowReturn & UseNotebookFileHelpersReturn => {
   const fileWorkflow = useFileWorkflow(options);
   const notebookHelpers = useNotebookFileHelpers(fileWorkflow);

   return {
      ...fileWorkflow,
      ...notebookHelpers
   };
};
