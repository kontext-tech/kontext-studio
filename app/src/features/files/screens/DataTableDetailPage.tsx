import PageHeader from "@/components/common/PageHeader";
import PageContainer from "@/components/layout/SeoPageContainer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useFileResource } from "@/hooks/useFileResource";
import { useRoute } from "@/hooks/useRoute";
import { useFileWorkflow, useInlineDataFile } from "@kontext-tech/file";
import { useProject } from "@kontext-tech/project";
import { RouteNames } from "@/types";
import { DataTablePreview } from "@kontext-tech/query";
import { FileActions } from "@kontext-tech/file";
import type { FileModel } from "@kontext-tech/schema";
import { LoadingSpinner } from "@kontext-tech/ui";
import { Alert, Empty } from "antd";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const DataTableDetailPage = () => {
   const { fileId } = useParams<{ fileId: string }>();
   const { currentProject } = useProject();
   const navigate = useNavigate();
   const { getFilesOverviewPath } = useRoute();
   const apiErrorHandler = useApiErrorHandler();

   const [nameOverride, setNameOverride] = useState<string | null>(null);
   const [isSaving, setIsSaving] = useState<boolean>(false);

   const { updateFile, downloadFile, deleteFile } = useFileWorkflow({
      projectId: currentProject?.id
   });

   const {
      data: fileModel,
      isLoading: isMetadataLoading,
      error: metadataQueryError
   } = useFileResource(fileId, currentProject?.id, apiErrorHandler);

   const metadataError = metadataQueryError
      ? "An unexpected error occurred while loading"
      : undefined;
   const title = nameOverride ?? fileModel?.name ?? "Data Table Details";

   // Use the standalone hook for data loading (no notebook context required)
   const {
      table,
      inlineData,
      isLoading: isDataLoading,
      error: dataError
   } = useInlineDataFile(fileId, currentProject?.id, apiErrorHandler);

   const handleRename = async (newName: string) => {
      if (!fileId) return;
      setIsSaving(true);
      const result = await updateFile({ fileId, name: newName });
      if (result.success) {
         setNameOverride(newName);
      }
      setIsSaving(false);
   };

   const handleDelete = async (file: FileModel) => {
      if (await deleteFile(file)) {
         navigate(getFilesOverviewPath(currentProject!));
      }
   };

   if (!currentProject) {
      return (
         <PageContainer
            title="Data Table"
            routeName={RouteNames.PROJECT_DATA_TABLE_DETAIL}
            type="website"
         >
            <Alert title="Project not found" type="error" />
         </PageContainer>
      );
   }

   if (metadataError || dataError) {
      return (
         <PageContainer
            title="Data Table"
            project={currentProject}
            routeName={RouteNames.PROJECT_DATA_TABLE_DETAIL}
            type="website"
            fluid
            showPageTitle={false}
         >
            <div style={{ padding: "24px" }}>
               <Alert
                  title="Error"
                  description={
                     metadataError ||
                     dataError?.message ||
                     "Failed to load data table"
                  }
                  type="error"
                  showIcon
               />
            </div>
         </PageContainer>
      );
   }

   const isLoading = (isDataLoading || isMetadataLoading) && !fileModel;

   if (isLoading) {
      return <LoadingSpinner />;
   }

   return (
      <PageContainer
         title="Data Table"
         description="Explore and preview the data table."
         project={currentProject}
         routeName={RouteNames.PROJECT_DATA_TABLE_DETAIL}
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
               title={title}
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
               <div style={{ width: "100%", maxWidth: 1200, padding: "24px" }}>
                  {isDataLoading && !table ? (
                     <LoadingSpinner />
                  ) : inlineData ? (
                     <DataTablePreview data={inlineData} />
                  ) : (
                     <Empty description="No compatible data found in this file." />
                  )}
               </div>
            </div>
         </div>
      </PageContainer>
   );
};

export default DataTableDetailPage;
