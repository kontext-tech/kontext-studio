import PageHeader from "@/components/common/PageHeader";
import PageContainer from "@/components/layout/SeoPageContainer";
import { usePermissionContext } from "@/context/AppPermissionContext";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useChartDocument } from "@/hooks/useChartDocument";
import { useFileResource } from "@/hooks/useFileResource";
import { ProjectRole } from "@kontext-labs/auth";
import { ChartDocumentView } from "@kontext-labs/chart";
import { useProject } from "@kontext-labs/project";
import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { FileActions } from "@kontext-labs/file";
import type { FileModel, ProjectModel } from "@kontext-labs/schema";
import { LoadingSpinner } from "@kontext-labs/ui";
import { Alert, Empty } from "antd";
import { useNavigate, useParams } from "react-router-dom";

/**
 * Inner component that requires a loaded project
 */
const ChartDetailPageContent = ({
   project,
   fileId
}: {
   project: ProjectModel;
   fileId: string;
}) => {
   const apiErrorHandler = useApiErrorHandler();
   const { hasAtLeastOneRole } = usePermissionContext();
   const navigate = useNavigate();
   const { getFilesOverviewPath } = useRoute();

   const {
      chart,
      isLoading,
      isSaving,
      error,
      remoteTable,
      isRemoteDataLoading,
      remoteDataError,
      handleSave,
      fileWorkflow
   } = useChartDocument({ fileId, projectId: project.id });
   const { downloadFile, deleteFile } = fileWorkflow;

   const canEdit = hasAtLeastOneRole(
      [ProjectRole.OWNER, ProjectRole.ADMIN, ProjectRole.CONTRIBUTOR],
      project
   );

   const { data: fileModel = null } = useFileResource(
      fileId,
      project.id,
      apiErrorHandler
   );

   const handleRename = async (newName: string) => {
      if (!chart) return;
      await handleSave({ ...chart, name: newName });
   };

   const handleDelete = async (file: FileModel) => {
      if (await deleteFile(file)) {
         navigate(getFilesOverviewPath(project));
      }
   };

   if (isLoading) {
      return <LoadingSpinner />;
   }

   if (error) {
      return (
         <PageContainer
            title="Chart Error"
            project={project}
            routeName={RouteNames.PROJECT_CHART_DETAIL}
         >
            <Alert title={error} type="error" showIcon />
         </PageContainer>
      );
   }

   if (!chart) {
      return (
         <PageContainer
            title="Chart Not Found"
            project={project}
            routeName={RouteNames.PROJECT_CHART_DETAIL}
         >
            <Empty description="The requested chart could not be found." />
         </PageContainer>
      );
   }

   return (
      <PageContainer
         title={chart.name}
         description={`Visualize and analyze ${chart.name}.`}
         project={project}
         routeName={RouteNames.PROJECT_CHART_DETAIL}
         type="website"
         fluid
         showPageTitle={false}
         style={{ height: "100%" }}
      >
         <div
            style={{
               display: "flex",
               flexDirection: "column",
               flex: 1,
               overflow: "hidden",
               minHeight: 0
            }}
         >
            <PageHeader
               variant="application"
               title={chart.name}
               onSaveTitle={handleRename}
               isSaving={isSaving}
               isTitleEditable={true}
               actions={
                  fileModel && (
                     <FileActions
                        file={fileModel}
                        onDownload={downloadFile}
                        onDelete={handleDelete}
                        showDelete
                        usePermissions
                     />
                  )
               }
            />
            <div
               style={{
                  flex: 1,
                  overflow: "auto",
                  display: "flex",
                  justifyContent: "center"
               }}
            >
               <div
                  style={{ width: "100%", maxWidth: 1200, padding: "0 24px" }}
               >
                  <ChartDocumentView
                     chart={chart}
                     remoteTable={remoteTable}
                     isRemoteDataLoading={isRemoteDataLoading}
                     remoteDataError={remoteDataError}
                     canEdit={canEdit}
                     onSave={handleSave}
                     isSaving={isSaving}
                  />
               </div>
            </div>
         </div>
      </PageContainer>
   );
};

const ChartDetailPage = () => {
   const { fileId } = useParams<{ fileId: string }>();
   const { currentProject } = useProject();

   if (!currentProject) return null;

   if (!currentProject || !fileId) {
      return null;
   }

   return <ChartDetailPageContent project={currentProject} fileId={fileId} />;
};

export default ChartDetailPage;
