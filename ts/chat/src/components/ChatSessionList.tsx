import { DeleteOutlined } from "@kontext-labs/icons";
import { UserAvatarById } from "@kontext-labs/identity";
import { type ChatSessionModel, type ProjectModel } from "@kontext-labs/schema";
import { LoadingSpinner } from "@kontext-labs/ui";
import { Button, Empty, Flex, Space, Tooltip, Typography, theme } from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import React from "react";

const { Text } = Typography;
dayjs.extend(relativeTime);

export interface ChatSessionListProps {
   sessions: ChatSessionModel[];
   onOpen: (session: ChatSessionModel) => void;
   onDelete?: (session: ChatSessionModel) => void;
   projects?: ProjectModel[];
   isLoading?: boolean;
   emptyDescription?: string;
   showProjectName?: boolean;
   showAvatar?: boolean;
   showAgentInfo?: boolean;
}

const ChatSessionList: React.FC<ChatSessionListProps> = ({
   sessions,
   onOpen,
   onDelete,
   projects = [],
   isLoading = false,
   emptyDescription = "No recent chats found",
   showProjectName = true,
   showAvatar = false,
   showAgentInfo = false
}) => {
   const { token } = theme.useToken();

   if (isLoading) {
      return <LoadingSpinner style={{ padding: "40px" }} />;
   }

   if (sessions.length === 0) {
      return <Empty description={emptyDescription} />;
   }

   return (
      <Flex vertical gap="small">
         {sessions.map((session) => {
            const project = projects.find((p) => p.id === session.projectId);
            return (
               <Flex
                  key={session.id}
                  align="center"
                  justify="space-between"
                  style={{
                     padding: "12px 16px",
                     cursor: "pointer",
                     borderRadius: token.borderRadiusLG,
                     transition: "background 0.3s"
                  }}
                  className="hover-bg"
                  onClick={() => onOpen(session)}
                  onMouseEnter={(e) =>
                     (e.currentTarget.style.backgroundColor =
                        token.colorFillAlter)
                  }
                  onMouseLeave={(e) =>
                     (e.currentTarget.style.backgroundColor = "transparent")
                  }
               >
                  <Flex align="center" gap="middle">
                     {showAvatar && (
                        <UserAvatarById userId={session.ownerId || ""} />
                     )}
                     <Flex vertical>
                        <Space>
                           <Text strong>
                              {session.sessionName || "Untitled Chat"}
                           </Text>
                           {showAgentInfo && (
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                 Assistant
                              </Text>
                           )}
                        </Space>
                        <Text type="secondary" style={{ fontSize: "12px" }}>
                           {showProjectName && (
                              <>
                                 {project?.projectName || "Unknown Project"}{" "}
                                 •{" "}
                              </>
                           )}
                           {dayjs(
                              session.dateModified || session.dateCreated
                           ).fromNow()}
                        </Text>
                     </Flex>
                  </Flex>
                  <Flex gap="small">
                     {!onDelete && (
                        <Button
                           type="link"
                           onClick={(e) => {
                              e.stopPropagation();
                              onOpen(session);
                           }}
                        >
                           Open
                        </Button>
                     )}
                     {onDelete && (
                        <Tooltip title="Delete Chat">
                           <Button
                              type="text"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={(e) => {
                                 e.stopPropagation();
                                 onDelete(session);
                              }}
                           />
                        </Tooltip>
                     )}
                  </Flex>
               </Flex>
            );
         })}
      </Flex>
   );
};

export default ChatSessionList;
