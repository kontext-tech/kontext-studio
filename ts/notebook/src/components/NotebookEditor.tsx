import { logger } from "@kontext-labs/common";
import type { ArtifactAction } from "@kontext-labs/schema";
import { type BlockAPI, default as EditorJS } from "@editorjs/editorjs";
import {
   EditOutlined,
   ExportOutlined,
   EyeOutlined,
   ImportOutlined,
   MoreOutlined,
   PanelRightCloseOutlined,
   PanelRightOpenOutlined,
   SaveOutlined,
   SettingOutlined
} from "@kontext-labs/icons";
import { ThemeProvider, useTheme } from "@kontext-labs/theme";
import {
   ChartBlock,
   CustomCode,
   CustomDelimiter,
   CustomHeader,
   CustomImage,
   CustomList,
   CustomParagraph,
   CustomQuote,
   CustomTable,
   MermaidBlock,
   SqlBlock
} from "@notebook/blocks";
import {
   useNotebookServices,
   type NotebookPersistenceResult
} from "@notebook/context/NotebookServiceContext";
import { useNotebookStore } from "@notebook/stores/notebookStore";
import type {
   NotebookDocument,
   NotebookEditorProps,
   NotebookMetadata
} from "@notebook/types/notebook";
import { convertToEditorJSFormat } from "@notebook/utils/documentConverter";
import {
   cleanupEditor,
   createUpdatedDocument,
   getSavableEditor
} from "@notebook/utils/editorHelpers";
import {
   createEditorSnapshotDirtyStateHash,
   createNotebookDirtyStateHash,
   hashString
} from "@notebook/utils/documentDirtyState";
import { sharedReactRoot } from "@notebook/utils/sharedReactRoot";
import {
   App,
   Button,
   Checkbox,
   Drawer,
   Dropdown,
   Flex,
   Input,
   Layout,
   Space,
   theme,
   Tooltip
} from "antd";
import React, {
   useCallback,
   useEffect,
   useMemo,
   useRef,
   useState
} from "react";
import { NOTEBOOK_FILE_EXTENSION } from "../constants";
import "../styles/editorjs-theme.css";
import NotebookPreview from "./NotebookPreview";
import NotebookSidebar from "./NotebookSidebar";

const { Content, Sider } = Layout;

// Stable fallback: a Zustand selector must return the same reference for
// unchanged state, otherwise useSyncExternalStore re-renders in an infinite
// loop before the instance exists.
const EMPTY_PENDING_ACTIONS: ArtifactAction[] = [];

/**
 * Nearest scrollable ancestor of the editor holder — the element whose
 * scrollTop must be preserved across wholesale EditorJS re-renders.
 */
const findScrollContainer = (start: HTMLElement | null): HTMLElement | null => {
   let element = start?.parentElement ?? null;
   while (element) {
      const overflowY = window.getComputedStyle(element).overflowY;
      if (overflowY === "auto" || overflowY === "scroll") {
         return element;
      }
      element = element.parentElement;
   }
   return null;
};

/**
 * NotebookEditor component for creating and editing notebook documents
 *
 * IMPORTANT: This component does NOT manage store instances. Parent components
 * (NotebookViewer, NotebookDetailPage, etc.) must create the instance via
 * `createInstance(instanceId, {...})` before rendering NotebookEditor.
 *
 * The component is responsible for:
 * - Rendering the EditorJS instance
 * - Syncing store state to EditorJS (blocks, actions)
 * - Tracking dirty state for unsaved changes
 * - Handling save/export operations
 *
 * The component accepts document-level configuration for SQL blocks,
 * including an SQL executor and available catalog entities. These are stored
 * in the notebookDocumentStore and accessible to all SQL blocks in the document.
 *
 * @param instanceId - Required instance ID (must match parent's createInstance call)
 * @param document - Optional NotebookDocument to edit (deprecated, use store)
 * @param defaultTitle - Default title for new documents (defaults to "Untitled Notebook")
 * @param onSave - Callback when document is saved
 * @param onExport - Callback when document is exported
 * @param onDirtyChange - Callback when document dirty state changes
 * @param readonly - Whether the document is read-only
 * @param sidebarExtensions - Optional host-owned sidebar tabs shown before metadata
 */
const NotebookEditor: React.FC<NotebookEditorProps> = ({
   instanceId,
   onSave,
   onExport,
   onDirtyChange,
   readonly = false,
   previewMode = false,
   cultures = [],
   saveButtonText = "Save",
   saveButtonIcon = <SaveOutlined />,
   enableSqlBlock: enableDataBlocks = false,
   enableChartBlock: enableChartBlocks = false,
   includeFrontmatter: _includeFrontmatter = true,
   showArticleMetadata = false,
   showSaveAsDraft = true,
   defaultTitle = "Untitled Notebook",
   maxHeight = "100vh",
   showHeader = true,
   projectId,
   errorHandler,
   sidebarExtensions = []
}) => {
   const { message, modal } = App.useApp();
   const { useToken } = theme;
   const { token } = useToken();
   const themeContextValue = useTheme();
   const { isDarkMode, themeConfig } = themeContextValue;

   // Get file service from context
   const {
      fileSystem,
      executionEngine,
      notebookId: contextNotebookId,
      projectCode,
      onViewExecutionRun
   } = useNotebookServices();

   // Get state from Zustand store (with optional instance support)
   const document = useNotebookStore(
      (state) => state.getInstanceState(instanceId || "default")?.document
   );
   const sidebarMode = useNotebookStore(
      (state) =>
         state.getInstanceState(instanceId || "default")?.sidebarMode ||
         "sidebar"
   );
   const setSidebarMode = useNotebookStore((state) => state.setSidebarMode);
   const focusedBlockId = useNotebookStore(
      (state) =>
         state.getInstanceState(instanceId || "default")?.focusedBlockId || null
   );
   const pendingActions = useNotebookStore(
      (state) =>
         state.getInstanceState(instanceId || "default")?.pendingActions ??
         EMPTY_PENDING_ACTIONS
   );
   const lastAppliedSequence = useNotebookStore(
      (state) =>
         state.getInstanceState(instanceId || "default")?.lastAppliedSequence ||
         0
   );
   const clearFocus = useNotebookStore((state) => state.clearFocus);
   const clearPendingActions = useNotebookStore(
      (state) => state.clearPendingActions
   );
   const [rightPanelOpen, setRightPanelOpen] = useState(true);
   const [isEditorLoading, setIsEditorLoading] = useState(true);
   const [isTitleHovered, setIsTitleHovered] = useState(false);
   const [internalPreviewMode, setInternalPreviewMode] = useState<
      boolean | null
   >(null);
   const [isDirty, setIsDirty] = useState(false);
   const [showMetadataModal, setShowMetadataModal] = useState(false);

   // Reference to track current document for dynamic access in callbacks
   const currentDocumentRef = useRef(document);
   const processingActionsRef = useRef(false);

   // Use internal preview state if set, otherwise fall back to prop
   const effectivePreviewMode =
      internalPreviewMode !== null ? internalPreviewMode : previewMode;

   // Collapse metadata panel in preview mode or when using popup mode
   const effectiveRightPanelOpen = effectivePreviewMode
      ? false
      : sidebarMode === "sidebar"
        ? rightPanelOpen
        : false;

   const editorRef = useRef<EditorJS | null>(null);
   const containerRef = useRef<HTMLDivElement>(null);
   const isInitialized = useRef(false);
   const initializationInProgress = useRef(false);
   const lastDocumentId = useRef<number | null>(null);
   const lastRenderedContent = useRef<string | null>(null);
   const editorInstanceId = useRef<string>(crypto.randomUUID()); // Unique instance ID

   // Memoize editor tools configuration to prevent unnecessary re-initializations
   const editorTools = useMemo(
      () => ({
         header: {
            class: CustomHeader as unknown as EditorJS.BlockToolConstructable,
            config: {
               placeholder: "Enter a header",
               levels: [2, 3, 4, 5],
               defaultLevel: 2
            }
         },
         list: {
            class: CustomList as unknown as EditorJS.BlockToolConstructable,
            inlineToolbar: true,
            config: {
               defaultStyle: "unordered"
            }
         },
         quote: {
            class: CustomQuote as unknown as EditorJS.BlockToolConstructable,
            inlineToolbar: true,
            config: {
               quotePlaceholder: "Enter a quote",
               captionPlaceholder: "Quote's author"
            }
         },
         code: {
            class: CustomCode as unknown as EditorJS.BlockToolConstructable,
            config: {
               placeholder: "Enter code",
               instanceId,
               projectId
            }
         },
         mermaid: {
            class: MermaidBlock as unknown as EditorJS.BlockToolConstructable,
            config: {
               message,
               modal,
               instanceId
            }
         },
         paragraph: {
            class: CustomParagraph as unknown as EditorJS.BlockToolConstructable,
            inlineToolbar: true,
            config: {
               preserveBlank: false
            }
         },
         delimiter: {
            class: CustomDelimiter as unknown as EditorJS.BlockToolConstructable
         },
         table: {
            class: CustomTable as unknown as EditorJS.BlockToolConstructable,
            inlineToolbar: true,
            config: {
               rows: 2,
               cols: 3
            }
         },
         image: {
            class: CustomImage as unknown as EditorJS.BlockToolConstructable,
            config: {
               uploader: {
                  uploadByFile: async (file: File) => {
                     if (!projectId) {
                        message.error(
                           "Project ID is required for image upload."
                        );
                        console.error(
                           "projectId prop is not provided to NotebookEditor."
                        );
                        return { success: 0 };
                     }

                     try {
                        if (!fileSystem?.uploadImage) {
                           message.error("Image upload is not configured.");
                           return { success: 0 };
                        }

                        const result = await fileSystem.uploadImage(
                           projectId,
                           file
                        );
                        const uploadedUrl =
                           typeof result === "string"
                              ? result
                              : result.data?.url;

                        if (uploadedUrl) {
                           return {
                              success: 1,
                              file: { url: uploadedUrl }
                           };
                        }

                        message.error(
                           (typeof result !== "string"
                              ? result.error?.messages.join(", ")
                              : undefined) || "Image upload failed."
                        );
                        return { success: 0 };
                     } catch (error) {
                        console.error("Image upload error:", error);
                        message.error("Image upload failed.");
                        return { success: 0 };
                     }
                  },
                  uploadByUrl: (url: string) => {
                     return Promise.resolve({
                        success: 1,
                        file: { url }
                     });
                  }
               },
               // File service passed via NotebookServiceProvider context
               projectId,
               fileSystem
            }
         },
         ...(enableChartBlocks
            ? {
                 chart: {
                    class: ChartBlock as unknown as EditorJS.BlockToolConstructable,
                    config: {
                       message,
                       modal,
                       instanceId
                    }
                 }
              }
            : {}),
         ...(enableDataBlocks
            ? {
                 sql: {
                    class: SqlBlock as unknown as EditorJS.BlockToolConstructable,
                    config: {
                       message,
                       modal,
                       projectId,
                       errorHandler,
                       instanceId
                    }
                 }
              }
            : {})
      }),
      [
         enableDataBlocks,
         enableChartBlocks,
         projectId,
         fileSystem,
         message,
         modal,
         errorHandler,
         instanceId
      ]
   );

   // Compute derived values
   const showSaveButton = !readonly && !effectivePreviewMode;
   const showEditToggleButton = !readonly;
   const isEditButtonDisabled = isEditorLoading;

   // EditorJS can emit onChange during initial render/rehydration.
   // We suppress these so a freshly-loaded notebook doesn't become "dirty".
   const suppressEditorOnChangeRef = useRef(true);

   // Track a stable baseline of the editor content so focus/scroll/selection
   // events that trigger EditorJS onChange don't mark the document dirty.
   const baselineContentHashRef = useRef<string | null>(null);
   const pendingDirtyCheckTimeoutRef = useRef<number | null>(null);

   // Avoid expensive editor.save() calls on every change.
   // We can safely skip hashing once we're already dirty; we only need to
   // detect the initial transition to dirty. Clearing dirty (undo back to
   // baseline) is handled with a slower debounce.
   const isDirtyRef = useRef(false);
   useEffect(() => {
      isDirtyRef.current = isDirty;
   }, [isDirty]);

   const computeStableHashFromDocument = useCallback(
      (doc: NotebookDocument) => {
         return createNotebookDirtyStateHash(doc);
      },
      []
   );

   const computeStableHashFromEditor = useCallback(
      async (editorInstance: EditorJS | null = editorRef.current) => {
         const savableEditor = await getSavableEditor(editorInstance);

         if (!savableEditor) {
            return null;
         }

         const output = await savableEditor.save();
         return createEditorSnapshotDirtyStateHash({
            title: currentDocumentRef.current?.title,
            metadata: currentDocumentRef.current?.metadata,
            output
         });
      },
      []
   );

   const setDirty = useCallback(
      (dirty: boolean) => {
         setIsDirty((prev) => {
            if (prev === dirty) return prev;
            onDirtyChange?.(dirty);
            return dirty;
         });
      },
      [onDirtyChange]
   );

   const persistCurrentNotebook =
      useCallback(async (): Promise<NotebookPersistenceResult> => {
         if (!onSave) {
            return {
               success: false,
               error: "Notebook save is not available."
            };
         }

         if (!currentDocumentRef.current) {
            return {
               success: false,
               error: "Notebook document is not ready to save."
            };
         }

         try {
            const updatedDocument = await createUpdatedDocument(
               currentDocumentRef.current,
               editorRef,
               defaultTitle,
               isEditorLoading,
               instanceId
            );

            await onSave(updatedDocument);

            baselineContentHashRef.current =
               computeStableHashFromDocument(updatedDocument);
            setDirty(false);
            useNotebookStore
               .getState()
               .setDirty(false, instanceId || "default");

            return { success: true };
         } catch (error) {
            console.error("Error persisting notebook state:", error);
            return {
               success: false,
               error:
                  error instanceof Error
                     ? error.message
                     : "Failed to save notebook"
            };
         }
      }, [
         onSave,
         defaultTitle,
         isEditorLoading,
         instanceId,
         computeStableHashFromDocument,
         setDirty
      ]);

   const sharedRootServiceProps = useMemo(
      () => ({
         projectId,
         projectCode,
         notebookId: contextNotebookId,
         onViewExecutionRun,
         persistCurrentNotebook,
         fileSystem,
         executionEngine
      }),
      [
         contextNotebookId,
         executionEngine,
         fileSystem,
         onViewExecutionRun,
         persistCurrentNotebook,
         projectCode,
         projectId
      ]
   );

   const sharedRootProviders = useMemo(
      () => ({
         configProvider: {
            theme: themeConfig,
            getPopupContainer: () =>
               globalThis.document?.body ||
               globalThis.document?.documentElement ||
               undefined
         },
         themeProvider: ThemeProvider,
         themeContextValue,
         // Pass the context value (not a provider component): the provider
         // element type must stay stable so binding updates re-render blocks
         // instead of remounting every chart/SQL block portal.
         notebookServiceValue: sharedRootServiceProps
      }),
      [sharedRootServiceProps, themeConfig, themeContextValue]
   );

   // Initialize shared React root for blocks
   useEffect(() => {
      const currentInstanceId = editorInstanceId.current;

      // Initialize shared React root with guard against React Strict Mode
      logger.debug(
         "🔧 Initializing shared React root for instance:",
         currentInstanceId
      );

      sharedReactRoot.initialize(currentInstanceId, sharedRootProviders);

      return () => {
         logger.debug(
            "🧹 Cleaning up shared React root for instance:",
            currentInstanceId
         );
         sharedReactRoot.destroy(currentInstanceId);
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
   }, []); // Only initialize once

   useEffect(() => {
      const store = useNotebookStore.getState();
      store.setTheme(isDarkMode, instanceId || "default");
   }, [isDarkMode, instanceId]);

   // Update shared React root providers when theme or services change
   useEffect(() => {
      sharedReactRoot.updateProviders(
         editorInstanceId.current,
         sharedRootProviders
      );
   }, [sharedRootProviders]);

   useEffect(() => {
      const store = useNotebookStore.getState();
      store.setReadonly(readonly, instanceId || "default");
   }, [readonly, instanceId]);

   // Keep document ref updated for dynamic access in callbacks
   useEffect(() => {
      currentDocumentRef.current = document;

      // Reset content hash when document changes to allow proper re-initialization
      if (document?.modified !== lastDocumentId.current) {
         logger.debug("📋 Document changed, resetting content hash");
         lastRenderedContent.current = null;
      }
   }, [document]);

   const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (document) {
         const newTitle = e.target.value;
         const store = useNotebookStore.getState();
         store.updateDocument(
            (currentDocument) => ({
               ...currentDocument,
               title: newTitle
            }),
            instanceId || "default"
         );
         setDirty(true);
      }
   };

   const handleTitleBlur = () => {
      if (document && document.title.trim() === "") {
         message.warning("Title cannot be empty. Reverted to default.");
         const store = useNotebookStore.getState();
         store.updateDocument(
            (currentDocument) => ({
               ...currentDocument,
               title: defaultTitle
            }),
            instanceId || "default"
         );
         setDirty(true);
      }
   };

   const handleMetadataChange = (metadata: NotebookMetadata) => {
      if (document) {
         const store = useNotebookStore.getState();
         store.updateDocument(
            (currentDocument) => ({
               ...currentDocument,
               metadata
            }),
            instanceId || "default"
         );
         setDirty(true);
      }
   };

   useEffect(() => {
      if (!containerRef.current || !document) return;

      // OPTIMIZATION: Instead of destroying the editor when switching to preview mode,
      // we keep it alive but hidden. This preserves all React components in the shared root
      // and avoids unnecessary re-mounting/unmounting when switching between modes.
      if (effectivePreviewMode) {
         // Editor visibility is now controlled by inline styles in JSX
         return;
      }

      // Prevent multiple simultaneous initializations
      if (initializationInProgress.current) {
         logger.debug("⏳ Initialization already in progress, skipping...");
         return;
      }

      // Don't reinitialize if already initialized for the same document
      if (
         isInitialized.current &&
         editorRef.current &&
         lastDocumentId.current === document.modified
      ) {
         logger.debug(
            "✅ Editor already initialized for document (modified:",
            document.modified,
            ")"
         );
         return;
      }

      // Only reinitialize if document modified timestamp changed or editor is not initialized
      const shouldInitialize =
         !isInitialized.current ||
         !editorRef.current ||
         lastDocumentId.current !== document.modified;

      if (!shouldInitialize) {
         logger.debug("🚫 Should not initialize, conditions not met");
         return;
      }

      logger.debug(
         "🔧 Initializing EditorJS for document (modified:",
         document.modified,
         "Instance:",
         editorInstanceId.current
      );
      initializationInProgress.current = true;

      // Add a small delay to prevent React Strict Mode double initialization
      const initTimeout = setTimeout(() => {
         // Double-check that we should still initialize (prevents race conditions)
         if (!initializationInProgress.current) {
            logger.debug("🚫 Initialization cancelled during delay");
            return;
         }

         // Clean up any existing editor before creating a new one
         if (editorRef.current) {
            cleanupEditor(editorRef);
         }

         // Clear the container to ensure clean state
         if (containerRef.current) {
            containerRef.current.innerHTML = "";

            // Add unique class to identify this specific editor instance
            containerRef.current.classList.add(
               `editor-instance-${editorInstanceId.current}`
            );
         }

         // Update theme classes
         if (isDarkMode) {
            containerRef.current?.classList.add("dark");
         } else {
            containerRef.current?.classList.remove("dark");
         }

         // Get current editor data at initialization time
         const currentEditorData = convertToEditorJSFormat(document);

         // Suppress initial change events during render/rehydration.
         suppressEditorOnChangeRef.current = true;

         const editor = new EditorJS({
            holder: containerRef.current!,
            readOnly: readonly,
            onReady: () => {
               logger.debug(
                  "✅ EditorJS is ready for document (modified:",
                  document.modified,
                  "Instance:",
                  editorInstanceId.current,
                  ")"
               );
               initializationInProgress.current = false;
               isInitialized.current = true;
               lastDocumentId.current = document.modified;
               setIsEditorLoading(false);

               // Initialize the structural hash to prevent immediate re-render
               const initialStructuralString = JSON.stringify({
                  blockCount: currentEditorData.blocks.length,
                  blockStructure: currentEditorData.blocks.map((block) => ({
                     id: block.id,
                     type: block.type
                  }))
               });
               lastRenderedContent.current = hashString(
                  initialStructuralString
               );
               logger.debug(
                  "📋 Initial structural hash set:",
                  lastRenderedContent.current
               );

               // Establish baseline hash from the loaded document (and later normalize from editor save).
               baselineContentHashRef.current =
                  computeStableHashFromDocument(document);

               // Allow onChange after the editor has finished mounting.
               // Use a macrotask to avoid the "first" onChange some tools emit after ready.
               setTimeout(() => {
                  suppressEditorOnChangeRef.current = false;

                  // Some tools normalize block data on first interaction.
                  // Capture the editor's serialized baseline once after mount.
                  void computeStableHashFromEditor(editor)
                     .then((hash) => {
                        if (!hash) return;
                        baselineContentHashRef.current = hash;
                     })
                     .catch((error) => {
                        console.warn("baseline.setFromEditor failed", error);
                     });
               }, 0);
            },
            onChange: () => {
               // Keep local UI state and global store state in sync.
               // This ensures route blocking reflects actual editor changes.
               if (readonly) return;
               if (suppressEditorOnChangeRef.current) {
                  return;
               }

               // Debounce and only mark dirty if the serialized content differs
               // from the baseline hash.
               //
               // Performance: avoid calling editor.save() repeatedly once the
               // doc is already dirty.
               const debounceMs = isDirtyRef.current ? 400 : 100;

               if (pendingDirtyCheckTimeoutRef.current) {
                  window.clearTimeout(pendingDirtyCheckTimeoutRef.current);
               }

               pendingDirtyCheckTimeoutRef.current = window.setTimeout(() => {
                  void computeStableHashFromEditor()
                     .then((currentHash) => {
                        if (!currentHash) return;
                        const baselineHash = baselineContentHashRef.current;

                        if (baselineHash && currentHash === baselineHash) {
                           // No real content change; keep/restore clean state.
                           if (isDirtyRef.current) {
                              setDirty(false);
                              useNotebookStore
                                 .getState()
                                 .setDirty(false, instanceId || "default");
                           }
                           return;
                        }

                        if (!isDirtyRef.current) {
                           setDirty(true);
                           useNotebookStore
                              .getState()
                              .setDirty(true, instanceId || "default");
                        }
                     })
                     .catch((error) => {
                        console.warn(
                           "computeStableHashFromEditor failed",
                           error
                        );
                     });
               }, debounceMs);
            },
            defaultBlock: "paragraph",
            minHeight: 300,
            sanitizer: {
               b: true,
               i: true,
               u: true,
               s: true,
               mark: true,
               small: true,
               sup: true,
               sub: true,
               a: {
                  href: true,
                  target: "_blank",
                  rel: "noopener noreferrer"
               },
               code: {
                  class: true
               }
            },
            tools: editorTools,
            data: currentEditorData,
            placeholder: "Start writing or press '/' for commands..."
         });

         editorRef.current = editor;
      }, 10); // Small delay to prevent React Strict Mode double initialization

      return () => {
         clearTimeout(initTimeout);
         // Only cleanup when component unmounts or document ID changes
         // Don't cleanup on preview mode changes to preserve React components
         if (lastDocumentId.current !== document.modified) {
            initializationInProgress.current = false;
            isInitialized.current = false;
            lastDocumentId.current = null;
            cleanupEditor(editorRef);
         }
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
   }, [
      document?.modified, // Only re-initialize when document modified timestamp changes
      readonly
      // Removed effectivePreviewMode from dependencies to prevent cleanup on mode switch
   ]);

   // Separate cleanup effect for component unmount
   useEffect(() => {
      return () => {
         // Always cleanup when component unmounts
         cleanupEditor(editorRef);
         initializationInProgress.current = false;
         isInitialized.current = false;
         lastDocumentId.current = null;
      };
   }, []);

   // Separate effect to update editor data when document structure changes (not data within blocks)
   useEffect(() => {
      // Only update editor data for structural changes:
      // 1. Document import/load (document ID change)
      // 2. Block addition/removal (blocks array length change)
      // 3. Initial document rendering
      //
      // Do NOT re-render for data changes within existing blocks -
      // blocks manage their own state and will call save() when EditorJS needs current data
      if (
         editorRef.current &&
         isInitialized.current &&
         !initializationInProgress.current &&
         document &&
         lastDocumentId.current === document.modified &&
         !effectivePreviewMode &&
         !isEditorLoading
      ) {
         const currentEditorData = convertToEditorJSFormat(document);

         // Create a structural hash that only includes block types and IDs, not internal data
         const structuralDataString = JSON.stringify({
            blockCount: currentEditorData.blocks.length,
            blockStructure: currentEditorData.blocks.map((block) => ({
               id: block.id,
               type: block.type
            }))
         });

         const currentStructuralHash = hashString(structuralDataString);

         // Only re-render if document structure actually changed
         if (lastRenderedContent.current === currentStructuralHash) {
            logger.debug(
               "📋 Skipping editor re-render: document structure unchanged"
            );
            return; // Skip re-rendering if structure is identical
         }

         // Also skip if this is the very first render and we haven't set a baseline hash yet
         if (lastRenderedContent.current === null) {
            logger.debug(
               "📋 Skipping first render - setting baseline structural hash"
            );
            lastRenderedContent.current = currentStructuralHash;
            return;
         }

         // FIX: If we have pending actions, we should NOT call editor.render()
         // because applyIncremental will handle the updates without re-mounting everything.
         // We only update lastRenderedContent.current to match the new structure
         // so we don't trigger this later.
         if (pendingActions.length > 0 || processingActionsRef.current) {
            logger.debug(
               "📋 Skipping editor structural re-render: incremental actions are pending or applying"
            );
            // Still update the hash so we don't trigger it later for the SAME change
            lastRenderedContent.current = currentStructuralHash;
            return;
         }

         logger.debug("🔄 Document structure changed, re-rendering blocks...", {
            previousHash: lastRenderedContent.current,
            currentHash: currentStructuralHash,
            blockTypes: currentEditorData.blocks.map((b) => b.type),
            blocksCount: currentEditorData.blocks.length
         });

         // Debounce the update to prevent flashing
         const timeoutId = setTimeout(() => {
            // Double-check that we still should re-render
            if (lastRenderedContent.current === currentStructuralHash) {
               logger.debug(
                  "📋 Render cancelled - structure already up to date"
               );
               return;
            }

            if (
               editorRef.current &&
               typeof editorRef.current.render === "function" &&
               !initializationInProgress.current
            ) {
               // EditorJS render() replaces the DOM wholesale, which resets the
               // scroll container to the top. Snapshot the position and restore
               // it after the render so server-side reconciliation never yanks
               // the reader back up; when a block focus is queued, let the
               // focus effect win instead (it scrolls to the changed block).
               const scrollContainer = findScrollContainer(
                  containerRef.current
               );
               const previousScrollTop = scrollContainer?.scrollTop ?? null;
               const pendingFocusBlockId = instanceId
                  ? useNotebookStore.getState().getInstanceState(instanceId)
                       ?.focusedBlockId
                  : null;

               logger.debug("🔄 Actually rendering document structure changes");
               editorRef.current
                  .render(currentEditorData)
                  .then(() => {
                     // Update the hash after successful render using the structural hash
                     lastRenderedContent.current = currentStructuralHash;

                     if (
                        scrollContainer &&
                        previousScrollTop !== null &&
                        !pendingFocusBlockId
                     ) {
                        scrollContainer.scrollTop = previousScrollTop;
                     }
                  })
                  .catch((error) => {
                     console.warn("Error updating editor data:", error);
                  });
            }
         }, 50);

         return () => clearTimeout(timeoutId);
      }
   }, [
      document,
      effectivePreviewMode,
      isEditorLoading,
      instanceId,
      pendingActions.length
   ]);

   // Separate effect to handle theme changes without reinitializing the editor
   useEffect(() => {
      if (!containerRef.current) return;

      if (isDarkMode) {
         containerRef.current.classList.add("dark");
      } else {
         containerRef.current.classList.remove("dark");
      }
   }, [isDarkMode]);

   // Handle block focusing (scroll to view)
   useEffect(() => {
      if (!focusedBlockId || !containerRef.current || isEditorLoading) return;
      const instanceKey = instanceId || "default";
      const targetBlockId = focusedBlockId;
      let attempts = 0;
      let timerId: number | undefined;

      const attemptScroll = () => {
         // EditorJS uses data-id on the .ce-block elements; the block may not
         // exist yet when focus arrives (a remote upsert can still be inside
         // the async render/insert), so retry briefly before giving up.
         const element = containerRef.current?.querySelector(
            `[data-id="${targetBlockId}"]`
         );
         if (element) {
            element.scrollIntoView({
               behavior: "smooth",
               block: "center"
            });
            // Clear focus in the store so it can be re-triggered for the same block
            clearFocus(instanceKey);
            return;
         }
         attempts += 1;
         if (attempts >= 8) {
            // Block never appeared (e.g. it was deleted): release the focus
            // so a later action can re-trigger scrolling.
            clearFocus(instanceKey);
            return;
         }
         timerId = window.setTimeout(attemptScroll, 150);
      };
      attemptScroll();

      return () => window.clearTimeout(timerId);
   }, [focusedBlockId, isEditorLoading, clearFocus, instanceId]);

   // Sync incoming actions from store to EditorJS instance imperatively to avoid full re-renders/refresh
   useEffect(() => {
      const editor = editorRef.current;
      if (!editor || isEditorLoading) return;
      if (pendingActions.length === 0 || processingActionsRef.current) return;

      const applyIncremental = async () => {
         // Lock processing to prevent race conditions during async operations
         processingActionsRef.current = true;

         try {
            // Wait for editor to be ready
            await editor.isReady;

            // Take a snapshot of actions to process
            const actionsToProcess = [...pendingActions];
            logger.debug(
               `[NotebookEditor] Applying ${actionsToProcess.length} incremental actions to EditorJS`
            );

            // Suppress our own onchange to avoid feedback loops
            suppressEditorOnChangeRef.current = true;

            const getBlockIndexSafe = (cid: string): number => {
               try {
                  // Check existence first to avoid console console errors from getBlockIndex
                  const block = editor.blocks.getById(cid);
                  if (!block) return -1;
                  return editor.blocks.getBlockIndex(cid);
               } catch {
                  return -1;
               }
            };

            for (const action of actionsToProcess) {
               try {
                  switch (action.actionType) {
                     case "upsertBlock": {
                        const { cid, blockType, data, position } =
                           action.payload;

                        // Check if block exists
                        const blockIndex = getBlockIndexSafe(cid);

                        if (blockIndex !== -1) {
                           // 1. Check if type changed
                           const blockCount = editor.blocks.getBlocksCount();
                           const existingBlock =
                              blockIndex >= 0 && blockIndex < blockCount
                                 ? editor.blocks.getBlockByIndex(blockIndex)
                                 : null;

                           const currentType = (existingBlock as BlockAPI)
                              ?.name;

                           if (
                              existingBlock &&
                              currentType &&
                              currentType !== blockType
                           ) {
                              logger.debug(
                                 `[NotebookEditor] Block type changed from ${currentType} to ${blockType}, replacing...`
                              );
                              editor.blocks.delete(blockIndex);
                              await editor.blocks.insert(
                                 blockType,
                                 data,
                                 {},
                                 position ?? blockIndex,
                                 true,
                                 false,
                                 cid
                              );
                           } else {
                              // 2. Update data
                              try {
                                 // Check if block exists before update to prevent errors
                                 const currentIdx = getBlockIndexSafe(cid);
                                 if (currentIdx !== -1) {
                                    await editor.blocks.update(cid, data);
                                 }
                              } catch (updateErr) {
                                 // Ignore update errors as they can occur during rapid changes
                                 logger.debug(
                                    `[NotebookEditor] Checked failed update for block ${cid}:`,
                                    updateErr
                                 );
                              }

                              // 3. Update position if needed
                              if (position !== undefined && position !== null) {
                                 const currentIdx = getBlockIndexSafe(cid);
                                 if (
                                    currentIdx !== -1 &&
                                    currentIdx !== position
                                 ) {
                                    const blockCount =
                                       editor.blocks.getBlocksCount();
                                    const maxIndex = Math.max(
                                       0,
                                       blockCount - 1
                                    );
                                    const nextIdx = Math.max(
                                       0,
                                       Math.min(position, maxIndex)
                                    );

                                    // Validate indices before calling move (EditorJS throws if out of bounds)
                                    if (
                                       currentIdx >= 0 &&
                                       currentIdx < blockCount &&
                                       nextIdx >= 0 &&
                                       nextIdx < blockCount
                                    ) {
                                       try {
                                          // EditorJS: move(toIndex, fromIndex)
                                          editor.blocks.move(
                                             nextIdx,
                                             currentIdx
                                          );
                                       } catch (moveErr) {
                                          console.warn(
                                             `[NotebookEditor] Move failed:`,
                                             moveErr
                                          );
                                       }
                                    }
                                 }
                              }
                           }
                        } else {
                           // New block
                           try {
                              await editor.blocks.insert(
                                 blockType,
                                 data,
                                 {},
                                 position ?? editor.blocks.getBlocksCount(),
                                 true,
                                 false,
                                 cid
                              );
                           } catch (insertError) {
                              console.error(
                                 `[NotebookEditor] Failed to insert block ${cid} (type: ${blockType}):`,
                                 insertError
                              );
                           }
                        }
                        break;
                     }
                     case "patchBlockContent": {
                        const { cid, field, value } = action.payload;
                        if (!field) break;

                        const blockIndex = getBlockIndexSafe(cid);

                        const existingBlock =
                           blockIndex !== -1
                              ? editor.blocks.getBlockByIndex(blockIndex)
                              : null;

                        if (existingBlock) {
                           try {
                              const currentData = await existingBlock.save();
                              if (currentData?.data) {
                                 const idx = getBlockIndexSafe(cid);
                                 if (idx !== -1) {
                                    editor.blocks.update(cid, {
                                       ...currentData.data,
                                       [field]: value
                                    });
                                 }
                              }
                           } catch (err) {
                              console.error(
                                 `[NotebookEditor] Failed to patch block ${cid}:`,
                                 err
                              );
                           }
                        } else {
                           console.warn(
                              `[NotebookEditor] Cannot patch block ${cid}: not found`
                           );
                        }
                        break;
                     }
                     case "removeBlock": {
                        const { cid } = action.payload;
                        const blockIndex = getBlockIndexSafe(cid);

                        if (blockIndex !== -1) {
                           editor.blocks.delete(blockIndex);
                        } else {
                           console.warn(
                              `[NotebookEditor] Cannot remove block ${cid}: not found`
                           );
                        }
                        break;
                     }
                     case "setBlockOutput": {
                        // setBlockOutput is mostly for state, but some blocks (like SQL)
                        // might need to refresh their UI if the output is passed in config.
                        // For now, we update data to trigger block-internal re-renders.
                        const { cid, outputs } = action.payload;

                        const blockIndex = getBlockIndexSafe(cid);

                        const existingBlock =
                           blockIndex !== -1
                              ? editor.blocks.getBlockByIndex(blockIndex)
                              : null;

                        if (existingBlock) {
                           try {
                              const currentData = await existingBlock.save();
                              if (currentData?.data) {
                                 const idx = getBlockIndexSafe(cid);
                                 if (idx !== -1) {
                                    editor.blocks.update(cid, {
                                       ...currentData.data,
                                       outputs
                                    });
                                 }
                              }
                           } catch (err) {
                              console.error(
                                 `[NotebookEditor] Failed to set block output for ${cid}:`,
                                 err
                              );
                           }
                        }
                        break;
                     }
                  }
               } catch (err) {
                  console.error(
                     "[NotebookEditor] Failed to apply incremental action:",
                     action,
                     err
                  );
                  // Force a full re-render on next structural change as recovery
                  lastRenderedContent.current = null;
               }
            }

            // Successfully processed these actions, remove them from store
            clearPendingActions(actionsToProcess, instanceId || "default");
         } finally {
            processingActionsRef.current = false;
            // Resume onchange after a small delay
            setTimeout(() => {
               suppressEditorOnChangeRef.current = false;
            }, 500);
         }
      };

      void applyIncremental();
   }, [
      pendingActions,
      lastAppliedSequence,
      isEditorLoading,
      clearPendingActions,
      instanceId
   ]);

   const handleSave = async () => {
      if (!onSave) return;
      await persistCurrentNotebook();
   };

   const handleExport = async () => {
      if (document) {
         try {
            const updatedDocument = await createUpdatedDocument(
               document,
               editorRef,
               defaultTitle,
               isEditorLoading,
               instanceId
            );

            if (onExport) {
               onExport(updatedDocument);
            } else {
               // Default export behavior - download as JSON (document is now serializable by default)
               const blob = new Blob(
                  [JSON.stringify(updatedDocument, null, 2)],
                  { type: "application/json" }
               );
               const url = URL.createObjectURL(blob);
               const a = window.document.createElement("a");
               a.href = url;
               a.download = `${
                  updatedDocument.title || "notebook"
               }${NOTEBOOK_FILE_EXTENSION}`;
               a.click();
               URL.revokeObjectURL(url);
            }
            message.success("Notebook exported successfully");
         } catch (error) {
            console.error("Error exporting notebook:", error);
            message.error("Failed to export notebook");
         }
      }
   };

   const handleNotebookImport = () => {
      const input = window.document.createElement("input");
      input.type = "file";
      input.accept = NOTEBOOK_FILE_EXTENSION;
      input.onchange = async (event: Event) => {
         const file = (event.target as HTMLInputElement).files?.[0];
         if (file) {
            try {
               const jsonContent = await file.text();
               const importedDocument = JSON.parse(jsonContent);

               // Basic validation to ensure it's a valid notebook document
               if (
                  !importedDocument.blocks ||
                  !Array.isArray(importedDocument.blocks)
               ) {
                  throw new Error(
                     "Invalid notebook format: missing or invalid blocks array"
                  );
               }

               // Ask user for confirmation before overwriting
               const confirmed = await new Promise<boolean>((resolve) => {
                  modal.confirm({
                     title: "Import Notebook",
                     content: `Are you sure you want to import "${file.name}"? This will replace the current document content.`,
                     okText: "Import",
                     cancelText: "Cancel",
                     okType: "primary",
                     onOk: () => resolve(true),
                     onCancel: () => resolve(false)
                  });
               });

               if (!confirmed) {
                  return;
               }

               // Ensure required properties exist and set defaults if needed
               const notebookDocument: NotebookDocument = {
                  title:
                     importedDocument.title ||
                     file.name.replace(
                        new RegExp(`\\${NOTEBOOK_FILE_EXTENSION}$`),
                        ""
                     ),
                  blocks: importedDocument.blocks,
                  metadata: importedDocument.metadata || {},
                  created: importedDocument.created || Date.now(),
                  modified: Date.now() // Always update modified time on import
               };

               // Update the document in store
               const store = useNotebookStore.getState();
               store.setDocument(notebookDocument, instanceId || "default");

               // Reload the editor with new data if editor is initialized
               if (editorRef.current) {
                  const editorData = convertToEditorJSFormat(notebookDocument);
                  await editorRef.current.render(editorData);
               }

               message.success("Notebook imported successfully");
            } catch (error) {
               console.error("❌ Error importing notebook:", error);
               if (error instanceof SyntaxError) {
                  message.error(
                     "Failed to import notebook: Invalid JSON format"
                  );
               } else {
                  message.error(
                     `Failed to import notebook: ${
                        error instanceof Error ? error.message : "Unknown error"
                     }`
                  );
               }
            }
         }
      };
      logger.debug("🖱️ Triggering notebook file input click...");
      input.click();
   };

   const handlePreviewToggle = useCallback(async () => {
      const newPreviewMode = !effectivePreviewMode;

      // If switching to preview mode, sync the current editor state first
      // But only if there are actual unsaved changes
      if (
         newPreviewMode &&
         !readonly &&
         document &&
         !isEditorLoading &&
         editorRef.current &&
         isDirty // Only save if there are actual changes
      ) {
         try {
            const updatedDocument = await createUpdatedDocument(
               document,
               editorRef,
               defaultTitle,
               isEditorLoading,
               instanceId
            );

            // Use the same stable hash comparison as the content change detection
            // Only update document if content actually changed (not just timestamps)
            if (
               computeStableHashFromDocument(updatedDocument) !==
               computeStableHashFromDocument(document)
            ) {
               logger.debug("💾 Saving editor changes before preview mode");
               const store = useNotebookStore.getState();
               store.setDocument(updatedDocument, instanceId || "default");
            } else {
               logger.debug(
                  "📋 No content changes to save before preview mode"
               );
            }
         } catch (error) {
            console.error("Failed to sync editor state before preview:", error);
            // Don't prevent preview mode switch even if save fails
         }
      }

      // Switch mode immediately - no delay needed since we're not destroying the editor
      setInternalPreviewMode(newPreviewMode);
   }, [
      effectivePreviewMode,
      readonly,
      document,
      isEditorLoading,
      defaultTitle,
      isDirty,
      instanceId,
      computeStableHashFromDocument
   ]);

   if (!document) {
      return <div>Loading...</div>;
   }

   const notebookLayout = (
      <Layout
         style={{
            height: maxHeight,
            maxHeight: maxHeight,
            width: "100%",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column",
            flex: maxHeight === "100%" ? 1 : undefined,
            minHeight: 0
         }}
         className={`kontext-notebook-editor ${isDarkMode ? "dark" : ""}`}
      >
         {showHeader && (
            <Flex
               style={{
                  background: token.colorBgContainer,
                  minHeight: "var(--app-chrome-row-height, 56px)",
                  padding: "0 var(--app-page-content-padding, 24px)",
                  borderBottom: `1px solid ${token.colorBorder}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  position: "sticky",
                  top: 0,
                  zIndex: 100,
                  gap: token.paddingSM
               }}
            >
               <div style={{ display: "flex", alignItems: "center", flex: 1 }}>
                  {readonly || effectivePreviewMode ? (
                     <div
                        style={{
                           fontSize: "16px",
                           fontWeight: 600,
                           padding: "4px 8px",
                           marginRight: "16px",
                           flex: 1,
                           minWidth: 0,
                           color: token.colorText,
                           overflow: "hidden",
                           textOverflow: "ellipsis",
                           whiteSpace: "nowrap"
                        }}
                     >
                        {document?.title || defaultTitle}
                     </div>
                  ) : (
                     <Input
                        value={document?.title || ""}
                        onChange={handleTitleChange}
                        onBlur={handleTitleBlur}
                        onPressEnter={(e) =>
                           (e.target as HTMLInputElement).blur()
                        }
                        placeholder={defaultTitle}
                        disabled={readonly}
                        onMouseEnter={() => setIsTitleHovered(true)}
                        onMouseLeave={() => setIsTitleHovered(false)}
                        style={{
                           fontSize: "16px",
                           fontWeight: 600,
                           border: "none",
                           boxShadow: "none",
                           padding: "4px 8px",
                           marginRight: "16px",
                           borderRadius: token.borderRadius,
                           flex: 1,
                           minWidth: 0,
                           color: token.colorText,
                           transition: "background-color 0.2s ease-in-out",
                           backgroundColor:
                              isTitleHovered && !readonly
                                 ? token.colorBgTextHover
                                 : "transparent",
                           overflow: "hidden",
                           textOverflow: "ellipsis",
                           whiteSpace: "nowrap"
                        }}
                     />
                  )}
               </div>
               <Space size="middle">
                  {showSaveButton && (
                     <Button
                        icon={saveButtonIcon}
                        type="primary"
                        onClick={handleSave}
                        disabled={isEditorLoading || !isDirty}
                     >
                        {saveButtonText}
                     </Button>
                  )}

                  <Space size={4}>
                     {showEditToggleButton && (
                        <Tooltip
                           title={
                              effectivePreviewMode
                                 ? "Switch to Edit Mode"
                                 : "Switch to Preview Mode"
                           }
                        >
                           <Button
                              icon={
                                 effectivePreviewMode ? (
                                    <EditOutlined />
                                 ) : (
                                    <EyeOutlined />
                                 )
                              }
                              type="text"
                              onClick={handlePreviewToggle}
                              disabled={isEditButtonDisabled}
                              style={{ border: "none" }}
                           />
                        </Tooltip>
                     )}
                     {!effectivePreviewMode && sidebarMode === "sidebar" && (
                        <Tooltip
                           title={
                              rightPanelOpen ? "Close Sidebar" : "Open Sidebar"
                           }
                        >
                           <Button
                              type="text"
                              icon={
                                 rightPanelOpen ? (
                                    <PanelRightCloseOutlined />
                                 ) : (
                                    <PanelRightOpenOutlined />
                                 )
                              }
                              onClick={() => setRightPanelOpen(!rightPanelOpen)}
                              style={{ border: "none" }}
                           />
                        </Tooltip>
                     )}
                     {!effectivePreviewMode && sidebarMode === "popup" && (
                        <Tooltip title="Notebook Settings">
                           <Button
                              type="text"
                              icon={<SettingOutlined />}
                              onClick={() => setShowMetadataModal(true)}
                              style={{ border: "none" }}
                           />
                        </Tooltip>
                     )}
                     {!effectivePreviewMode && (
                        <Dropdown
                           menu={{
                              items: [
                                 {
                                    key: "import-notebook",
                                    label: "Import Notebook",
                                    icon: <ImportOutlined />,
                                    onClick: handleNotebookImport,
                                    disabled: isEditorLoading || readonly
                                 },
                                 {
                                    key: "toggle-sidebar-mode",
                                    label: (
                                       <Checkbox
                                          checked={sidebarMode === "sidebar"}
                                          onChange={(e) =>
                                             setSidebarMode(
                                                e.target.checked
                                                   ? "sidebar"
                                                   : "popup",
                                                instanceId || "default"
                                             )
                                          }
                                       >
                                          Dock Sidebar
                                       </Checkbox>
                                    )
                                 },
                                 {
                                    type: "divider"
                                 },
                                 {
                                    key: "export-notebook",
                                    label: "Export Notebook",
                                    icon: <ExportOutlined />,
                                    onClick: handleExport,
                                    disabled: isEditorLoading || readonly
                                 }
                              ]
                           }}
                           trigger={["click"]}
                           placement="bottomRight"
                        >
                           <Button
                              type="text"
                              icon={<MoreOutlined />}
                              disabled={isEditorLoading}
                              style={{ border: "none" }}
                           />
                        </Dropdown>
                     )}
                  </Space>
               </Space>
            </Flex>
         )}

         <Layout
            style={{
               flex: 1,
               overflow: "hidden",
               display: "flex",
               flexDirection: "row",
               minHeight: 0
            }}
         >
            <Content
               style={{
                  padding: effectivePreviewMode ? "0" : "16px 0 0 0",
                  margin: 0,
                  overflowY: "auto",
                  flex: 1,
                  minHeight: 0,
                  position: "relative",
                  background: token.colorBgContainer
               }}
            >
               {/* Always render both preview and editor, but control visibility */}
               {effectivePreviewMode && (
                  <NotebookPreview
                     document={document}
                     instanceId={instanceId}
                     className={`kontext-notebook-editor ${
                        isDarkMode ? "dark" : ""
                     }`}
                  />
               )}
               {/* Editor container - always present but visibility controlled by useEffect */}
               <div
                  id="editorjs-container"
                  ref={containerRef}
                  style={{
                     display: effectivePreviewMode ? "none" : "block"
                  }}
               />
            </Content>
            {effectiveRightPanelOpen && (
               <Sider
                  width="25%"
                  style={{
                     backgroundColor: token.colorBgLayout,
                     borderLeft: `1px solid ${token.colorBorder}`,
                     padding: "24px",
                     overflowY: "hidden",
                     height: "100%",
                     display: "flex",
                     flexDirection: "column",
                     minHeight: 0
                  }}
               >
                  <div
                     style={{
                        flex: 1,
                        minHeight: 0,
                        display: "flex",
                        flexDirection: "column"
                     }}
                  >
                     <NotebookSidebar
                        cultures={cultures}
                        metadata={document?.metadata || {}}
                        onMetadataChange={
                           effectivePreviewMode
                              ? undefined
                              : handleMetadataChange
                        }
                        showArticleFields={showArticleMetadata}
                        showSaveAsDraft={showSaveAsDraft}
                        sidebarExtensions={sidebarExtensions}
                     />
                  </div>
               </Sider>
            )}
         </Layout>
      </Layout>
   );

   // Return notebook layout with optional metadata modal
   return (
      <>
         {notebookLayout}
         {/* Metadata Drawer for popup mode */}
         {sidebarMode === "popup" && (
            <Drawer
               title="Properties & Settings"
               open={showMetadataModal}
               onClose={() => setShowMetadataModal(false)}
               size={600}
               styles={{ body: { padding: 16, overflow: "hidden" } }}
               destroyOnHidden
               placement="right"
            >
               <NotebookSidebar
                  cultures={cultures}
                  metadata={document?.metadata || {}}
                  onMetadataChange={
                     effectivePreviewMode ? undefined : handleMetadataChange
                  }
                  showArticleFields={showArticleMetadata}
                  showSaveAsDraft={showSaveAsDraft}
                  sidebarExtensions={sidebarExtensions}
               />
            </Drawer>
         )}
      </>
   );
};

export default NotebookEditor;
