import { UserAvatarById } from "@kontext-labs/identity";
import { formatTimeAgo, logger } from "@kontext-labs/common";
import {
   CalendarOutlined,
   CheckOutlined,
   ClockCircleOutlined,
   CloseOutlined,
   EditOutlined,
   StopOutlined,
   UserOutlined
} from "@kontext-labs/icons";
import {
   Alert,
   Button,
   Card,
   Descriptions,
   Input,
   Space,
   Tooltip,
   Typography,
   theme
} from "antd";
import React, { useState } from "react";
import { useProjectQuerySessions } from "../hooks";
import QuerySessionStatusComponent from "./QuerySessionStatus";

const { Text } = Typography;

export interface QuerySessionInfoProps {
   projectId: string;
   sessionId: string;
   onClose: () => void;
   onMessage?: (
      type: "success" | "error" | "warning" | "info",
      content: string
   ) => void;
}

export const QuerySessionInfo: React.FC<QuerySessionInfoProps> = ({
   projectId,
   sessionId,
   onClose,
   onMessage
}) => {
   const { token } = theme.useToken();
   const [isEditingName, setIsEditingName] = useState(false);
   const [editingName, setEditingName] = useState("");
   const [isSavingName, setIsSavingName] = useState(false);

   const { closeSession, updateSession, getSession } =
      useProjectQuerySessions(projectId);

   const session = getSession(sessionId);

   const showMessage =
      onMessage ||
      ((type, content) => {
         logger.debug(`[${type.toUpperCase()}] ${content}`);
      });

   const handleCloseSession = async () => {
      try {
         const result = await closeSession(sessionId);
         if (result.succeed) {
            showMessage("success", "Session closed successfully");
            onClose();
         } else {
            showMessage(
               "error",
               result.error?.messages?.[0] || "Failed to close session"
            );
         }
      } catch (error) {
         console.error("Error closing session:", error);
         showMessage(
            "error",
            "An unexpected error occurred while closing the session"
         );
      }
   };

   const handleStartEditName = () => {
      setEditingName(session?.sessionName || "");
      setIsEditingName(true);
   };

   const handleCancelEditName = () => {
      setIsEditingName(false);
      setEditingName("");
   };

   const handleSaveSessionName = async () => {
      if (!editingName.trim() || !session?.id) {
         showMessage("error", "Session name cannot be empty");
         return;
      }

      try {
         setIsSavingName(true);

         const result = await updateSession(session.id, {
            sessionName: editingName.trim()
         });

         if (result) {
            setIsEditingName(false);
            setEditingName("");
            showMessage("success", "Session name updated successfully");
         } else {
            showMessage("error", "Failed to update session name");
         }
      } catch (error) {
         console.error("Error updating session name:", error);
         showMessage("error", "Failed to update session name");
      } finally {
         setIsSavingName(false);
      }
   };

   if (!session) {
      return (
         <Alert
            title="Error"
            description="Session not found"
            type="error"
            showIcon
            action={
               <Button size="small" onClick={onClose}>
                  Close
               </Button>
            }
         />
      );
   }

   return (
      <Card
         style={{ height: "100%", display: "flex", flexDirection: "column" }}
         variant="borderless"
         title={
            isEditingName ? (
               <div
                  style={{
                     display: "flex",
                     alignItems: "center",
                     gap: token.marginXS,
                     width: "100%"
                  }}
               >
                  <Input
                     value={editingName}
                     onChange={(event) => setEditingName(event.target.value)}
                     onPressEnter={handleSaveSessionName}
                     placeholder="Enter session name"
                     size="small"
                     style={{ flex: 1 }}
                     autoFocus
                  />
                  <Button
                     type="primary"
                     size="small"
                     icon={<CheckOutlined />}
                     onClick={handleSaveSessionName}
                     loading={isSavingName}
                  />
                  <Button
                     size="small"
                     icon={<CloseOutlined />}
                     onClick={handleCancelEditName}
                  />
               </div>
            ) : (
               <div
                  style={{
                     display: "flex",
                     alignItems: "center",
                     gap: token.marginXS,
                     minWidth: 0,
                     flex: 1
                  }}
               >
                  <span
                     style={{
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                        flex: 1,
                        minWidth: 0
                     }}
                     title={session.sessionName}
                  >
                     {session.sessionName}
                  </span>
                  <Tooltip title="Edit session name">
                     <Button
                        type="text"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={handleStartEditName}
                        style={{ flexShrink: 0 }}
                     />
                  </Tooltip>
               </div>
            )
         }
         extra={
            <Button
               type="text"
               danger
               icon={<StopOutlined />}
               onClick={handleCloseSession}
               title="Close Session"
            />
         }
      >
         <div style={{ flex: 1, overflow: "auto" }}>
            <Space direction="vertical" size="middle" style={{ width: "100%" }}>
               <QuerySessionStatusComponent status={session.status!} />

               <Descriptions
                  column={1}
                  size="small"
                  bordered
                  title="Session Information"
                  items={[
                     {
                        key: "id",
                        label: "Session ID",
                        children: (
                           <Text code copyable={{ text: session.id || "" }}>
                              {session.id}
                           </Text>
                        )
                     },
                     {
                        key: "catalogConnection",
                        label: "Catalog Connection",
                        children: session.catalogConnectionId ? (
                           <Text
                              code
                              copyable={{ text: session.catalogConnectionId }}
                           >
                              {session.catalogConnectionId}
                           </Text>
                        ) : (
                           <Text type="secondary">Auto-selected</Text>
                        )
                     },
                     {
                        key: "project",
                        label: "Project ID",
                        children: (
                           <Text code copyable={{ text: session.projectId }}>
                              {session.projectId}
                           </Text>
                        )
                     },
                     {
                        key: "owner",
                        label: "Owner",
                        children: session.ownerId ? (
                           <div
                              style={{
                                 display: "flex",
                                 alignItems: "center",
                                 gap: token.marginXS
                              }}
                           >
                              <UserAvatarById
                                 userId={session.ownerId}
                                 size="small"
                                 showTooltip
                                 tooltipText="Owner"
                              />
                              <Text code copyable={{ text: session.ownerId }}>
                                 {session.ownerId}
                              </Text>
                           </div>
                        ) : (
                           <div
                              style={{
                                 display: "flex",
                                 alignItems: "center",
                                 gap: token.marginXS
                              }}
                           >
                              <UserOutlined />
                              <Text type="secondary">System</Text>
                           </div>
                        )
                     },
                     {
                        key: "created",
                        label: "Created",
                        children: session.createdAt ? (
                           <div
                              style={{
                                 display: "flex",
                                 alignItems: "center",
                                 gap: token.marginXXS
                              }}
                           >
                              <CalendarOutlined />
                              <Text>{formatTimeAgo(session.createdAt)}</Text>
                           </div>
                        ) : (
                           <Text type="secondary">Unknown</Text>
                        )
                     },
                     {
                        key: "lastAccessed",
                        label: "Last Accessed",
                        children: session.lastAccessedAt ? (
                           <div
                              style={{
                                 display: "flex",
                                 alignItems: "center",
                                 gap: token.marginXXS
                              }}
                           >
                              <ClockCircleOutlined />
                              <Text>
                                 {formatTimeAgo(session.lastAccessedAt)}
                              </Text>
                           </div>
                        ) : (
                           <Text type="secondary">Never</Text>
                        )
                     }
                  ]}
               />

               {session.errorMessage && (
                  <Alert
                     title="Session Error"
                     description={session.errorMessage}
                     type="error"
                     showIcon
                  />
               )}
            </Space>
         </div>
      </Card>
   );
};
