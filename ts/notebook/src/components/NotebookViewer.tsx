import { DatabaseZapOutlined } from "@kontext-labs/icons";
import { useFileOperations } from "@kontext-labs/file";
import type {
   Artifact,
   ArtifactAction,
   CultureInfoModel,
   FileModel
} from "@kontext-labs/schema";
import { LoadingSpinner, useUiApp } from "@kontext-labs/ui";
import { Alert } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CodeExecutionEngine, FileSystemBinding } from "../types/bindings";
import type { NotebookDocument } from "../types/notebook";
import { notebookInstanceId } from "../constants";
import { useNotebookFileHelpers } from "../hooks/useNotebookFileHelpers";
import NotebookEditor from "./NotebookEditor";
import NotebookSessionsSidebarTab from "./NotebookSessionsSidebarTab";
import { NotebookServiceProvider } from "../context/NotebookServiceContext";
import { useNotebookStore } from "../stores/notebookStore";

const hasSameContent = (a: NotebookDocument, b: NotebookDocument): boolean => {
   if (a.blocks.length !== b.blocks.length) return false;
   return a.blocks.every((block, index) => {
      const other = b.blocks[index];
      // Compare full block content, not just id/type: content patches keep
      // both stable, so an id/type-only check would treat a missed content
      // update as "already reconciled" and never recover it.
      return !!other && JSON.stringify(block) === JSON.stringify(other);
   });
};

/**
 * First block (by position) whose content differs between two documents, or
 * the newest appended block. Null when there is nothing to scroll to: no
 * change, an empty next document, or pure deletions. (An empty *previous*
 * document is itself informative — the agent added blocks to a freshly opened
 * notebook — and resolves to the newest appended block.)
 */
export const findFirstChangedBlockId = (
   previous: NotebookDocument["blocks"],
   next: NotebookDocument["blocks"]
): string | null => {
   const paired = Math.min(previous.length, next.length);
   for (let index = 0; index < paired; index++) {
      // Same comparison granularity as hasSameContent: full block content.
      if (JSON.stringify(previous[index]) !== JSON.stringify(next[index])) {
         return next[index].id;
      }
   }
   if (next.length > previous.length && next.length > 0) {
      return next[next.length - 1].id;
   }
   return null;
};

export interface NotebookViewerProps {
   artifact: Artifact;
   projectId: string;
   projectCode?: string;
   onViewExecutionRun?: (runId: string) => void;
   fileSystem: FileSystemBinding;
   executionEngine: CodeExecutionEngine;
   readonly?: boolean;
   onTitleChange?: (title: string) => void;
   cultures?: CultureInfoModel[];
   streamingActions?: ArtifactAction[];
   /**
    * Monotonic token that advances whenever the underlying artifact changes
    * server-side. The viewer reconciles the persisted document when it moves,
    * which recovers any live actions that could not be replayed (or arrived
    * before the viewer mounted).
    */
   refreshToken?: number;
}

const NotebookViewerContent = ({
   artifact,
   readonly = true,
   onTitleChange,
   projectId,
   projectCode,
   onViewExecutionRun,
   fileSystem,
   executionEngine,
   cultures = [],
   streamingActions = [],
   refreshToken
}: NotebookViewerProps) => {
   const { message } = useUiApp();
   const { fetchFile, getFileBlob, updateFile } = useFileOperations({
      projectId
   });
   const { loadNotebook, saveNotebook } = useNotebookFileHelpers({
      fetchFile,
      getFileBlob,
      updateFile
   });

   const [notebook, setNotebook] = useState<NotebookDocument | null>(null);
   const [resource, setResource] = useState<FileModel | null>(null);
   const [isLoading, setIsLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);

   const instanceId = notebookInstanceId(artifact.artifactId);

   const createInstance = useNotebookStore((state) => state.createInstance);
   const removeInstance = useNotebookStore((state) => state.removeInstance);
   const isInstanceInitialized = useNotebookStore(
      (state) => !!state.getInstanceState(instanceId)
   );
   const storeTitle = useNotebookStore(
      (state) => state.getInstanceState(instanceId)?.document?.title
   );

   const sidebarExtensions = useMemo(() => {
      return [
         {
            key: "sessions",
            label: "Sessions",
            icon: <DatabaseZapOutlined />,
            children: (
               <NotebookSessionsSidebarTab
                  projectId={projectId}
                  readonly={readonly}
               />
            )
         }
      ];
   }, [projectId, readonly]);

   const lastLoadedArtifactIdRef = useRef<string | null>(null);

   useEffect(() => {
      let mounted = true;

      const doLoad = async () => {
         if (!artifact.artifactId) {
            if (!mounted) return;
            setError("Missing artifact or project information");
            setIsLoading(false);
            return;
         }

         if (
            lastLoadedArtifactIdRef.current === artifact.artifactId &&
            notebook
         ) {
            return;
         }

         try {
            if (!mounted) return;

            setIsLoading(true);
            setError(null);

            const {
               notebook: loadedNotebook,
               file,
               error: loadError
            } = await loadNotebook(artifact.artifactId, {
               createEmptyOnParseError: false
            });

            if (!mounted) return;

            if (file) {
               setResource(file);
            }

            if (loadedNotebook) {
               setNotebook(loadedNotebook);
               lastLoadedArtifactIdRef.current = artifact.artifactId;
            }

            if (loadError) {
               setError(loadError);
            }
         } catch (parseError) {
            console.error("Error loading notebook:", parseError);
            if (mounted) {
               setError("Failed to load notebook content");
            }
         } finally {
            if (mounted) {
               setIsLoading(false);
            }
         }
      };

      void doLoad();

      return () => {
         mounted = false;
      };
   }, [artifact.artifactId, loadNotebook, notebook]);

   const onTitleChangeRef = useRef<typeof onTitleChange>(onTitleChange);

   useEffect(() => {
      onTitleChangeRef.current = onTitleChange;
   }, [onTitleChange]);

   useEffect(() => {
      if (onTitleChangeRef.current && storeTitle) {
         onTitleChangeRef.current(storeTitle);
      }
   }, [storeTitle]);

   useEffect(() => {
      if (!notebook || !instanceId) return;

      const existing = useNotebookStore.getState().getInstanceState(instanceId);
      if (!existing) {
         createInstance(instanceId, {
            document: notebook,
            isDarkMode: false,
            readonly,
            sidebarMode: "popup"
         });
         return;
      }

      const currentDoc = existing.document;
      const isServerUpdate =
         !currentDoc ||
         (notebook.modified && notebook.modified > (currentDoc.modified || 0));

      if (isServerUpdate) {
         useNotebookStore.getState().setDocument(notebook, instanceId);
      }

      if (existing.readonly !== readonly) {
         useNotebookStore.getState().setReadonly(readonly, instanceId);
      }
   }, [createInstance, instanceId, notebook, readonly]);

   useEffect(() => {
      if (!instanceId) return;

      return () => removeInstance(instanceId);
   }, [instanceId, removeInstance]);

   const actionsLength = streamingActions.length;
   const lastSequence =
      streamingActions.length > 0
         ? streamingActions[streamingActions.length - 1]?.sequence
         : undefined;
   const notebookModified = notebook?.modified;
   const hasNotebook = !!notebook;

   useEffect(() => {
      if (streamingActions.length > 0) {
         useNotebookStore.getState().applyActions(streamingActions, instanceId);
      }
   }, [
      actionsLength,
      hasNotebook,
      instanceId,
      lastSequence,
      notebookModified,
      streamingActions
   ]);

   const lastReconciledTokenRef = useRef<number | undefined>(undefined);
   const reconcileInFlightRef = useRef(false);
   const pendingRefreshTokenRef = useRef<number | undefined>(undefined);
   const mountedRef = useRef(true);

   useEffect(() => {
      mountedRef.current = true;
      return () => {
         mountedRef.current = false;
      };
   }, []);

   // Keep the reload callable out of the effect deps so unrelated renders (it
   // is re-created whenever the file-operations hooks re-render) do not reset
   // the debounce timer.
   const loadNotebookRef = useRef(loadNotebook);
   useEffect(() => {
      loadNotebookRef.current = loadNotebook;
   }, [loadNotebook]);

   const runReconcile = useCallback(
      async (token: number): Promise<void> => {
         lastReconciledTokenRef.current = token;
         if (reconcileInFlightRef.current) return;
         reconcileInFlightRef.current = true;
         try {
            // Never clobber in-flight user edits.
            const instance = useNotebookStore
               .getState()
               .getInstanceState(instanceId);
            if (instance?.isDirty) return;

            const { notebook: fresh } = await loadNotebookRef.current(
               artifact.artifactId,
               {
                  createEmptyOnParseError: false
               }
            );
            if (!fresh) return;

            // Bail if the viewer unmounted while the load was in flight;
            // otherwise we would re-create the instance we just removed.
            if (!mountedRef.current) return;

            // Live replay already produced the same content - nothing to do.
            const latestInstance = useNotebookStore
               .getState()
               .getInstanceState(instanceId);
            if (
               latestInstance?.document &&
               hasSameContent(latestInstance.document, fresh)
            ) {
               return;
            }

            setNotebook(fresh);
            lastLoadedArtifactIdRef.current = artifact.artifactId;

            // Ensure the store reflects the authoritative server document even if
            // the loaded `modified` timestamp ordering looks stale.
            if (
               !latestInstance?.document ||
               fresh.modified !== latestInstance.document.modified
            ) {
               useNotebookStore.getState().setDocument(fresh, instanceId);
            }

            // Scroll to the block the reconciliation changed so server-driven
            // updates (added/edited blocks, execution state) land in view.
            // Without a previous document there is nothing to compare — the
            // viewer just mounted and should start at the top.
            if (latestInstance?.document) {
               const changedBlockId = findFirstChangedBlockId(
                  latestInstance.document.blocks,
                  fresh.blocks
               );
               if (changedBlockId) {
                  useNotebookStore
                     .getState()
                     .focusBlock(changedBlockId, instanceId);
               }
            }
         } catch (reconcileError) {
            console.warn(
               "Failed to reconcile notebook with server artifact:",
               reconcileError
            );
         } finally {
            reconcileInFlightRef.current = false;
            const pendingToken = pendingRefreshTokenRef.current;
            if (
               pendingToken !== undefined &&
               pendingToken !== token &&
               useNotebookStore.getState().getInstanceState(instanceId)
            ) {
               pendingRefreshTokenRef.current = undefined;
               setTimeout(() => {
                  void runReconcile(pendingToken);
               }, 350);
            }
         }
      },
      [artifact.artifactId, instanceId]
   );

   useEffect(() => {
      if (refreshToken === undefined) return;
      if (lastReconciledTokenRef.current === refreshToken) return;
      if (reconcileInFlightRef.current) {
         // Remember the newest update and re-arm once the in-flight
         // reconcile settles, so the last update of a burst is never lost.
         pendingRefreshTokenRef.current = refreshToken;
         return;
      }

      // Debounce so a burst of artifact updates coalesces into a single
      // reconcile once the stream pauses, instead of reloading per event.
      const timeoutId = window.setTimeout(() => {
         void runReconcile(refreshToken);
      }, 350);

      return () => window.clearTimeout(timeoutId);
   }, [refreshToken, artifact.artifactId, instanceId, runReconcile]);

   const resourceId = resource?.id;
   const handleSave = useCallback(
      async (updatedDocument: NotebookDocument) => {
         if (readonly || !resourceId) {
            throw new Error("Notebook save is not available");
         }

         try {
            const updated = {
               ...updatedDocument,
               modified: Date.now()
            };

            const result = await saveNotebook(
               resourceId,
               updated,
               updated.title
            );

            if (result.success && result.file) {
               setResource(result.file);
               setNotebook(updated);
               message.success("Notebook saved successfully.");
               return;
            }

            throw new Error("Failed to save notebook");
         } catch (saveError) {
            console.error(
               "Error saving notebook in artifact viewer:",
               saveError
            );
            const error =
               saveError instanceof Error
                  ? saveError
                  : new Error("Failed to save notebook");
            message.error(error.message);
            throw error;
         }
      },
      [readonly, resourceId, saveNotebook, message]
   );

   if (isLoading) {
      return <LoadingSpinner />;
   }

   if (error || !notebook) {
      return (
         <Alert
            type="error"
            showIcon
            message="Failed to load notebook"
            description={error || undefined}
         />
      );
   }

   if (!isInstanceInitialized) {
      return <LoadingSpinner />;
   }

   return (
      <div
         style={{
            height: "100%",
            overflow: "hidden",
            display: "flex",
            flexDirection: "column"
         }}
      >
         <NotebookServiceProvider
            projectId={projectId}
            projectCode={projectCode}
            notebookId={artifact.artifactId}
            onViewExecutionRun={onViewExecutionRun}
            fileSystem={fileSystem}
            executionEngine={executionEngine}
         >
            <NotebookEditor
               instanceId={instanceId}
               readonly={readonly}
               previewMode={false}
               onSave={handleSave}
               enableSqlBlock={true}
               enableChartBlock={true}
               cultures={cultures}
               projectId={projectId}
               sidebarExtensions={sidebarExtensions}
               showHeader={true}
            />
         </NotebookServiceProvider>
      </div>
   );
};

const NotebookViewer = (props: NotebookViewerProps) => {
   return <NotebookViewerContent {...props} />;
};

export default NotebookViewer;
