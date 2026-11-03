import { logger } from "@kontext-labs/common";
import { default as EditorJS } from "@editorjs/editorjs";
import { useNotebookStore } from "@notebook/stores/notebookStore";
import type { NotebookDocument } from "@notebook/types/notebook";
import { convertFromEditorJSFormat } from "@notebook/utils/documentConverter";
import type React from "react";

/**
 * Clean up an existing EditorJS instance.
 *
 * Clears the ref immediately to prevent repeated cleanup, then destroys the
 * EditorJS instance once it reports ready. Destruction is best-effort: the
 * "redactor dom changed" warning is common when destroying early, so we force
 * a second attempt if the `isReady` path fails.
 */
export const cleanupEditor = (
   editorRef: React.MutableRefObject<EditorJS | null>
) => {
   if (editorRef.current) {
      const editor = editorRef.current;
      editorRef.current = null; // Clear reference immediately to prevent multiple cleanup calls

      if (typeof editor.destroy === "function") {
         try {
            logger.debug("Destroying EditorJS instance");
            editor.isReady
               .then(() => {
                  editor.destroy();
               })
               .catch((err) => {
                  // If it wasn't ready or already destroyed, this might fail
                  console.warn(
                     "EditorJS cleanup failed (during isReady):",
                     err
                  );
                  // Force destroy anyway if it didn't happen
                  try {
                     editor.destroy();
                  } catch {
                     // Ignore error during force destroy
                  }
               });
         } catch (error) {
            console.warn("Error destroying EditorJS:", error);
         }
      }
   }
};

export const getSavableEditor = async (editor: EditorJS | null) => {
   if (!editor) {
      return null;
   }

   try {
      await editor.isReady;
   } catch (error) {
      console.warn("EditorJS instance is not ready for save", error);
      return null;
   }

   return typeof editor.save === "function" ? editor : null;
};

/**
 * Create an updated document with current editor state and clean up any data
 * tables not linked to any blocks.
 */
export const createUpdatedDocument = async (
   document: NotebookDocument,
   editorRef: React.MutableRefObject<EditorJS | null>,
   defaultTitle: string,
   isEditorLoading: boolean,
   instanceId?: string
): Promise<NotebookDocument> => {
   let blocks = document.blocks;

   // Try to get the latest state from editor if available
   if (!isEditorLoading) {
      const savableEditor = await getSavableEditor(editorRef.current);

      if (savableEditor) {
         const outputData = await savableEditor.save();
         blocks = convertFromEditorJSFormat(outputData);
      }
   }

   // Build new document skeleton
   const newDocument: NotebookDocument = {
      ...document,
      title: document.title || defaultTitle,
      created: document.created || Date.now(),
      blocks,
      modified: Date.now()
   };

   // Persist to store
   const store = useNotebookStore.getState();
   store.setDocument(newDocument, instanceId || "default");

   // Return the current document from store
   const currentDocument = store.getInstanceState(
      instanceId || "default"
   )?.document;
   return currentDocument!;
};
