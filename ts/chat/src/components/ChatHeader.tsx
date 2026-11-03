import { useUiApp } from "@kontext-tech/ui";
import {
   DeleteOutlined,
   EditOutlined,
   HistoryOutlined,
   MoreOutlined,
   PanelLeftCloseOutlined,
   PanelLeftOpenOutlined
} from "@kontext-tech/icons";
import { type ChatSessionModel } from "@kontext-tech/schema";
import {
   Button,
   Dropdown,
   Flex,
   Input,
   Typography,
   type MenuProps,
   theme
} from "antd";
import React, { useState } from "react";

const { Title } = Typography;
const { useToken } = theme;

export interface ChatHeaderProps {
   displaySessionName: string;
   onSaveSessionName?: (name: string) => Promise<void> | void;
   onDeleteSession?: (sessionId: string) => Promise<boolean> | void;
   onOpenSessions?: () => void;
   isSidebarOpen: boolean;
   setSidebarOpen: (open: boolean) => void;
   hasArtifacts: boolean;
   chatSession: ChatSessionModel | null;
   messagesCount: number;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
   displaySessionName,
   onSaveSessionName,
   onDeleteSession,
   onOpenSessions,
   isSidebarOpen,
   setSidebarOpen,
   hasArtifacts,
   chatSession,
   messagesCount
}) => {
   const { token } = useToken();
   const { modal } = useUiApp();
   const [isEditing, setIsEditing] = useState(false);
   const [localName, setLocalName] = useState(displaySessionName);
   const [isSaving, setIsSaving] = useState(false);

   const startEdit = () => {
      setLocalName(displaySessionName);
      setIsEditing(true);
   };

   const saveName = async () => {
      const trimmed = localName.trim();
      if (!trimmed) {
         setIsEditing(false);
         return;
      }

      if (onSaveSessionName) {
         try {
            setIsSaving(true);
            await onSaveSessionName(trimmed);
         } catch (err) {
            console.error("Failed to save session name", err);
         } finally {
            setIsSaving(false);
         }
      }

      setIsEditing(false);
   };

   const handleDelete = () => {
      if (!chatSession || !onDeleteSession) return;

      modal.confirm({
         title: "Delete Chat",
         content: `Are you sure you want to delete "${displaySessionName}"? This action cannot be undone.`,
         okText: "Delete",
         okType: "danger",
         cancelText: "Cancel",
         onOk: async () => {
            try {
               const result = await onDeleteSession(chatSession.id);
               if (result === false) {
                  modal.error({ title: "Failed to delete chat" });
               }
            } catch (err) {
               console.error("Failed to delete session", err);
               modal.error({ title: "Failed to delete chat" });
            }
         }
      });
   };

   const renderActions = () => {
      if (!chatSession) return null;

      const menuItems: MenuProps["items"] = [
         {
            key: "sessions",
            label: "All chats",
            icon: <HistoryOutlined style={{ fontSize: "14px" }} />,
            onClick: onOpenSessions
         }
      ];

      if (onDeleteSession) {
         menuItems.push({
            key: "delete",
            label: "Delete chat",
            icon: <DeleteOutlined />,
            danger: true,
            onClick: handleDelete
         });
      }

      return (
         <Flex align="center" gap="small">
            <Dropdown menu={{ items: menuItems }} trigger={["click"]}>
               <Button type="text" icon={<MoreOutlined />} size="small" />
            </Dropdown>
         </Flex>
      );
   };

   return (
      <div
         style={{
            minHeight: "var(--app-chrome-row-height, 56px)",
            padding: "0 var(--app-page-content-padding, 24px)",
            borderBottom: `1px solid ${token.colorBorder}`,
            background: token.colorBgContainer,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: token.paddingSM,
            flexShrink: 0
         }}
      >
         <Flex align="center" gap="small" style={{ minWidth: 0, flex: 1 }}>
            {hasArtifacts && messagesCount > 0 && (
               <Button
                  type="text"
                  icon={
                     isSidebarOpen ? (
                        <PanelLeftCloseOutlined />
                     ) : (
                        <PanelLeftOpenOutlined />
                     )
                  }
                  onClick={() => setSidebarOpen(!isSidebarOpen)}
                  size="small"
                  title={isSidebarOpen ? "Hide artifacts" : "Show artifacts"}
               />
            )}
            {isEditing ? (
               <Input
                  value={localName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                     setLocalName(e.target.value)
                  }
                  onPressEnter={saveName}
                  onBlur={saveName}
                  size="small"
                  style={{ width: "100%", maxWidth: 320 }}
                  autoFocus
                  disabled={isSaving}
               />
            ) : (
               <Flex align="center" gap="small" style={{ minWidth: 0 }}>
                  <Title
                     level={5}
                     style={{ margin: 0 }}
                     ellipsis={{ tooltip: displaySessionName }}
                  >
                     {displaySessionName}
                  </Title>
                  {chatSession && onSaveSessionName && (
                     <Button
                        type="text"
                        icon={<EditOutlined />}
                        onClick={startEdit}
                        size="small"
                     />
                  )}
               </Flex>
            )}
         </Flex>
         {renderActions()}
      </div>
   );
};

export default ChatHeader;
