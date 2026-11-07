import {
   FileChartLineOutlined,
   FileCogOutlined,
   FileDigitOutlined,
   FileImageOutlined,
   FileJsonOutlined,
   FileOutlined,
   FileSpreadsheetOutlined,
   FileTextOutlined,
   NotebookOutlined
} from "@kontext-tech/icons";
import { FileFormatType } from "@kontext-tech/schema";
import React from "react";

export interface FileIconProps {
   fileType: FileFormatType;
   style?: React.CSSProperties;
   className?: string;
}

/**
 * Component that displays the appropriate icon for a given file format type
 * @param fileType - The type of file format
 * @param style - Optional style object to apply to the icon
 * @param className - Optional CSS class name
 */
export const FileIcon: React.FC<FileIconProps> = ({
   fileType,
   style,
   className
}) => {
   const defaultStyle = { fontSize: 20, ...style };
   const props = { style: defaultStyle, className };

   switch (fileType) {
      case FileFormatType.Notebook:
         return <NotebookOutlined {...props} />;
      case FileFormatType.Image:
         return <FileImageOutlined {...props} />;
      case FileFormatType.PDF:
         return <FileOutlined {...props} />;
      case FileFormatType.Text:
      case FileFormatType.Markdown:
         return <FileTextOutlined {...props} />;
      case FileFormatType.CSV:
      case FileFormatType.TSV:
         return <FileSpreadsheetOutlined {...props} />;
      case FileFormatType.JSON:
      case FileFormatType.JSONL:
         return <FileJsonOutlined {...props} />;
      case FileFormatType.Parquet:
         return <FileDigitOutlined {...props} />;
      case FileFormatType.DataTable:
         return <FileCogOutlined {...props} />;
      case FileFormatType.Chart:
         return <FileChartLineOutlined {...props} />;
      case FileFormatType.DrawIO:
         return <FileImageOutlined {...props} />;
      default:
         return <FileOutlined {...props} />;
   }
};
