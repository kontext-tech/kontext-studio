import type { NotebookDocument } from "@notebook/types/notebook";
import {
   createEditorSnapshotDirtyStateHash,
   createNotebookDirtyStateHash
} from "../documentDirtyState";

const createDocument = (
   overrides: Partial<NotebookDocument> = {}
): NotebookDocument => ({
   title: "Notebook Title",
   metadata: {
      languageCode: "en",
      tags: ["docs"]
   },
   blocks: [
      {
         id: "11111111-1111-1111-1111-111111111111",
         type: "paragraph",
         data: {
            text: "Hello world"
         }
      }
   ],
   created: 1,
   modified: 1,
   ...overrides
});

describe("NotebookEditor dirty-state hashing", () => {
   it("treats metadata changes as dirty even when editor blocks are unchanged", () => {
      const originalDocument = createDocument();
      const originalHash = createNotebookDirtyStateHash(originalDocument);

      const editorSnapshotHash = createEditorSnapshotDirtyStateHash({
         title: originalDocument.title,
         metadata: {
            ...originalDocument.metadata,
            languageCode: "fr"
         },
         output: {
            blocks: originalDocument.blocks.map((block) => ({
               type: block.type,
               data: block.data
            }))
         }
      });

      expect(editorSnapshotHash).not.toBe(originalHash);
   });

   it("treats title changes as dirty even when editor blocks are unchanged", () => {
      const originalDocument = createDocument();
      const originalHash = createNotebookDirtyStateHash(originalDocument);

      const editorSnapshotHash = createEditorSnapshotDirtyStateHash({
         title: "Updated Notebook Title",
         metadata: originalDocument.metadata,
         output: {
            blocks: originalDocument.blocks.map((block) => ({
               type: block.type,
               data: block.data
            }))
         }
      });

      expect(editorSnapshotHash).not.toBe(originalHash);
   });

   it("matches the saved document after save so no-op editor changes stay clean", () => {
      const savedDocument = createDocument({
         title: "Updated Notebook Title",
         metadata: {
            languageCode: "fr",
            tags: ["docs"]
         }
      });

      const savedHash = createNotebookDirtyStateHash(savedDocument);
      const editorSnapshotHash = createEditorSnapshotDirtyStateHash({
         title: savedDocument.title,
         metadata: savedDocument.metadata,
         output: {
            blocks: savedDocument.blocks.map((block) => ({
               type: block.type,
               data: block.data
            }))
         }
      });

      expect(editorSnapshotHash).toBe(savedHash);
   });

   it("ignores runtime-only sql fields in dirty-state hashing", () => {
      const sqlDocument = createDocument({
         blocks: [
            {
               id: "22222222-2222-2222-2222-222222222222",
               type: "sql",
               data: {
                  title: "SQL Query",
                  code: "select 1"
               }
            }
         ]
      });

      const savedHash = createNotebookDirtyStateHash(sqlDocument);
      const editorSnapshotHash = createEditorSnapshotDirtyStateHash({
         title: sqlDocument.title,
         metadata: sqlDocument.metadata,
         output: {
            blocks: [
               {
                  type: "sql",
                  data: {
                     code: "select 1",
                     title: "SQL Query",
                     isExecuting: true,
                     lastExecuted: Date.now()
                  }
               }
            ]
         }
      });

      expect(editorSnapshotHash).toBe(savedHash);
   });
});
