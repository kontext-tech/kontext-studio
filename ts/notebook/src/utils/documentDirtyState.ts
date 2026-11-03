import type {
   NotebookDocument,
   NotebookMetadata
} from "@notebook/types/notebook";

type PersistedBlockSnapshot = {
   type: string;
   data: unknown;
};

type PersistedNotebookSnapshot = {
   title: string;
   metadata: NotebookMetadata;
   blocks: PersistedBlockSnapshot[];
};

type EditorOutputSnapshot = {
   blocks?: Array<{
      type: string;
      data: unknown;
   }>;
};

const sortValueRecursively = (value: unknown): unknown => {
   if (Array.isArray(value)) {
      return value.map(sortValueRecursively);
   }

   if (value && typeof value === "object") {
      return Object.fromEntries(
         Object.entries(value as Record<string, unknown>)
            .sort(([leftKey], [rightKey]) => leftKey.localeCompare(rightKey))
            .map(([key, nestedValue]) => [
               key,
               sortValueRecursively(nestedValue)
            ])
      );
   }

   return value;
};

/**
 * Simple hash function for stable content comparison.
 * Uses the djb2 algorithm for fast, collision-resistant hashing.
 */
export const hashString = (str: string): string => {
   let hash = 5381;
   for (let i = 0; i < str.length; i++) {
      hash = (hash * 33) ^ str.charCodeAt(i);
   }
   return (hash >>> 0).toString(36);
};

const normalizeMetadata = (
   metadata: NotebookMetadata | undefined
): NotebookMetadata => ({
   description: metadata?.description,
   languageCode: metadata?.languageCode,
   tags: metadata?.tags,
   keyWords: metadata?.keyWords,
   imageUrl: metadata?.imageUrl,
   isPublished: metadata?.isPublished
});

const normalizeBlocks = (
   blocks: PersistedBlockSnapshot[]
): PersistedBlockSnapshot[] =>
   blocks.map((block) => {
      if (
         block.type === "sql" &&
         block.data &&
         typeof block.data === "object"
      ) {
         const {
            isExecuting: _isExecuting,
            lastExecuted: _lastExecuted,
            ...stableData
         } = block.data as Record<string, unknown>;
         void _isExecuting;
         void _lastExecuted;

         return {
            type: block.type,
            data: stableData
         };
      }

      return {
         type: block.type,
         data: block.data
      };
   });

export const normalizeNotebookForDirtyState = ({
   title,
   metadata,
   blocks
}: {
   title?: string;
   metadata?: NotebookMetadata;
   blocks: PersistedBlockSnapshot[];
}): PersistedNotebookSnapshot => ({
   title: title ?? "",
   metadata: normalizeMetadata(metadata),
   blocks: normalizeBlocks(blocks)
});

export const createNotebookDirtyStateHash = (
   document: Pick<NotebookDocument, "title" | "metadata" | "blocks">
): string =>
   hashString(
      JSON.stringify(
         sortValueRecursively(
            normalizeNotebookForDirtyState({
               title: document.title,
               metadata: document.metadata,
               blocks: document.blocks.map((block) => ({
                  type: block.type,
                  data: block.data
               }))
            })
         )
      )
   );

export const createEditorSnapshotDirtyStateHash = ({
   title,
   metadata,
   output
}: {
   title?: string;
   metadata?: NotebookMetadata;
   output: EditorOutputSnapshot;
}): string =>
   hashString(
      JSON.stringify(
         sortValueRecursively(
            normalizeNotebookForDirtyState({
               title,
               metadata,
               blocks: (output.blocks || []).map((block) => ({
                  type: block.type,
                  data: block.data
               }))
            })
         )
      )
   );
