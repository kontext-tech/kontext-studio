import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useInlineDataFile } from "@kontext-tech/file";
import { useProject } from "@kontext-tech/project";
import { DataTablePreview } from "@kontext-tech/query";
import type { Artifact, ProjectModel } from "@kontext-tech/schema";
import { LoadingSpinner } from "@kontext-tech/ui";
import { Alert, Empty } from "antd";
import React, { useEffect } from "react";

interface DataTableViewerProps {
   artifact: Artifact;
   onTitleChange?: (title: string) => void;
}

/**
 * Inner content component that requires a loaded project
 */
const DataTableViewerContent: React.FC<{
   artifact: Artifact;
   project: ProjectModel;
   onTitleChange?: (title: string) => void;
}> = ({ artifact, project, onTitleChange }) => {
   const apiErrorHandler = useApiErrorHandler();
   const { inlineData, isLoading, error } = useInlineDataFile(
      artifact.artifactId,
      project.id,
      apiErrorHandler
   );

   useEffect(() => {
      if (onTitleChange) {
         // Priority:
         // 1. Specific title in file content (if not generic "Data Table")
         // 2. Artifact title from metadata (if not generic "Data Table")

         const dataTableTitle = inlineData?.title;
         const isContentGeneric =
            !dataTableTitle ||
            dataTableTitle === "Data Table" ||
            dataTableTitle === "query-result";
         const isArtifactGeneric =
            !artifact.title ||
            artifact.title === "Data Table" ||
            artifact.title === "query-result";

         if (!isContentGeneric) {
            // Use title from the .dt file content
            onTitleChange(dataTableTitle!);
         } else if (!isArtifactGeneric) {
            // Use title from the session artifact record (link table)
            onTitleChange(artifact.title);
         }
      }
   }, [inlineData?.title, artifact.title, onTitleChange]);

   if (isLoading) {
      return (
         <div style={{ padding: "12px" }}>
            <LoadingSpinner />
         </div>
      );
   }

   if (error) {
      return (
         <div style={{ padding: "12px" }}>
            <Alert
               title="Error"
               description={
                  error instanceof Error ? error.message : String(error)
               }
               type="error"
               showIcon
            />
         </div>
      );
   }

   if (!inlineData || !inlineData.table) {
      return (
         <div style={{ padding: "12px" }}>
            <Empty description="No table data available" />
         </div>
      );
   }

   return <DataTablePreview data={inlineData} compact />;
};

/**
 * DataTableViewer - Specialized viewer for ArtifactType.DataTable
 */
const DataTableViewer: React.FC<DataTableViewerProps> = ({
   artifact,
   onTitleChange
}) => {
   const { currentProject } = useProject();

   if (!currentProject) {
      return <LoadingSpinner />;
   }

   return (
      <DataTableViewerContent
         artifact={artifact}
         project={currentProject}
         onTitleChange={onTitleChange}
      />
   );
};

export default DataTableViewer;
