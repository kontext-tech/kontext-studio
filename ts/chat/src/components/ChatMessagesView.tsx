import { LoadingSpinner } from "@kontext-labs/ui";
import React from "react";
import type { ChatMessage } from "../types/chat";
import ChatMessageList from "./ChatMessageList";
import ChatWelcome from "./ChatWelcome";
import type { MarkdownImageBlobResolver } from "./MarkdownRenderer";

export interface ChatMessagesViewProps {
   messages: ChatMessage[];
   onPromptClick: (msg: string) => void;
   isMessagesLoading?: boolean;
   ownerId?: string;
   resolveImageBlob?: MarkdownImageBlobResolver;
   renderAssistantFooterActions?: (
      message: ChatMessage,
      context: { isLast: boolean }
   ) => React.ReactNode;
}

const ChatMessagesView: React.FC<ChatMessagesViewProps> = ({
   messages,
   onPromptClick,
   isMessagesLoading,
   ownerId,
   resolveImageBlob,
   renderAssistantFooterActions
}) => {
   return (
      <div
         className="chat-messages-container"
         style={{
            flex: 1,
            padding: "16px 24px",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            overflowY: "auto",
            overflowX: "hidden"
         }}
      >
         {isMessagesLoading && messages.length === 0 ? (
            <div
               style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  height: 240
               }}
            >
               <LoadingSpinner />
            </div>
         ) : (
            <>
               <ChatMessageList
                  messages={messages}
                  ownerId={ownerId}
                  resolveImageBlob={resolveImageBlob}
                  renderAssistantFooterActions={renderAssistantFooterActions}
               />
               {messages.length <= 0 && (
                  <div
                     style={{
                        maxWidth: "800px",
                        margin: "0 auto",
                        width: "100%"
                     }}
                  >
                     <ChatWelcome
                        onPromptClick={onPromptClick}
                        showPrompts={false}
                     />
                  </div>
               )}
            </>
         )}
      </div>
   );
};

export default ChatMessagesView;
