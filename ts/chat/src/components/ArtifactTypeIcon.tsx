import {
   FileChartLineOutlined,
   FileImageOutlined,
   FileTextOutlined,
   NotebookOutlined,
   TableOutlined
} from "@kontext-labs/icons";
import { ArtifactType } from "@kontext-labs/schema";
import React from "react";

export interface ArtifactTypeIconProps {
   type: ArtifactType;
}

const ArtifactTypeIcon: React.FC<ArtifactTypeIconProps> = ({ type }) => {
   switch (type) {
      case ArtifactType.DataTable:
         return <TableOutlined />;
      case ArtifactType.Notebook:
         return <NotebookOutlined />;
      case ArtifactType.Chart:
         return <FileChartLineOutlined />;
      case ArtifactType.Image:
         return <FileImageOutlined />;
      default:
         return <FileTextOutlined />;
   }
};

export default ArtifactTypeIcon;
