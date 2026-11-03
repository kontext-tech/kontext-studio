import { formatFileSize } from "@kontext-labs/common";
import type { FileModel } from "@kontext-labs/schema";
import { Descriptions, Typography } from "antd";

const { Text } = Typography;

export interface FileDetailViewProps {
   file: FileModel;
}

const FileDetailView = ({ file }: FileDetailViewProps) => {
   return (
      <Descriptions column={1} bordered>
         <Descriptions.Item label="File ID">
            <Text copyable code>
               {file.id}
            </Text>
         </Descriptions.Item>
         <Descriptions.Item label="Name">{file.name}</Descriptions.Item>
         <Descriptions.Item label="Type">{file.fileType}</Descriptions.Item>
         <Descriptions.Item label="Content Type">
            {file.contentType || "Unknown"}
         </Descriptions.Item>
         <Descriptions.Item label="Size">
            {formatFileSize(file.size || 0)}
         </Descriptions.Item>
         <Descriptions.Item label="Access Level">
            {file.accessLevel}
         </Descriptions.Item>
         <Descriptions.Item label="Owner">
            {file.ownerId ? (
               <Text copyable code>
                  {file.ownerId}
               </Text>
            ) : (
               <Text type="secondary">Unknown</Text>
            )}
         </Descriptions.Item>
         <Descriptions.Item label="Created Date">
            {file.dateCreated
               ? new Date(file.dateCreated).toLocaleString()
               : "Unknown"}
         </Descriptions.Item>
      </Descriptions>
   );
};

export default FileDetailView;
