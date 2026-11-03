import { QuerySessionManager } from "@kontext-labs/query";
import { Space, Typography } from "antd";
import React from "react";

const { Text, Title } = Typography;

export interface NotebookSessionsSidebarTabProps {
   projectId: string;
   readonly?: boolean;
}

const styles = {
   container: { padding: "8px 0" },
   fullWidth: { width: "100%" },
   header: { margin: "0 0 8px 0" },
   subtitle: { fontSize: "12px" }
};

const NotebookSessionsSidebarTab: React.FC<NotebookSessionsSidebarTabProps> = ({
   projectId,
   readonly = false
}) => {
   return (
      <div style={styles.container}>
         <Space orientation="vertical" style={styles.fullWidth} size="middle">
            <div>
               <Title level={5} style={styles.header}>
                  Query Sessions
               </Title>
               <Text type="secondary" style={styles.subtitle}>
                  Manage SQL query sessions for this notebook
               </Text>
            </div>

            {!readonly && <QuerySessionManager projectId={projectId} />}

            {readonly && (
               <Text type="secondary">
                  Session management is disabled in readonly mode
               </Text>
            )}
         </Space>
      </div>
   );
};

export default NotebookSessionsSidebarTab;
