/** @jest-environment jsdom */

import React from "react";
import { render, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ArtifactType } from "@kontext-labs/schema";
import type { Artifact, ArtifactAction } from "@kontext-labs/schema";
import { useNotebookStore } from "@notebook/stores/notebookStore";
import NotebookViewer, { findFirstChangedBlockId } from "./NotebookViewer";

// The schema validates loaded documents, so block ids must be real UUIDs.
const BLOCK_A_ID = "8f2c9d1a-5f3e-4b7a-9c2d-111111111111";
const BLOCK_B_ID = "3e5b7c9f-8d2a-4f1e-b6c4-222222222222";

const SERVER_DOC = {
   title: "NB",
   created: 1,
   modified: 2000,
   blocks: [
      {
         id: BLOCK_A_ID,
         type: "paragraph",
         data: { text: "first" }
      },
      {
         id: BLOCK_B_ID,
         type: "header",
         data: { text: "Heading", level: 2 }
      }
   ]
};

const EMPTY_DOC = { title: "NB", created: 1, modified: 1000, blocks: [] };

let servedDoc: typeof SERVER_DOC = EMPTY_DOC;
const fileFetches = { count: 0 };

jest.mock("@kontext-labs/icons", () => ({
   DatabaseZapOutlined: () => null
}));

const fetchFileMock = jest.fn(async () => ({ id: "notebook-file-1" }));
const getFileBlobMock = jest.fn(async () => {
   fileFetches.count += 1;
   return { text: async () => JSON.stringify(servedDoc) };
});
const updateFileMock = jest.fn(async () => ({ success: true }));

jest.mock("@kontext-labs/file", () => ({
   useFileOperations: () => ({
      fetchFile: fetchFileMock,
      getFileBlob: getFileBlobMock,
      updateFile: updateFileMock
   }),
   useJsonFileHelpers: jest.requireActual(
      "../../../file/src/hooks/useJsonFileHelpers"
   ).useJsonFileHelpers
}));

jest.mock("@kontext-labs/ui", () => ({
   __esModule: true,
   LoadingSpinner: () => null,
   useUiApp: () => ({ message: { error: jest.fn(), success: jest.fn() } })
}));

jest.mock("./NotebookSessionsSidebarTab", () => ({
   __esModule: true,
   default: () => null
}));

jest.mock("./NotebookEditor", () => ({
   __esModule: true,
   // Lowercase props-only function would trip the react-hooks lint rule; a
   // named component keeps it a valid React function component.
   default: function NotebookEditorMock(props: { instanceId?: string }) {
      const document = useNotebookStore(
         (state) =>
            state.getInstanceState(props.instanceId || "default")?.document
      );
      return React.createElement(
         "div",
         { "data-testid": "mock-editor" },
         (document?.blocks ?? []).map((block) =>
            React.createElement(
               "div",
               { "key": block.id, "data-testid": `block-${block.id}` },
               block.type
            )
         )
      );
   }
}));

const artifact = {
   id: "record-1",
   sessionId: "session-1",
   artifactId: "notebook-file-1",
   artifactType: ArtifactType.Notebook,
   title: "Notebook",
   meta: null
} as Artifact;

const INSTANCE_ID = "notebook-notebook-file-1";

const createViewer = (overrides?: {
   streamingActions?: ArtifactAction[];
   refreshToken?: number;
}) =>
   React.createElement(NotebookViewer, {
      artifact,
      projectId: "project-1",
      fileSystem: {},
      executionEngine: {},
      ...overrides
   });

const storeDocument = () =>
   useNotebookStore.getState().getInstanceState(INSTANCE_ID)?.document;

const upsertAction = (cid: string): ArtifactAction => ({
   actionType: "upsertBlock",
   sequence: 1,
   payload: {
      cid,
      blockType: "paragraph",
      data: { content: `content for ${cid}` },
      position: 0
   }
});

describe("NotebookViewer streaming + reconcile", () => {
   beforeEach(() => {
      Object.keys(useNotebookStore.getState().instances).forEach(
         (instanceId) => {
            useNotebookStore.getState().removeInstance(instanceId);
         }
      );
      servedDoc = EMPTY_DOC;
      fileFetches.count = 0;
   });

   it("creates the instance with the just-created (empty) server document", async () => {
      const utils = render(createViewer());

      await waitFor(() =>
         expect(utils.getByTestId("mock-editor")).toBeInTheDocument()
      );
      expect(storeDocument()?.blocks).toEqual([]);
   });

   it("applies streamed block actions that arrive after mount", async () => {
      const utils = render(createViewer({ streamingActions: [] }));

      await waitFor(() =>
         expect(
            useNotebookStore.getState().getInstanceState(INSTANCE_ID)
         ).toBeDefined()
      );

      utils.rerender(
         createViewer({ streamingActions: [upsertAction(BLOCK_A_ID)] })
      );

      await waitFor(() =>
         expect(storeDocument()?.blocks.map((block) => block.id)).toEqual([
            BLOCK_A_ID
         ])
      );
   });

   it("reconciles missed replay from the persisted server document on refresh", async () => {
      // Live replay missed every action; the server doc is the truth.
      servedDoc = SERVER_DOC;

      const utils = render(createViewer({ streamingActions: [] }));
      await waitFor(() =>
         expect(
            useNotebookStore.getState().getInstanceState(INSTANCE_ID)
         ).toBeDefined()
      );

      utils.rerender(createViewer({ refreshToken: 1 }));

      await waitFor(
         () => {
            expect(storeDocument()?.blocks.map((block) => block.id)).toEqual([
               BLOCK_A_ID,
               BLOCK_B_ID
            ]);
         },
         { timeout: 2000 }
      );
   });

   it("focuses the newest appended block when reconciliation applies additions", async () => {
      // Viewer mounted with the empty server document, then the agent's adds
      // landed only server-side: reconcile both applies them and scrolls to
      // the newest appended block instead of leaving the reader at the top.
      servedDoc = EMPTY_DOC;
      const utils = render(createViewer({ streamingActions: [] }));
      await waitFor(() => expect(storeDocument()?.blocks).toEqual([]));

      servedDoc = SERVER_DOC;
      utils.rerender(createViewer({ refreshToken: 1 }));

      await waitFor(
         () => {
            expect(
               useNotebookStore.getState().getInstanceState(INSTANCE_ID)
                  ?.focusedBlockId
            ).toBe(BLOCK_B_ID);
         },
         { timeout: 2000 }
      );
   });

   it("skips the reconcile when the viewer holds unsaved user edits", async () => {
      const utils = render(createViewer({ streamingActions: [] }));
      await waitFor(() =>
         expect(
            useNotebookStore.getState().getInstanceState(INSTANCE_ID)
         ).toBeDefined()
      );
      const fetchesBefore = fileFetches.count;

      // The agent updated the server while the user has unsaved edits.
      servedDoc = SERVER_DOC;
      useNotebookStore.getState().setDirty(true, INSTANCE_ID);

      utils.rerender(createViewer({ refreshToken: 5 }));
      await waitFor(() => expect(fileFetches.count).toBe(fetchesBefore), {
         timeout: 1000
      });

      expect(storeDocument()?.blocks).toEqual([]);
      useNotebookStore.getState().setDirty(false, INSTANCE_ID);
   });

   it("keeps the document when a reconcile finds the same structure", async () => {
      // Live replay already delivered block-a into the empty document.
      const utils = render(
         createViewer({ streamingActions: [upsertAction(BLOCK_A_ID)] })
      );
      await waitFor(() =>
         expect(storeDocument()?.blocks.map((block) => block.id)).toEqual([
            BLOCK_A_ID
         ])
      );

      // The server now holds the identical block set with a newer stamp.
      servedDoc = {
         ...SERVER_DOC,
         modified: 3000,
         blocks: [SERVER_DOC.blocks[0]]
      };
      utils.rerender(createViewer({ refreshToken: 2 }));
      await waitFor(() => expect(fileFetches.count).toBeGreaterThan(1), {
         timeout: 2000
      });
      const fetchesAfterReconcile = fileFetches.count;

      // Structure matches -> the reconcile must NOT clobber the document.
      await new Promise((resolve) => setTimeout(resolve, 700));
      expect(storeDocument()?.blocks.map((block) => block.id)).toEqual([
         BLOCK_A_ID
      ]);
      expect(fileFetches.count).toBe(fetchesAfterReconcile);

      // A structurally different server doc does get adopted.
      servedDoc = SERVER_DOC;
      utils.rerender(createViewer({ refreshToken: 3 }));
      await waitFor(
         () => {
            expect(storeDocument()?.blocks.map((block) => block.id)).toEqual([
               BLOCK_A_ID,
               BLOCK_B_ID
            ]);
         },
         { timeout: 2000 }
      );
   });
});

describe("findFirstChangedBlockId", () => {
   const block = (id: string, text: string) => ({
      type: "paragraph",
      id,
      data: { text }
   });

   it("returns null when documents are identical or next is empty", () => {
      const a = [block(BLOCK_A_ID, "same")];
      expect(findFirstChangedBlockId(a, a)).toBeNull();
      expect(findFirstChangedBlockId(a, [])).toBeNull();
   });

   it("resolves an empty previous document to the newest appended block", () => {
      // The agent added blocks to a notebook that was empty when the viewer
      // opened it: the first reconcile should scroll to the new content.
      expect(
         findFirstChangedBlockId([], [block(BLOCK_A_ID, "new content")])
      ).toBe(BLOCK_A_ID);
   });

   it("returns the first changed block and the newest appended block", () => {
      const before = [block(BLOCK_A_ID, "old"), block(BLOCK_B_ID, "keep")];
      const after = [block(BLOCK_A_ID, "changed"), block(BLOCK_B_ID, "keep")];
      expect(findFirstChangedBlockId(before, after)).toBe(BLOCK_A_ID);

      const appended = [...before, block("new-block-id", "new")];
      expect(findFirstChangedBlockId(before, appended)).toBe("new-block-id");
   });

   it("returns null on pure deletions (nothing left to scroll to)", () => {
      const before = [block(BLOCK_A_ID, "x"), block(BLOCK_B_ID, "y")];
      expect(findFirstChangedBlockId(before, [])).toBeNull();
   });
});
