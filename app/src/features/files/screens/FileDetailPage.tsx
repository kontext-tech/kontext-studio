import PageHeader from "@/components/common/PageHeader";
import PageContainer from "@/components/layout/SeoPageContainer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useFileResource } from "@/hooks/useFileResource";
import { AccessDeniedAlert } from "@kontext-labs/auth";
import { useUiApp } from "@kontext-labs/ui";
import {
   FileActions,
   FileDetailView,
   ImagePreviewModal,
   useFileService,
   useFileWorkflow
} from "@kontext-labs/file";
import { useProject } from "@kontext-labs/project";
import { useRoute } from "@/hooks/useRoute";
import { useUser } from "@kontext-labs/identity";
import { RouteNames } from "@/types";
import { type FileModel, FileFormatType } from "@kontext-labs/schema";
import { LoadingSpinner } from "@kontext-labs/ui";
import { Flex } from "antd";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

const FileDetailPage = () => {
   const { fileId } = useParams<{
      projectCode: string;
      fileId: string;
   }>();
   const { currentProject } = useProject();
   const { isLoading: isUserLoading } = useUser();
   const [fileOverride, setFileOverride] = useState<FileModel | null>(null);
   const [isSaving, setIsSaving] = useState<boolean>(false);
   const [previewVisible, setPreviewVisible] = useState<boolean>(false);

   const navigate = useNavigate();
   const { getFilesOverviewPath } = useRoute();
   const apiErrorHandler = useApiErrorHandler();
   const { message } = useUiApp();

   const fileService = useFileService(apiErrorHandler);

   const {
      data: fetchedFile,
      isLoading: isFileLoading,
      error: fileError
   } = useFileResource(fileId, currentProject?.id, apiErrorHandler);

   // Local override keeps the UI in sync after a rename until the query refetches.
   const file =
      fileOverride?.id === fileId ? fileOverride : (fetchedFile ?? null);
   const error = fileError ? "Failed to load file" : null;

   const { downloadFile, deleteFile } = useFileWorkflow({
      projectId: currentProject?.id
   });

   const handleRename = async (newName: string) => {
      if (!file || !currentProject) return;

      setIsSaving(true);
      try {
         const result = await fileService.updateFile({
            fileId: file.id!,
            projectId: currentProject.id,
            name: newName
         });

         if (result.succeed) {
            setFileOverride({ ...file, name: newName });
            message.success("File renamed successfully");
         } else {
            message.error("Failed to rename file");
         }
      } catch (err) {
         console.error("Error renaming file:", err);
         message.error("Error renaming file");
      } finally {
         setIsSaving(false);
      }
   };

   const handlePreview = () => {
      setPreviewVisible(true);
   };

   const handleDelete = async (fileToDelete: FileModel) => {
      const success = await deleteFile(fileToDelete);
      if (success && currentProject) {
         // Navigate back to files list after successful deletion
         navigate(getFilesOverviewPath(currentProject));
      }
   };

   // Authentication loading check
   if (isUserLoading) {
      return <LoadingSpinner />;
   }

   if (!currentProject || !fileId) {
      return null;
   }

   if (isFileLoading) {
      return <LoadingSpinner />;
   }

   if (error || !file) {
      return (
         <PageContainer
            title="File Not Found"
            routeName={RouteNames.PROJECT_FILE_DETAIL}
            project={currentProject}
         >
            <Flex justify="center" align="center" style={{ minHeight: "50vh" }}>
               <AccessDeniedAlert
                  title="File Not Found"
                  description={
                     error || "The requested file could not be found."
                  }
                  status="404"
               />
            </Flex>
         </PageContainer>
      );
   }

   return (
      <PageContainer
         title={`${file.name}`}
         routeName={RouteNames.PROJECT_FILE_DETAIL}
         project={currentProject}
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
               title={file.name}
               onSaveTitle={handleRename}
               isSaving={isSaving}
               isTitleEditable={
                  file.fileType === FileFormatType.Notebook ||
                  file.fileType === FileFormatType.Chart ||
                  file.fileType === FileFormatType.DataTable
               }
               actions={
                  <FileActions
                     file={file}
                     onDownload={downloadFile}
                     onPreview={handlePreview}
                     onDelete={handleDelete}
                     showPreview
                     showDelete
                     usePermissions
                  />
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
                  <FileDetailView file={file} />
               </div>
            </div>
            <ImagePreviewModal
               visible={previewVisible}
               resource={file}
               projectId={currentProject.id}
               onClose={() => setPreviewVisible(false)}
            />
         </div>
      </PageContainer>
   );
};

export default FileDetailPage;
