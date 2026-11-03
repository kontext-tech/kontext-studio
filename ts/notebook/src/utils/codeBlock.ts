import type { CodeBlockData } from "@kontext-labs/schema";
import type {
   CodeBlock,
   NotebookBlock,
   NotebookDocument
} from "../types/notebook";

export const PYTHON_CODE_BLOCK_LANGUAGE = "python" as const;
export const PYTHON_CODE_BLOCK_LABEL = "Python";

export function normalizeCodeBlockData<T extends Partial<CodeBlockData>>(
   data: T
): T & { language: typeof PYTHON_CODE_BLOCK_LANGUAGE } {
   return {
      ...data,
      language: PYTHON_CODE_BLOCK_LANGUAGE
   };
}

export function normalizeCodeBlock(block: CodeBlock): CodeBlock {
   return {
      ...block,
      data: normalizeCodeBlockData(block.data)
   };
}

export function normalizeNotebookBlock(block: NotebookBlock): NotebookBlock {
   if (block.type !== "code") {
      return block;
   }

   return normalizeCodeBlock(block);
}

export function normalizeNotebookDocument(
   document: NotebookDocument
): NotebookDocument {
   return {
      ...document,
      blocks: document.blocks.map(normalizeNotebookBlock)
   };
}
