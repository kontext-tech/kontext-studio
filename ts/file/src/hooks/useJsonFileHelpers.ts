import type { FileModel } from "@kontext-tech/schema";
import { useCallback } from "react";
import type { UseFileWorkflowReturn } from "./useFileWorkflow";

export interface LoadJsonFileOptions<TDocument> {
   artifactContent?: string | TDocument;
   fallbackDocument?: TDocument;
   createFallbackDocument?: (context: { file: FileModel | null }) => TDocument;
   parseDocument?: (parsed: unknown) => TDocument;
   parseErrorMessage?: string;
   loadErrorMessage?: string;
}

export interface SaveJsonFileOptions<TDocument> {
   documentName?: string;
   fallbackName?: string;
   extension?: string;
   stringify?: (document: TDocument) => string;
}

interface JsonFileResult<TDocument> {
   document: TDocument | null;
   file: FileModel | null;
   error: string | null;
}

const resolveFallbackDocument = <TDocument>(
   options: Pick<
      LoadJsonFileOptions<TDocument>,
      "fallbackDocument" | "createFallbackDocument"
   >,
   file: FileModel | null
): TDocument | null => {
   if (options.createFallbackDocument) {
      return options.createFallbackDocument({ file });
   }

   return options.fallbackDocument ?? null;
};

export const useJsonFileHelpers = ({
   fetchFile,
   getFileBlob,
   updateFile
}: Pick<UseFileWorkflowReturn, "fetchFile" | "getFileBlob" | "updateFile">) => {
   const loadJsonFile = useCallback(
      async <TDocument>(
         fileId: string,
         options?: LoadJsonFileOptions<TDocument>
      ): Promise<JsonFileResult<TDocument>> => {
         let file: FileModel | null = null;
         let document: TDocument | null = null;
         let error: string | null = null;

         const parseDocument =
            options?.parseDocument ??
            ((parsed: unknown) => parsed as TDocument);

         try {
            if (options?.artifactContent) {
               try {
                  const parsedContent =
                     typeof options.artifactContent === "string"
                        ? JSON.parse(options.artifactContent)
                        : options.artifactContent;

                  document = parseDocument(parsedContent);
               } catch (parseError) {
                  console.warn(
                     "Failed to parse provided artifact content:",
                     parseError
                  );
                  document = resolveFallbackDocument(options, null);
               }
            }

            file = await fetchFile(fileId);

            if (document) {
               return { document, file, error };
            }

            const blob = await getFileBlob(fileId);
            if (!blob) {
               return {
                  document,
                  file,
                  error: options?.loadErrorMessage ?? "Failed to load file"
               };
            }

            try {
               const text = await blob.text();
               document = parseDocument(JSON.parse(text));
            } catch (parseError) {
               console.error("Error parsing file content:", parseError);
               document = resolveFallbackDocument(options ?? {}, file);
               if (!document) {
                  error =
                     options?.parseErrorMessage ??
                     "Failed to parse file content";
               }
            }
         } catch (loadError) {
            console.error("Error loading file:", loadError);
            error = options?.loadErrorMessage ?? "Failed to load file";
         }

         return { document, file, error };
      },
      [fetchFile, getFileBlob]
   );

   const saveJsonFile = useCallback(
      async <TDocument>(
         fileId: string,
         document: TDocument,
         options?: SaveJsonFileOptions<TDocument>
      ): Promise<{
         success: boolean;
         file?: FileModel;
      }> => {
         try {
            const baseName =
               options?.documentName || options?.fallbackName || "Untitled";
            const extension = options?.extension ?? "";
            const nextName =
               extension && !baseName.endsWith(extension)
                  ? `${baseName}${extension}`
                  : baseName;

            const file = new File(
               [
                  options?.stringify
                     ? options.stringify(document)
                     : JSON.stringify(document, null, 2)
               ],
               nextName,
               {
                  type: "application/json"
               }
            );

            return await updateFile({
               fileId,
               file,
               name: nextName
            });
         } catch (saveError) {
            console.error("Error saving file:", saveError);
            return { success: false };
         }
      },
      [updateFile]
   );

   return {
      loadJsonFile,
      saveJsonFile
   };
};
