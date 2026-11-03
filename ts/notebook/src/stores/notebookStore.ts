import { logger } from "@kontext-tech/common";
import type { ArtifactAction } from "@kontext-tech/schema";
import type {
   ChartBlock,
   CodeBlock,
   NotebookBlock,
   NotebookDocument,
   NotebookMetadata,
   SqlBlock
} from "@notebook/types/notebook";
import {
   normalizeCodeBlockData,
   normalizeNotebookDocument
} from "@notebook/utils/codeBlock";
import { create } from "zustand";
import { devtools, subscribeWithSelector } from "zustand/middleware";

// Individual notebook instance state
interface NotebookInstanceState {
   // Document state (persistent)
   document: NotebookDocument | null;
   isDirty: boolean;
   mode: "editor" | "preview";
   isInitialized: boolean;

   // Runtime state (not persisted)
   // Note: data tables are managed by querySessionStore for session creation

   // Action tracking
   lastAppliedSequence: number; // Track the last sequence number applied
   appliedSequences: Set<string>; // Set of all applied sequence identifiers to prevent double-processing
   pendingActions: ArtifactAction[]; // Queue of actions waiting to be applied to the editor
   focusedBlockId: string | null;

   // Theme and config
   isDarkMode: boolean;
   readonly: boolean;
   sidebarMode: "sidebar" | "popup";
}

// Main store state interface - manages multiple notebook instances
/**
 * Usage Pattern:
 *
 * 1. Parent component creates instance:
 *    ```ts
 *    useEffect(() => {
 *       if (!notebook) return;
 *       const existing = useNotebookStore.getState().getInstanceState(instanceId);
 *       if (!existing) {
 *          createInstance(instanceId, { document: notebook, readonly, sidebarMode: 'popup' });
 *       }
 *    }, [notebook?.modified, readonly, instanceId]);
 *    ```
 *
 * 2. Parent handles document updates:
 *    ```ts
 *    useEffect(() => {
 *       const existing = useNotebookStore.getState().getInstanceState(instanceId);
 *       if (existing && notebook.modified > (existing.document?.modified || 0)) {
 *          setDocument(notebook, instanceId);
 *       }
 *    }, [notebook]);
 *    ```
 *
 * 3. Parent applies streaming actions:
 *    ```ts
 *    useEffect(() => {
 *       if (streamingActions.length > 0) {
 *          applyActions(streamingActions, instanceId);
 *       }
 *    }, [streamingActions]);
 *    ```
 *
 * 4. NotebookEditor syncs store → EditorJS automatically via internal effects
 *
 * 5. Parent cleans up on unmount:
 *    ```ts
 *    useEffect(() => () => removeInstance(instanceId), [instanceId]);
 *    ```
 */
interface NotebookState {
   // Map of notebook instances by instanceId (e.g., artifact ID)
   instances: Record<string, NotebookInstanceState>;
}

// Store actions interface
interface NotebookActions {
   // Instance management
   createInstance: (
      instanceId: string,
      config?: {
         document?: NotebookDocument;
         isDarkMode?: boolean;
         readonly?: boolean;
         sidebarMode?: "sidebar" | "popup";
      }
   ) => void;
   removeInstance: (instanceId: string) => void;
   getInstanceState: (instanceId: string) => NotebookInstanceState | undefined;
   // Document actions (work on active instance or specified instance)
   setDocument: (document: NotebookDocument, instanceId: string) => void;
   updateDocument: (
      updater: (doc: NotebookDocument) => NotebookDocument,
      instanceId: string
   ) => void;
   setMode: (mode: "editor" | "preview", instanceId: string) => void;
   setDirty: (isDirty: boolean, instanceId: string) => void;
   updateMetadata: (
      metadata: Partial<NotebookMetadata>,
      instanceId: string
   ) => void;

   // Block actions (work on active instance or specified instance)
   updateBlockData: <T extends NotebookBlock>(
      blockId: string,
      data: Partial<T["data"]>,
      instanceId: string,
      options?: {
         /**
          * Whether this update should mark the notebook as having unsaved changes.
          * Use false for runtime/UI-only fields (e.g. execution state).
          */
         markDirty?: boolean;
      }
   ) => void;

   // SQL block actions
   updateSqlBlock: (
      blockId: string,
      updates: Partial<SqlBlock["data"]>,
      instanceId: string
   ) => void;
   updateSqlBlockRuntime: (
      blockId: string,
      updates: Partial<SqlBlock["data"]>,
      instanceId: string
   ) => void;
   clearSqlResult: (blockId: string, instanceId: string) => void;

   // Chart block actions
   updateChartConfig: (
      blockId: string,
      config: Partial<ChartBlock["data"]>,
      instanceId: string
   ) => void;

   // Block getters (work on active instance or specified instance)
   getSqlBlock: (blockId: string, instanceId: string) => SqlBlock | undefined;
   getCodeBlock: (blockId: string, instanceId: string) => CodeBlock | undefined;
   getChartBlock: (
      blockId: string,
      instanceId: string
   ) => ChartBlock | undefined;

   // Configuration (work on active instance or specified instance)
   setTheme: (isDarkMode: boolean, instanceId: string) => void;
   setReadonly: (readonly: boolean, instanceId: string) => void;
   setSidebarMode: (mode: "sidebar" | "popup", instanceId: string) => void;
   /** Scroll target: focus a block so the editor scrolls it into view. */
   focusBlock: (blockId: string, instanceId: string) => void;
   clearFocus: (instanceId: string) => void;

   // Action replay for streaming updates
   applyActions: (
      actions: ArtifactAction[],
      instanceId: string,
      onSequenceGap?: (expected: number, received: number) => void
   ) => {
      applied: number;
      appliedActions: ArtifactAction[];
      gaps: number;
   };

   /**
    * Clears actions from the pending queue after they've been successfully
    * applied to the EditorJS instance.
    */
   clearPendingActions: (actions: ArtifactAction[], instanceId: string) => void;
}

// Store type
type NotebookStore = NotebookState & NotebookActions;

// Helper function to get or create instance
const getOrCreateInstance = (
   state: NotebookState,
   instanceId: string
): NotebookInstanceState => {
   if (!state.instances[instanceId]) {
      return {
         document: null,
         isDirty: false,
         mode: "editor",
         isInitialized: false,
         isDarkMode: false,
         readonly: false,
         sidebarMode: "sidebar",
         lastAppliedSequence: 0,
         appliedSequences: new Set<string>(),
         pendingActions: [],
         focusedBlockId: null
      };
   }
   return state.instances[instanceId];
};

/**
 * Robust idempotency key to prevent double-processing of actions.
 * Combines sequence with CID (if available) or metadata field to handle
 * sequence collisions across different tools or tool calls.
 */
const getActionIdempotencyKey = (action: ArtifactAction): string => {
   const payload = action.payload as unknown as Record<string, unknown>;
   const targetId = payload?.cid || payload?.varField || "global";
   return `${action.actionType}:${targetId}:${action.sequence}`;
};

/**
 * Maximum number of applied-action idempotency keys retained per instance.
 * This set guards against duplicate delivery of streaming actions; once an
 * action is far enough behind `lastAppliedSequence` it will not be replayed,
 * so evicting the oldest keys keeps memory bounded on long-lived sessions.
 */
const MAX_APPLIED_SEQUENCES = 2000;
// Create the store
export const useNotebookStore = create<NotebookStore>()(
   devtools(
      subscribeWithSelector((set, get) => ({
         // Initial state
         instances: {},
         // Instance management
         createInstance: (instanceId, config = {}) => {
            const {
               document = null,
               isDarkMode = false,
               readonly = false,
               sidebarMode = "sidebar"
            } = config;

            set(
               (state) => ({
                  instances: {
                     ...state.instances,
                     [instanceId]: {
                        document: document
                           ? normalizeNotebookDocument(document)
                           : null,
                        isDarkMode,
                        readonly,
                        sidebarMode,
                        isDirty: false,
                        mode: "editor",
                        isInitialized: true,
                        lastAppliedSequence: 0,
                        appliedSequences: new Set<string>(),
                        pendingActions: [],
                        focusedBlockId: null
                     }
                  }
               }),
               false,
               "createInstance"
            );
         },

         removeInstance: (instanceId) => {
            set(
               (state) => {
                  const { [instanceId]: _removed, ...remainingInstances } =
                     state.instances;
                  return {
                     instances: remainingInstances
                  };
               },
               false,
               "removeInstance"
            );
         },

         getInstanceState: (instanceId) => {
            return get().instances[instanceId];
         },
         // Document actions (work on active instance or specified instance)
         setDocument: (document, instanceId) => {
            set(
               (state) => {
                  const instance = getOrCreateInstance(state, instanceId);
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: {
                           ...instance,
                           document: normalizeNotebookDocument(document),
                           isDirty: false
                        }
                     }
                  };
               },
               false,
               "setDocument"
            );
         },

         updateDocument: (updater, instanceId) => {
            set(
               (state) => {
                  const instance = state.instances[instanceId];
                  if (!instance?.document) return {};
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: {
                           ...instance,
                           document: normalizeNotebookDocument(
                              updater(instance.document)
                           ),
                           isDirty: true
                        }
                     }
                  };
               },
               false,
               "updateDocument"
            );
         },

         setMode: (mode, instanceId) => {
            set(
               (state) => {
                  const instance = getOrCreateInstance(state, instanceId);
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: { ...instance, mode }
                     }
                  };
               },
               false,
               "setMode"
            );
         },

         setDirty: (isDirty, instanceId) => {
            set(
               (state) => {
                  const existingInstance = state.instances[instanceId];
                  if (existingInstance && existingInstance.isDirty === isDirty)
                     return {};

                  const instance = existingInstance
                     ? existingInstance
                     : getOrCreateInstance(state, instanceId);

                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: { ...instance, isDirty }
                     }
                  };
               },
               false,
               "setDirty"
            );
         },

         updateMetadata: (metadata, instanceId) => {
            set(
               (state) => {
                  const instance = state.instances[instanceId];
                  if (!instance?.document) return {};
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: {
                           ...instance,
                           document: {
                              ...instance.document,
                              metadata: {
                                 ...instance.document.metadata,
                                 ...metadata
                              }
                           },
                           isDirty: true
                        }
                     }
                  };
               },
               false,
               "updateMetadata"
            );
         },

         // Block actions (work on active instance or specified instance)
         updateBlockData: (blockId, data, instanceId, options) => {
            set(
               (state) => {
                  const instance = state.instances[instanceId];
                  if (!instance?.document) return {};

                  const markDirty = options?.markDirty ?? true;

                  const newBlocks = instance.document.blocks.map((block) => {
                     if (block.id === blockId) {
                        if (block.type === "code") {
                           return {
                              ...block,
                              data: normalizeCodeBlockData({
                                 ...block.data,
                                 ...(data as Partial<CodeBlock["data"]>)
                              })
                           };
                        }

                        return { ...block, data: { ...block.data, ...data } };
                     }
                     return block;
                  });

                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: {
                           ...instance,
                           document: {
                              ...instance.document,
                              blocks: newBlocks as NotebookBlock[]
                           },
                           isDirty: markDirty ? true : instance.isDirty
                        }
                     }
                  };
               },
               false,
               "updateBlockData"
            );
         },

         // SQL block actions
         updateSqlBlock: (blockId, updates, instanceId) => {
            get().updateBlockData<SqlBlock>(blockId, updates, instanceId);
         },

         updateSqlBlockRuntime: (blockId, updates, instanceId) => {
            get().updateBlockData<SqlBlock>(blockId, updates, instanceId, {
               markDirty: false
            });
         },

         clearSqlResult: (blockId, instanceId) => {
            // Simply clear the data ID - no document cleanup needed
            get().updateBlockData<SqlBlock>(
               blockId,
               {
                  dataRef: undefined,
                  inlineData: undefined
               },
               instanceId
            );
         },

         // Chart block actions
         updateChartConfig: (blockId, config, instanceId) => {
            get().updateBlockData<ChartBlock>(blockId, config, instanceId);
         },

         // Block getters (work on active instance or specified instance)
         getSqlBlock: (blockId, instanceId) => {
            const instance = get().instances[instanceId];
            return instance?.document?.blocks.find(
               (block): block is SqlBlock =>
                  block.id === blockId && block.type === "sql"
            );
         },
         getCodeBlock: (blockId, instanceId) => {
            const instance = get().instances[instanceId];
            return instance?.document?.blocks.find(
               (block): block is CodeBlock =>
                  block.id === blockId && block.type === "code"
            );
         },

         getChartBlock: (blockId, instanceId) => {
            const instance = get().instances[instanceId];
            return instance?.document?.blocks.find(
               (block): block is ChartBlock =>
                  block.id === blockId && block.type === "chart"
            );
         },

         // Configuration (work on active instance or specified instance)
         setTheme: (isDarkMode, instanceId) => {
            set(
               (state) => {
                  const instance = getOrCreateInstance(state, instanceId);
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: { ...instance, isDarkMode }
                     }
                  };
               },
               false,
               "setTheme"
            );
         },

         setReadonly: (readonly, instanceId) => {
            set(
               (state) => {
                  const instance = getOrCreateInstance(state, instanceId);
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: { ...instance, readonly }
                     }
                  };
               },
               false,
               "setReadonly"
            );
         },

         setSidebarMode: (sidebarMode, instanceId) => {
            set(
               (state) => {
                  const instance = getOrCreateInstance(state, instanceId);
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: { ...instance, sidebarMode }
                     }
                  };
               },
               false,
               "setSidebarMode"
            );
         },

         // Action replay for streaming updates
         applyActions: (actions, instanceId) => {
            const instance = get().instances[instanceId];
            if (!instance || !instance.document) {
               console.warn(
                  `[NotebookStore] No instance or document for ${instanceId}`
               );
               return { applied: 0, appliedActions: [], gaps: 0 };
            }

            // Sort by sequence (expected to be high-precision high-precision unix timestamp)
            const sortedActions = [...actions].sort(
               (a, b) => a.sequence - b.sequence
            );

            let lastAppliedActions: ArtifactAction[] = [];

            set(
               (state) => {
                  const inst = state.instances[instanceId];
                  if (!inst || !inst.document) return {};

                  let currentDocument = { ...inst.document };
                  let currentFocusedBlockId = inst.focusedBlockId;
                  const currentAppliedSequences = new Set(
                     inst.appliedSequences
                  );
                  const batchAppliedActions: ArtifactAction[] = [];
                  let lastSeq = inst.lastAppliedSequence;

                  for (const action of sortedActions) {
                     const idempotencyKey = getActionIdempotencyKey(action);

                     // IDEMPOTENCY: Skip if this specific action was already applied
                     if (currentAppliedSequences.has(idempotencyKey)) {
                        continue;
                     }

                     try {
                        switch (action.actionType) {
                           case "upsertBlock": {
                              const { cid, blockType, data, position } =
                                 action.payload;
                              const existingIndex =
                                 currentDocument.blocks.findIndex(
                                    (b) => b.id === cid
                                 );

                              const newBlocks = [...currentDocument.blocks];
                              if (existingIndex >= 0) {
                                 const existing = newBlocks[existingIndex];
                                 // Type cast needed: spreading data across discriminated union types
                                 newBlocks[existingIndex] = {
                                    ...existing,
                                    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
                                    // @ts-ignore
                                    type: blockType,
                                    data: {
                                       ...(existing.data as unknown as Record<
                                          string,
                                          unknown
                                       >),
                                       ...(data as unknown as Record<
                                          string,
                                          unknown
                                       >)
                                    }
                                 } as unknown as NotebookBlock;
                              } else {
                                 // Type cast needed: data shape varies by blockType (discriminated union)
                                 const newBlock = {
                                    id: cid,
                                    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
                                    // @ts-ignore
                                    type: blockType,
                                    data: data as unknown as Record<
                                       string,
                                       unknown
                                    >
                                 } as unknown as NotebookBlock;
                                 if (
                                    position !== undefined &&
                                    position !== null &&
                                    position < newBlocks.length
                                 ) {
                                    newBlocks.splice(position, 0, newBlock);
                                 } else {
                                    newBlocks.push(newBlock);
                                 }

                                 // Frontend Heuristic: Focus new blocks
                                 currentFocusedBlockId = cid;
                              }

                              currentDocument = {
                                 ...currentDocument,
                                 blocks: newBlocks
                              };
                              break;
                           }

                           case "patchBlockContent": {
                              const { cid, field, value } = action.payload;
                              if (field) {
                                 const blockIndex =
                                    currentDocument.blocks.findIndex(
                                       (b) => b.id === cid
                                    );
                                 if (blockIndex >= 0) {
                                    const newBlocks = [
                                       ...currentDocument.blocks
                                    ];
                                    const existing = newBlocks[blockIndex];
                                    // Type cast needed: field/value may not exist on all block types
                                    newBlocks[blockIndex] = {
                                       ...existing,
                                       data: {
                                          ...(existing.data as unknown as Record<
                                             string,
                                             unknown
                                          >),
                                          [field]: value
                                       }
                                    } as NotebookBlock;
                                    currentDocument = {
                                       ...currentDocument,
                                       blocks: newBlocks
                                    };

                                    // Frontend Heuristic: Keep focus while patching
                                    currentFocusedBlockId = cid;
                                 }
                              }
                              break;
                           }

                           case "setBlockOutput": {
                              const { cid, outputs } = action.payload;
                              const blockIndex =
                                 currentDocument.blocks.findIndex(
                                    (b) => b.id === cid
                                 );
                              if (blockIndex >= 0) {
                                 const newBlocks = [...currentDocument.blocks];
                                 const existing = newBlocks[blockIndex];
                                 // Type cast needed: output is runtime-only field not in all schemas
                                 newBlocks[blockIndex] = {
                                    ...existing,
                                    data: {
                                       ...(existing.data as unknown as Record<
                                          string,
                                          unknown
                                       >),
                                       outputs
                                    }
                                 } as unknown as NotebookBlock;
                                 currentDocument = {
                                    ...currentDocument,
                                    blocks: newBlocks
                                 };
                                 // The agent just finished running this block: bring
                                 // its results into view (same as new-block upserts).
                                 currentFocusedBlockId = cid;
                              }
                              break;
                           }

                           case "removeBlock": {
                              const { cid } = action.payload;
                              currentDocument = {
                                 ...currentDocument,
                                 blocks: currentDocument.blocks.filter(
                                    (b) => b.id !== cid
                                 )
                              };
                              break;
                           }

                           case "updateMetadata": {
                              const { varField, value } = action.payload;
                              if (varField) {
                                 currentDocument = {
                                    ...currentDocument,
                                    metadata: {
                                       ...currentDocument.metadata,
                                       [varField]: value
                                    }
                                 };
                              }
                              break;
                           }
                        }

                        currentAppliedSequences.add(idempotencyKey);
                        lastSeq = Math.max(lastSeq, action.sequence);
                        batchAppliedActions.push(action);

                        // Bound the idempotency set so memory does not grow
                        // without limit while streaming into a long-lived
                        // notebook session. Evict the oldest keys first; actions
                        // far enough behind lastAppliedSequence will not replay.
                        if (
                           currentAppliedSequences.size > MAX_APPLIED_SEQUENCES
                        ) {
                           const overflow =
                              currentAppliedSequences.size -
                              MAX_APPLIED_SEQUENCES;
                           let removed = 0;
                           for (const key of currentAppliedSequences) {
                              currentAppliedSequences.delete(key);
                              if (++removed >= overflow) {
                                 break;
                              }
                           }
                        }
                     } catch (err) {
                        console.error(
                           `[NotebookStore] Error applying action ${action.actionType}:`,
                           err
                        );
                        // Continue with next action in batch
                     }
                  }

                  // Share reference with outer scope for the return value
                  lastAppliedActions = batchAppliedActions;

                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: {
                           ...inst,
                           document: currentDocument,
                           lastAppliedSequence: lastSeq,
                           appliedSequences: currentAppliedSequences,
                           pendingActions: [
                              ...inst.pendingActions,
                              ...batchAppliedActions
                           ],
                           focusedBlockId: currentFocusedBlockId,
                           isDirty: false
                        }
                     }
                  };
               },
               false,
               "applyActions"
            );

            if (lastAppliedActions.length > 0) {
               logger.debug(
                  `[NotebookStore] Applied ${lastAppliedActions.length} actions to ${instanceId}:`,
                  lastAppliedActions.map((a) => a.actionType)
               );
            }

            return {
               applied: lastAppliedActions.length,
               appliedActions: lastAppliedActions,
               gaps: 0
            };
         },

         clearPendingActions: (actions, instanceId) => {
            set(
               (state) => {
                  const inst = state.instances[instanceId];
                  if (!inst) return {};

                  // Create a set of action IDs to remove
                  const idsToRemove = new Set(
                     actions.map((a) => getActionIdempotencyKey(a))
                  );

                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: {
                           ...inst,
                           pendingActions: inst.pendingActions.filter(
                              (a: ArtifactAction) =>
                                 !idsToRemove.has(getActionIdempotencyKey(a))
                           )
                        }
                     }
                  };
               },
               false,
               "clearPendingActions"
            );
         },

         clearFocus: (instanceId) => {
            set(
               (state) => {
                  const instance = state.instances[instanceId];
                  if (!instance) return {};
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: { ...instance, focusedBlockId: null }
                     }
                  };
               },
               false,
               "clearFocus"
            );
         },

         focusBlock: (blockId, instanceId) => {
            set(
               (state) => {
                  const instance = state.instances[instanceId];
                  if (!instance) return {};
                  return {
                     instances: {
                        ...state.instances,
                        [instanceId]: { ...instance, focusedBlockId: blockId }
                     }
                  };
               },
               false,
               "focusBlock"
            );
         }
      })),
      {
         name: "notebook-store"
      }
   )
);
