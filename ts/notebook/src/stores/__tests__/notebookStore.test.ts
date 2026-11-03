import type { ArtifactAction } from "@kontext-labs/schema";
import { useNotebookStore } from "../notebookStore";

const INSTANCE_ID = "notebook-store-test";

const createDocument = (): NotebookDocument => ({
   title: "Notebook",
   created: 1,
   modified: 1,
   blocks: [
      {
         id: "11111111-1111-1111-1111-111111111111",
         type: "code",
         data: {
            code: "print('hello')",
            language: "python"
         }
      }
   ]
});

describe("notebookStore output actions", () => {
   beforeEach(() => {
      Object.keys(useNotebookStore.getState().instances).forEach(
         (instanceId) => {
            useNotebookStore.getState().removeInstance(instanceId);
         }
      );
   });

   it("applies setBlockOutput actions into code block outputs", () => {
      useNotebookStore.getState().createInstance(INSTANCE_ID, {
         document: createDocument()
      });

      const action: ArtifactAction = {
         actionType: "setBlockOutput",
         sequence: 1,
         payload: {
            cid: "11111111-1111-1111-1111-111111111111",
            outputs: [
               {
                  type: "text",
                  mimeType: "text/plain",
                  content: "done"
               }
            ]
         }
      };

      useNotebookStore.getState().applyActions([action], INSTANCE_ID);

      const state = useNotebookStore.getState().getInstanceState(INSTANCE_ID);
      const block = state?.document?.blocks[0];

      expect(block?.type).toBe("code");
      expect(block?.data).toMatchObject({
         language: "python",
         outputs: [
            {
               type: "text",
               mimeType: "text/plain",
               content: "done"
            }
         ]
      });
   });

   it("focuses the executed block when setBlockOutput lands", () => {
      useNotebookStore.getState().createInstance(INSTANCE_ID, {
         document: createDocument()
      });

      const blockId = "11111111-1111-1111-1111-111111111111";
      useNotebookStore.getState().applyActions(
         [
            {
               actionType: "setBlockOutput",
               sequence: 1,
               payload: {
                  cid: blockId,
                  outputs: null
               }
            } as unknown as ArtifactAction
         ],
         INSTANCE_ID
      );

      const state = useNotebookStore.getState().getInstanceState(INSTANCE_ID);
      expect(state?.focusedBlockId).toBe(blockId);
   });

   it("focusBlock targets a block and clearFocus releases it", () => {
      useNotebookStore.getState().createInstance(INSTANCE_ID, {
         document: createDocument()
      });

      useNotebookStore
         .getState()
         .focusBlock("11111111-1111-1111-1111-111111111111", INSTANCE_ID);
      expect(
         useNotebookStore.getState().getInstanceState(INSTANCE_ID)
            ?.focusedBlockId
      ).toBe("11111111-1111-1111-1111-111111111111");

      useNotebookStore.getState().clearFocus(INSTANCE_ID);
      expect(
         useNotebookStore.getState().getInstanceState(INSTANCE_ID)
            ?.focusedBlockId
      ).toBeNull();
   });
});
