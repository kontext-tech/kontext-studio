import { useChartDocument } from "@/hooks/useChartDocument";
import { usePermissionContext } from "@/context/AppPermissionContext";
import { ProjectRole } from "@kontext-tech/auth";
import { ChartDocumentView } from "@kontext-tech/chart";
import { useProject } from "@kontext-tech/project";
import type { Artifact, ProjectModel } from "@kontext-tech/schema";
import { LoadingSpinner } from "@kontext-tech/ui";
import { Alert, Button, Empty } from "antd";

interface ChartViewerProps {
   artifact: Artifact;
   readonly?: boolean;
   onTitleChange?: (title: string) => void;
   refreshToken?: number;
}

/**
 * Inner content component that requires a loaded project
 */
const ChartViewerContent: React.FC<{
   artifact: Artifact;
   project: ProjectModel;
   readonly: boolean;
   onTitleChange?: (title: string) => void;
   refreshToken?: number;
}> = ({ artifact, project, readonly, onTitleChange, refreshToken = 0 }) => {
   const { hasAtLeastOneRole } = usePermissionContext();

   const projectId = project.id;
   const canEdit =
      !readonly &&
      hasAtLeastOneRole(
         [ProjectRole.OWNER, ProjectRole.ADMIN, ProjectRole.CONTRIBUTOR],
         project
      );

   const {
      chart,
      isLoading,
      isSaving,
      error,
      setIsLoading,
      remoteTable,
      isRemoteDataLoading,
      remoteDataError,
      handleSave
   } = useChartDocument({
      fileId: artifact.artifactId,
      projectId,
      fallbackTitle: artifact.artifactId,
      onTitleChange,
      refreshToken,
      suppressSameContentReload: true
   });

   if (isLoading) {
      return (
         <div
            style={{
               display: "flex",
               justifyContent: "center",
               alignItems: "center",
               height: "400px"
            }}
         >
            <LoadingSpinner size="large" />
         </div>
      );
   }

   if (error) {
      return (
         <Alert
            title="Error Loading Chart"
            description={error}
            type="error"
            showIcon
            style={{ margin: "16px" }}
            action={
               <Button size="small" onClick={() => setIsLoading(true)}>
                  Retry
               </Button>
            }
         />
      );
   }

   if (!chart) {
      return (
         <div style={{ padding: "16px" }}>
            <Empty description="Chart not found" />
         </div>
      );
   }

   // Render the actual chart using ChartDocumentView
   // Chart data fetching is handled here in the viewer and passed down
   return (
      <ChartDocumentView
         chart={chart}
         remoteTable={remoteTable}
         isRemoteDataLoading={isRemoteDataLoading}
         remoteDataError={remoteDataError}
         readonly={readonly}
         canEdit={canEdit}
         onSave={handleSave}
         isSaving={isSaving}
      />
   );
};

/**
 * ChartViewer component to display chart artifacts
 *
 * Loads chart JSON documents from storage and displays them.
 */
const ChartViewer: React.FC<ChartViewerProps> = ({
   artifact,
   readonly = false,
   onTitleChange,
   refreshToken
}) => {
   const { currentProject, isProjectLoading, projectNotFound } = useProject();

   if (isProjectLoading) {
      return (
         <div
            style={{
               display: "flex",
               justifyContent: "center",
               alignItems: "center",
               height: "400px"
            }}
         >
            <LoadingSpinner size="large" />
         </div>
      );
   }

   if (projectNotFound || !currentProject) {
      return (
         <div style={{ padding: "16px" }}>
            <Empty description="Project not found or access denied" />
         </div>
      );
   }

   return (
      <ChartViewerContent
         artifact={artifact}
         project={currentProject}
         readonly={readonly}
         onTitleChange={onTitleChange}
         refreshToken={refreshToken}
      />
   );
};

export default ChartViewer;
