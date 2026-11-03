import type { OutputData } from "@editorjs/editorjs";
import { NotebookBlockSchema } from "@kontext-labs/schema";
import type { NotebookBlock, NotebookDocument } from "@notebook/types/notebook";
import { createBlockId } from "./coreUtils";

/**
 * Converts a NotebookDocument to EditorJS OutputData format
 */
export function convertToEditorJSFormat(
   document: NotebookDocument
): OutputData {
   return {
      time: document.modified || document.created,
      blocks: document.blocks.map((block) => ({
         id: block.id,
         type: block.type,
         data: block.data
      })),
      version: "2.28.0"
   };
}

/**
 * Converts EditorJS OutputData to NotebookDocument format
 */
export function convertFromEditorJSFormat(data: OutputData): NotebookBlock[] {
   return data.blocks
      .map((block) => {
         // Ensure all blocks have proper GUID format IDs
         let blockId = block.id || createBlockId();

         // If the ID doesn't look like a GUID (less than 32 chars, no dashes), generate a new GUID
         if (!blockId.includes("-") || blockId.length < 32) {
            blockId = createBlockId();
         }

         const rawBlock = {
            id: blockId,
            type: block.type,
            data: block.data
         };

         // Use Zod schema to parse and sanitize the block.
         // This automatically strips any extra attributes added by the frontend's EditorJS tools
         // that are not defined in our official schemas.
         try {
            return NotebookBlockSchema.parse(rawBlock) as NotebookBlock;
         } catch (error) {
            console.error(
               `[NotebookConverter] Block validation failed for block ${blockId} (${block.type}):`,
               error
            );
            // Fallback to raw block if validation fails, but it might still have extra attributes
            return rawBlock as NotebookBlock;
         }
      })
      .filter(Boolean);
}
