import { Bubble } from "@ant-design/x";
import { UserAvatar, UserAvatarById, useUser } from "@kontext-tech/identity";
import { CopyOutlined } from "@kontext-tech/icons";
import { RobotAvatar, useUiApp } from "@kontext-tech/ui";
import { Button, Flex } from "antd";
import React from "react";
import type { ChatMessage } from "../types/chat";
import { isTextSegment } from "../types/chat";
import type { MarkdownImageBlobResolver } from "./MarkdownRenderer";
import MessageSegmentsDisplay from "./MessageSegmentsDisplay";

export interface ChatMessageListProps {
   messages: ChatMessage[];
   ownerId?: string;
   resolveImageBlob?: MarkdownImageBlobResolver;
   renderAssistantFooterActions?: (
      message: ChatMessage,
      context: { isLast: boolean }
   ) => React.ReactNode;
}

const ChatMessageList: React.FC<ChatMessageListProps> = ({
   messages,
   ownerId,
   resolveImageBlob,
   renderAssistantFooterActions
}) => {
   const { user } = useUser();
   const { message: messageApi } = useUiApp();
   const isOwner = !ownerId || !user?.id || ownerId === user.id;

   const handleCopy = async (message: ChatMessage) => {
      try {
         let contentToCopy = "";

         message.segments.forEach((segment) => {
            if (typeof segment === "string") {
               contentToCopy += segment;
            }
         });

         await navigator.clipboard.writeText(contentToCopy);
         messageApi.success("Copied to clipboard");
      } catch {
         messageApi.error("Failed to copy");
      }
   };

   const bubbleItems = messages.map((message, index) => {
      const isLast = index === messages.length - 1;
      const hasVisibleAssistantText =
         message.type === "assistant" &&
         message.status === "completed" &&
         message.segments.some((segment) => {
            if (isTextSegment(segment)) {
               return segment.content?.trim() !== "";
            }
            return false;
         });
      const footerActions = hasVisibleAssistantText
         ? renderAssistantFooterActions?.(message, { isLast })
         : null;

      return {
         key: message.id,
         role: message.type,
         variant: "filled" as const,
         content: (
            <MessageSegmentsDisplay
               segments={message.segments}
               messageType={message.type}
               status={message.status}
               isLast={isLast}
               resolveImageBlob={resolveImageBlob}
            />
         ),
         placement: "start" as const,
         avatar:
            message.type === "user" ? (
               isOwner ? (
                  <UserAvatar user={user!} />
               ) : (
                  <UserAvatarById userId={ownerId!} />
               )
            ) : (
               <RobotAvatar icon="SparklesOutlined" />
            ),
         loading: message.status === "loading",
         footer: hasVisibleAssistantText ? (
            <Flex justify="end" align="center" gap={4} style={{ marginTop: 8 }}>
               {footerActions}
               <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => handleCopy(message)}
                  title="Copy message"
               >
                  Copy
               </Button>
            </Flex>
         ) : undefined
      };
   });

   return (
      <div
         style={{
            maxWidth: "800px",
            margin: "0 auto",
            width: "100%",
            flex: 1,
            display: "flex",
            flexDirection: "column",
            minHeight: 0
         }}
      >
         <Bubble.List
            items={bubbleItems}
            autoScroll={true}
            style={{ flex: 1 }}
            styles={{
               scroll: {
                  padding: "0 0 24px 0"
               }
            }}
         />
      </div>
   );
};

export default ChatMessageList;
