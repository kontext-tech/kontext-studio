import { Think } from "@ant-design/x";
import { LoadingOutlined, SparklesOutlined } from "@kontext-labs/icons";
import { Alert, Flex, theme } from "antd";
import React, { useEffect, useRef } from "react";
import { useChatSessionStore } from "../stores/chatSessionStore";
import type {
   ChatMessageRole,
   ChatMessageSegment,
   ChatMessageStatus
} from "../types/chat";
import {
   isChatErrorSegment,
   isReasoningSegment,
   isTextSegment,
   isToolCallSegment
} from "../types/chat";
import MarkdownRenderer, {
   type MarkdownImageBlobResolver
} from "./MarkdownRenderer";
import ToolCallDisplay from "./ToolCallDisplay";

export interface MessageSegmentsDisplayProps {
   segments: ChatMessageSegment[];
   allSegments?: ChatMessageSegment[];
   messageType?: ChatMessageRole;
   status?: ChatMessageStatus;
   isLast?: boolean;
   nested?: boolean;
   resolveImageBlob?: MarkdownImageBlobResolver;
}

const MessageSegmentsDisplay: React.FC<MessageSegmentsDisplayProps> = ({
   segments,
   allSegments = segments,
   messageType = "assistant",
   status,
   isLast = false,
   nested = false,
   resolveImageBlob
}) => {
   const { token } = theme.useToken();
   const thinkingScrollRef = useRef<HTMLDivElement>(null);
   const isLoading = useChatSessionStore((state) => state.isLoading);

   const visibleSegments = nested
      ? segments
      : segments.filter((segment) => !segment.parentId);
   const reasoningSegments = visibleSegments.filter(isReasoningSegment);
   const mainSegments = visibleSegments.filter(
      (segment) => !isReasoningSegment(segment)
   );
   const showThinking = reasoningSegments.length > 0;
   const combinedReasoningContent = reasoningSegments
      .map((segment) => segment.content || "")
      .join("");

   useEffect(() => {
      if (showThinking && thinkingScrollRef.current) {
         thinkingScrollRef.current.scrollTop =
            thinkingScrollRef.current.scrollHeight;
      }
   }, [showThinking, combinedReasoningContent]);

   const thinkingElement = showThinking ? (
      <Think
         key="reasoning-group"
         style={{ marginBottom: nested ? 8 : 16 }}
         icon={<SparklesOutlined />}
         title={status === "completed" ? "Reasoning" : "Thinking..."}
         loading={status !== "completed"}
      >
         <div
            ref={thinkingScrollRef}
            style={{
               whiteSpace: "pre-wrap",
               opacity: 0.8,
               maxHeight: nested ? "120px" : "180px",
               overflowY: "auto"
            }}
         >
            {combinedReasoningContent}
         </div>
      </Think>
   ) : null;

   const shouldShowWorking =
      (status === "streaming" ||
         status === "loading" ||
         (isLoading && isLast)) &&
      messageType === "assistant";

   const renderSegments: React.ReactNode[] = [];
   let currentTextBuffer = "";

   const flushTextBuffer = (key: string) => {
      if (!currentTextBuffer) {
         return;
      }

      if (messageType === "user") {
         renderSegments.push(<span key={key}>{currentTextBuffer}</span>);
      } else {
         renderSegments.push(
            <MarkdownRenderer
               key={key}
               content={currentTextBuffer}
               resolveImageBlob={resolveImageBlob}
            />
         );
      }

      currentTextBuffer = "";
   };

   mainSegments.forEach((segment, index) => {
      if (isTextSegment(segment) || typeof segment === "string") {
         const content =
            typeof segment === "string" ? segment : segment.content || "";
         currentTextBuffer += content;
         return;
      }

      flushTextBuffer(`combined-text-${index}`);

      if (isToolCallSegment(segment)) {
         renderSegments.push(
            <ToolCallDisplay
               key={`toolcall-${segment.toolCallId}`}
               toolCall={segment}
               allSegments={allSegments}
               resolveImageBlob={resolveImageBlob}
               renderNestedSegments={({
                  nestedSegments,
                  allSegments: nextAllSegments,
                  toolCall
               }) => (
                  <MessageSegmentsDisplay
                     segments={nestedSegments}
                     allSegments={nextAllSegments}
                     status={
                        toolCall.status === "started"
                           ? "streaming"
                           : "completed"
                     }
                     messageType="assistant"
                     nested={true}
                     resolveImageBlob={resolveImageBlob}
                  />
               )}
            />
         );
      } else if (isChatErrorSegment(segment)) {
         renderSegments.push(
            <div key={`error-${index}`} style={{ marginTop: 8 }}>
               <Alert
                  type="error"
                  description={String(segment.errorDetails)}
                  showIcon
                  banner
               />
            </div>
         );
      }
   });

   flushTextBuffer("combined-text-final");

   return (
      <>
         {thinkingElement}
         {renderSegments}
         {shouldShowWorking && (
            <Flex justify="start" style={{ marginTop: 8 }} gap="small">
               <LoadingOutlined spin style={{ color: token.colorPrimary }} />
               <span>Working...</span>
            </Flex>
         )}
      </>
   );
};

export default MessageSegmentsDisplay;
