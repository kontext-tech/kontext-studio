import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useProjectTriggerActorRenderer } from "@/features/projects/hooks/useProjectTriggerActorRenderer";
import { useNotebookHostBindings } from "@/hooks/useNotebookHostBindings";
import {
   ChatArtifactsPanel,
   useChatSessionStore,
   useChatSessionStoreApi,
   type ChatArtifactRenderParams
} from "@kontext-tech/chat";
import { ImageViewer } from "@kontext-tech/file";
import { JobRunDetailsDrawerHost } from "@kontext-tech/job";
import { NotebookViewer } from "@kontext-tech/notebook";
import { useProject } from "@kontext-tech/project";
import type { Artifact } from "@kontext-tech/schema";
import { ArtifactType } from "@kontext-tech/schema";
import { useUiFeedback } from "@kontext-tech/ui";
import { Card, Typography } from "antd";
import React from "react";
import ChartViewer from "./ChartViewer";
import DataTableViewer from "./DataTableViewer";

const { Text } = Typography;

interface ProjectChatArtifactsPanelProps {
   artifacts: Artifact[];
   onClose?: () => void;
   onRemoveArtifact?: (artifactId: string) => void;
   onAutoRename?: (title: string) => void;
}

const ProjectChatArtifactsPanel: React.FC<ProjectChatArtifactsPanelProps> = ({
   artifacts,
   onClose,
   onRemoveArtifact,
   onAutoRename
}) => {
   const { currentProject } = useProject();
   const apiErrorHandler = useApiErrorHandler();
   const artifactRuntimeById = useChatSessionStore(
      (state) => state.artifactRuntimeById
   );
   const chatSession = useChatSessionStore((state) => state.chatSession);
   const chatSessionStoreApi = useChatSessionStoreApi();
   // Memoize the chat scope: it feeds a useMemo in useNotebookHostBindings, so
   // an inline object here would rebuild `executionEngine` on every render and
   // force the notebook's block portals to re-render.
   const chatScope = React.useMemo(
      () =>
         chatSession
            ? {
                 chatSessionId: chatSession.id,
                 querySessionId: chatSession.querySessionId,
                 defaultCatalogConnectionId:
                    chatSession.defaultCatalogConnectionId,
                 defaultNamespace: chatSession.defaultNamespace,
                 defaultEntityId: chatSession.defaultEntityId
              }
            : undefined,
      [chatSession]
   );
   const { fileSystem, executionEngine } = useNotebookHostBindings(
      currentProject?.id ?? "",
      apiErrorHandler,
      chatScope,
      chatSessionStoreApi
   );
   const ui = useUiFeedback();
   const renderTriggerActor = useProjectTriggerActorRenderer();
   const [viewExecutionRunId, setViewExecutionRunId] = React.useState<
      string | null
   >(null);
   const renderArtifactContent = React.useCallback(
      ({ artifact, onTitleChange }: ChatArtifactRenderParams) => {
         const runtimeState = artifactRuntimeById[artifact.artifactId];

         switch (artifact.artifactType) {
            case ArtifactType.Notebook:
               if (!currentProject?.id) {
                  return (
                     <Card size="small">Project context is unavailable.</Card>
                  );
               }

               return (
                  <NotebookViewer
                     artifact={artifact}
                     projectId={currentProject.id}
                     projectCode={currentProject.projectCode}
                     onViewExecutionRun={setViewExecutionRunId}
                     fileSystem={fileSystem}
                     executionEngine={executionEngine}
                     readonly={false}
                     onTitleChange={onTitleChange}
                     streamingActions={runtimeState?.pendingActions}
                     refreshToken={runtimeState?.refreshToken}
                  />
               );
            case ArtifactType.Chart:
               return (
                  <ChartViewer
                     artifact={artifact}
                     readonly={false}
                     onTitleChange={onTitleChange}
                     refreshToken={runtimeState?.refreshToken}
                  />
               );
            case ArtifactType.DataTable:
               return (
                  <DataTableViewer
                     artifact={artifact}
                     onTitleChange={onTitleChange}
                  />
               );
            case ArtifactType.Image:
               if (!currentProject?.id) {
                  return (
                     <Card size="small">Project context is unavailable.</Card>
                  );
               }

               return (
                  <ImageViewer
                     artifact={artifact}
                     projectId={currentProject.id}
                  />
               );
            default:
               return (
                  <Card size="small">
                     <Text type="secondary">Unknown artifact type</Text>
                  </Card>
               );
         }
      },
      [artifactRuntimeById, currentProject, executionEngine, fileSystem]
   );

   return (
      <>
         <ChatArtifactsPanel
            artifacts={artifacts}
            host={{
               renderArtifactContent
            }}
            onClose={onClose}
            onRemoveArtifact={onRemoveArtifact}
            onAutoRename={onAutoRename}
         />
         {currentProject?.id ? (
            <JobRunDetailsDrawerHost
               projectId={currentProject.id}
               runId={viewExecutionRunId}
               onClose={() => setViewExecutionRunId(null)}
               ui={ui}
               errorHandler={apiErrorHandler}
               renderTriggerActor={renderTriggerActor}
            />
         ) : null}
      </>
   );
};

export default ProjectChatArtifactsPanel;
