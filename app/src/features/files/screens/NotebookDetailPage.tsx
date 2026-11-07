import PageContainer from "@/components/layout/SeoPageContainer";
import { usePermissionContext } from "@/context/AppPermissionContext";
import { useProjectTriggerActorRenderer } from "@/features/projects/hooks/useProjectTriggerActorRenderer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useNavigationBlock } from "@/hooks/useNavigationBlock";
import { useNotebookHostBindings } from "@/hooks/useNotebookHostBindings";
import { RouteNames } from "@/types";
import { AccessDeniedAlert } from "@kontext-tech/auth";
import { useFileWorkflow } from "@kontext-tech/file";
import { DatabaseZapOutlined } from "@kontext-tech/icons";
import { JobRunDetailsDrawerHost } from "@kontext-tech/job";
import { useUser } from "@kontext-tech/identity";
import {
   NotebookEditor,
   NotebookServiceProvider,
   NotebookSessionsSidebarTab,
   notebookInstanceId,
   useNotebookFileHelpers,
   useNotebookStore,
   type NotebookDocument,
   type SidebarTabExtension
} from "@kontext-tech/notebook";
import { useProject } from "@kontext-tech/project";
import type { FileModel } from "@kontext-tech/schema";
import { useSiteCultures } from "@kontext-tech/site";
import { LoadingSpinner, useUiApp, useUiFeedback } from "@kontext-tech/ui";
import { Flex } from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

type NotebookDetailPageProject = NonNullable<
   ReturnType<typeof useProject>["currentProject"]
>;

const NotebookDetailPageContent = ({
   fileId,
   currentProject
}: {
   fileId: string | undefined;
   currentProject: NotebookDetailPageProject;
}) => {
   const { isLoading: isUserLoading } = useUser();
   const { canContributeToProject } = usePermissionContext();
   const apiErrorHandler = useApiErrorHandler();
   const { cultures } = useSiteCultures({ errorHandler: apiErrorHandler });
   const { message } = useUiApp();

   const [resource, setResource] = useState<FileModel | null>(null);
   const [notebook, setNotebook] = useState<NotebookDocument | null>(null);
   const [isLoading, setIsLoading] = useState<boolean>(true);
   const [isSaving, setIsSaving] = useState<boolean>(false);
   const [error, setError] = useState<string | null>(null);
   // Store readiness is derived from instance state now

   // Use multi-instance notebook store (instance per file)
   const instanceId = fileId ? notebookInstanceId(fileId) : null;
   const createInstance = useNotebookStore((state) => state.createInstance);
   const removeInstance = useNotebookStore((state) => state.removeInstance);
   const setDocument = useNotebookStore((state) => state.setDocument);
   const setReadonly = useNotebookStore((state) => state.setReadonly);
   const storeDocument = useNotebookStore((state) =>
      instanceId ? state.getInstanceState(instanceId)?.document : null
   );
   const instanceState = useNotebookStore((state) =>
      instanceId ? state.getInstanceState(instanceId) : undefined
   );

   // Get isDirty state from the Zustand store
   const isDirty = useNotebookStore((state) =>
      instanceId ? state.getInstanceState(instanceId)?.isDirty || false : false
   );

   // Check if user can edit notebooks (has contributor permissions)
   const canEditNotebook = canContributeToProject(currentProject);

   // Users without edit permissions should start in preview mode and stay there
   // Users with edit permissions start in edit mode (false = edit mode, true = preview mode)
   const shouldStartInPreviewMode = !canEditNotebook;

   // Initialize notebook services
   const { fileSystem, executionEngine } = useNotebookHostBindings(
      currentProject.id,
      apiErrorHandler
   );

   const fileWorkflow = useFileWorkflow({
      projectId: currentProject.id
   });
   const { loadNotebook, saveNotebook } = useNotebookFileHelpers(fileWorkflow);
   const ui = useUiFeedback();
   const renderTriggerActor = useProjectTriggerActorRenderer();
   const [viewExecutionRunId, setViewExecutionRunId] = useState<string | null>(
      null
   );

   // Add effect for beforeunload
   useEffect(() => {
      const handleBeforeUnload = (event: BeforeUnloadEvent) => {
         if (isDirty) {
            event.preventDefault();
            // Modern browsers show a generic message.
            // For legacy browsers, assigning an empty string is sufficient.
            event.returnValue = "";
         }
      };

      window.addEventListener("beforeunload", handleBeforeUnload);

      return () => {
         window.removeEventListener("beforeunload", handleBeforeUnload);
      };
   }, [isDirty]);

   // Block React Router navigation when there are unsaved changes
   useNavigationBlock(
      isDirty,
      "You have unsaved changes. Are you sure you want to leave this page?"
   );

   // Fetch notebook resource and content
   useEffect(() => {
      const fetchNotebook = async () => {
         if (!fileId) return;

         setIsLoading(true);
         setError(null);

         try {
            const {
               notebook,
               file: loadedFile,
               error
            } = await loadNotebook(fileId, {
               fallbackTitle: resource?.name,
               createEmptyOnParseError: true
            });

            if (error) setError(error);

            if (loadedFile) {
               setResource(loadedFile);
            }

            if (notebook) {
               setNotebook(notebook);
            }
         } catch (err) {
            console.error("Error fetching notebook:", err);
            setError("Failed to load notebook");
         } finally {
            setIsLoading(false);
         }
      };

      fetchNotebook();
   }, [fileId, loadNotebook, resource?.name]);

   const resourceId = resource?.id;
   const resourceName = resource?.name;
   const currentProjectId = currentProject?.id;

   const handleSave = useCallback(
      async (document: NotebookDocument) => {
         if (!resourceId || !currentProjectId) {
            throw new Error("Notebook save is not available");
         }

         setIsSaving(true);
         try {
            // Update the document's modified timestamp
            const updatedDocument = {
               ...document,
               modified: Date.now()
            };

            const updateResult = await saveNotebook(
               resourceId,
               updatedDocument,
               updatedDocument.title || resourceName || "Notebook"
            );

            if (updateResult.success && updateResult.file) {
               // Update local state with the updated file info and document
               setResource(updateResult.file);
               setNotebook(updatedDocument);
               // Note: isDirty state is now managed by the NotebookEditor and Zustand store
               message.success("Notebook saved successfully.");
               return;
            }

            throw new Error("Failed to save notebook");
         } catch (error) {
            console.error("Error saving notebook:", error);

            // Extract more detailed error information if available
            const errorMessage =
               error instanceof Error
                  ? error.message
                  : "Failed to save notebook";

            message.error(errorMessage);
            throw error instanceof Error ? error : new Error(errorMessage);
         } finally {
            setIsSaving(false);
         }
      },
      [resourceId, resourceName, currentProjectId, saveNotebook, message]
   );

   const sidebarExtensions = useMemo<SidebarTabExtension[]>(() => {
      return [
         {
            key: "sessions",
            label: "Sessions",
            icon: <DatabaseZapOutlined />,
            children: (
               <NotebookSessionsSidebarTab
                  projectId={currentProject.id}
                  readonly={!canEditNotebook}
               />
            )
         }
      ];
   }, [canEditNotebook, currentProject.id]);

   // Ensure a dedicated store instance exists for this resource; update doc/config idempotently
   useEffect(() => {
      if (!notebook || !instanceId) return;

      if (!instanceState) {
         // Create once for this resource
         createInstance(instanceId, {
            document: notebook,
            isDarkMode: false,
            readonly: !canEditNotebook
         });
         return;
      }

      // Instance exists: only update document if the notebook was reloaded from server
      // (older modified timestamp indicates server update)
      const currentDoc = instanceState.document;
      const isServerUpdate =
         !currentDoc ||
         (notebook.modified && notebook.modified > (currentDoc.modified || 0));

      if (isServerUpdate) {
         setDocument(notebook, instanceId);
      }

      // Keep readonly in sync with permission changes without recreating instance
      if (instanceState.readonly !== !canEditNotebook) {
         setReadonly(!canEditNotebook, instanceId);
      }
   }, [
      notebook,
      instanceId,
      instanceState,
      canEditNotebook,
      createInstance,
      setDocument,
      setReadonly
   ]);

   // Cleanup the store instance on unmount or when instanceId changes
   useEffect(() => {
      if (!instanceId) return;
      return () => removeInstance(instanceId);
   }, [instanceId, removeInstance]);

   // Authentication loading check
   if (isUserLoading) {
      return <LoadingSpinner />;
   }

   if (isLoading) {
      return <LoadingSpinner />;
   }

   if (error || !resource || !notebook) {
      return (
         <PageContainer
            title="Notebook Not Found"
            routeName={RouteNames.PROJECT_NOTEBOOK_DETAIL}
            project={currentProject}
            showBreadcrumb={false}
            showPageTitle={false}
         >
            <Flex justify="center" align="center" style={{ minHeight: "50vh" }}>
               <AccessDeniedAlert
                  title="Notebook Not Found"
                  description={
                     error || "The requested notebook could not be found."
                  }
                  status="404"
               />
            </Flex>
         </PageContainer>
      );
   }

   return (
      <PageContainer
         title={storeDocument?.title || resource?.name || "Notebook"}
         routeName={RouteNames.PROJECT_NOTEBOOK_DETAIL}
         project={currentProject}
         showBreadcrumb={false}
         showPageTitle={false}
         fluid
         style={{ height: "100%" }}
      >
         {!instanceId || !storeDocument ? (
            <LoadingSpinner />
         ) : (
            <div
               style={{
                  flex: 1,
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  overflow: "hidden",
                  minHeight: 0
               }}
            >
               <NotebookServiceProvider
                  projectId={currentProject.id}
                  projectCode={currentProject.projectCode}
                  notebookId={fileId}
                  onViewExecutionRun={setViewExecutionRunId}
                  fileSystem={fileSystem}
                  executionEngine={executionEngine}
               >
                  <NotebookEditor
                     instanceId={instanceId}
                     onSave={handleSave}
                     readonly={!canEditNotebook}
                     previewMode={shouldStartInPreviewMode}
                     enableSqlBlock
                     enableChartBlock
                     saveButtonText={isSaving ? "Saving..." : "Save"}
                     maxHeight="100%"
                     showHeader={true}
                     cultures={cultures}
                     projectId={currentProject.id}
                     sidebarExtensions={sidebarExtensions}
                     errorHandler={apiErrorHandler}
                  />
                  <JobRunDetailsDrawerHost
                     projectId={currentProject.id}
                     runId={viewExecutionRunId}
                     onClose={() => setViewExecutionRunId(null)}
                     ui={ui}
                     errorHandler={apiErrorHandler}
                     renderTriggerActor={renderTriggerActor}
                  />
               </NotebookServiceProvider>
            </div>
         )}
      </PageContainer>
   );
};

const NotebookDetailPage = () => {
   const { fileId } = useParams<{
      projectCode: string;
      fileId: string;
   }>();
   const { currentProject } = useProject();

   if (!currentProject) return null;

   return (
      <NotebookDetailPageContent
         fileId={fileId}
         currentProject={currentProject}
      />
   );
};

export default NotebookDetailPage;
