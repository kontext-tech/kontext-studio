import { CodeHighlighter } from "@ant-design/x";
import {
   CheckOutlined,
   CloseOutlined,
   LoadingOutlined,
   RightOutlined
} from "@kontext-tech/icons";
import type { DescriptionsProps } from "antd";
import type { ChatMessageSegment, ChatToolCallSegment } from "../types/chat";
import { getToolDisplayName, isDelegationTool } from "../utils/toolNameUtils";
import MarkdownRenderer, {
   type MarkdownImageBlobResolver
} from "./MarkdownRenderer";
import { Button, Descriptions, Typography, theme } from "antd";
import React, { useState } from "react";

interface ToolCallDisplayProps {
   toolCall: ChatToolCallSegment;
   allSegments: ChatMessageSegment[];
   resolveImageBlob?: MarkdownImageBlobResolver;
   renderNestedSegments?: (params: {
      nestedSegments: ChatMessageSegment[];
      allSegments: ChatMessageSegment[];
      toolCall: ChatToolCallSegment;
   }) => React.ReactNode;
}

const { Text } = Typography;
const { useToken } = theme;

interface ToolArgumentRow {
   key: string;
   value: string;
}

const formatMemberId = (targetId: unknown): string | null => {
   if (!targetId) return null;
   const str = String(targetId);
   if (!str.includes("-")) return str;

   const parts = str.split("-");
   const role = parts[parts.length - 1];
   const guidPrefix = parts[0].substring(0, 8);
   return `${role.toLowerCase()}(${guidPrefix.toLowerCase()})`;
};

const safeParseJson = (data: unknown) => {
   if (typeof data !== "string") return data;
   try {
      return JSON.parse(data);
   } catch {
      return data;
   }
};

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
   typeof value === "object" && value !== null && !Array.isArray(value);

const formatArgumentValue = (value: unknown): string => {
   if (value === null) {
      return "null";
   }

   if (value === undefined) {
      return "undefined";
   }

   if (typeof value === "string") {
      return value === "" ? '""' : value;
   }

   if (
      typeof value === "number" ||
      typeof value === "boolean" ||
      typeof value === "bigint"
   ) {
      return String(value);
   }

   return String(value);
};

const collectArgumentRows = (
   value: unknown,
   path: string | null = null
): ToolArgumentRow[] => {
   if (Array.isArray(value)) {
      if (value.length === 0) {
         return [
            {
               key: path ?? "value",
               value: "[]"
            }
         ];
      }

      return value.flatMap((item, index) =>
         collectArgumentRows(item, path ? `${path}[${index}]` : `[${index}]`)
      );
   }

   if (isPlainObject(value)) {
      const entries = Object.entries(value);

      if (entries.length === 0) {
         return [
            {
               key: path ?? "value",
               value: "{}"
            }
         ];
      }

      return entries.flatMap(([key, item]) =>
         collectArgumentRows(item, path ? `${path}.${key}` : key)
      );
   }

   return [
      {
         key: path ?? "value",
         value: formatArgumentValue(value)
      }
   ];
};

const getToolArgumentRows = (toolArgs: unknown): ToolArgumentRow[] => {
   const parsedArgs = safeParseJson(toolArgs);

   if (parsedArgs === null || parsedArgs === undefined) {
      return [];
   }

   return collectArgumentRows(parsedArgs);
};

const ToolCallDisplay: React.FC<ToolCallDisplayProps> = ({
   toolCall,
   allSegments,
   renderNestedSegments,
   resolveImageBlob
}) => {
   const { token } = useToken();
   const isDelegation = isDelegationTool(toolCall.toolName);
   const argumentRows = getToolArgumentRows(toolCall.toolArgs);
   const hasArguments = argumentRows.length > 0;
   const nestedSegments = allSegments.filter(
      (segment) => segment.parentId === toolCall.toolCallId
   );
   const hasNested = nestedSegments.length > 0;

   const [expanded, setExpanded] = useState(
      (isDelegation || hasNested) && toolCall.status !== "completed"
   );
   const [prevStatus, setPrevStatus] = useState(toolCall.status);

   if (toolCall.status !== prevStatus) {
      setPrevStatus(toolCall.status);
      if (toolCall.status === "completed") {
         setExpanded(false);
      }
   }

   let displayTitle = getToolDisplayName(toolCall.toolName);

   if (displayTitle === "Run Sub Agent" || displayTitle === "Run Sub Agents") {
      const toolArgs = safeParseJson(toolCall.toolArgs) as Record<
         string,
         unknown
      >;
      const targetId = (toolArgs?.member_id || toolArgs?.agent_id) as string;
      const formatted = formatMemberId(targetId);
      if (formatted) {
         displayTitle = `${displayTitle}: ${formatted}`;
      }
   }

   const getStatusIcon = (currentToolCall: ChatToolCallSegment) => {
      const { status, toolCallError, result } = currentToolCall;

      if (status === "error" || toolCallError) {
         return <CloseOutlined style={{ color: token.colorError }} />;
      }

      if (status === "completed" && result) {
         const parsedResult = safeParseJson(result);
         if (
            parsedResult &&
            typeof parsedResult === "object" &&
            parsedResult.success === false
         ) {
            return <CloseOutlined style={{ color: token.colorError }} />;
         }
      }

      switch (status) {
         case "started":
            return (
               <LoadingOutlined spin style={{ color: token.colorPrimary }} />
            );
         case "completed":
            return <CheckOutlined style={{ color: token.colorSuccess }} />;
         default:
            return null;
      }
   };

   const ellipsisStyle = {
      minWidth: 0,
      overflow: "hidden",
      textOverflow: "ellipsis",
      whiteSpace: "nowrap"
   } as const;

   const descriptionItems: DescriptionsProps["items"] = [
      hasArguments && {
         key: "args",
         label: "Arguments",
         children: (
            <div
               style={{
                  padding: "4px 0",
                  display: "flex",
                  flexDirection: "column",
                  gap: token.paddingXXS
               }}
            >
               {argumentRows.map(({ key, value }) => (
                  <div
                     key={`${key}:${value}`}
                     style={{
                        display: "grid",
                        gridTemplateColumns:
                           "minmax(120px, 32%) minmax(0, 1fr)",
                        gap: token.paddingXS,
                        alignItems: "center"
                     }}
                  >
                     <div
                        title={key}
                        style={{
                           ...ellipsisStyle,
                           color: token.colorTextSecondary,
                           fontFamily: token.fontFamilyCode
                        }}
                     >
                        {key}
                     </div>
                     <div
                        title={value}
                        style={{
                           ...ellipsisStyle,
                           fontFamily: token.fontFamilyCode
                        }}
                     >
                        {value}
                     </div>
                  </div>
               ))}
            </div>
         )
      },
      toolCall.result && {
         key: "result",
         label: "Result",
         children: isDelegation ? (
            <div style={{ padding: "4px 0" }}>
               <MarkdownRenderer
                  content={String(toolCall.result)}
                  resolveImageBlob={resolveImageBlob}
               />
            </div>
         ) : (
            <CodeHighlighter lang="json">
               {JSON.stringify(safeParseJson(toolCall.result), null, 2)}
            </CodeHighlighter>
         )
      },
      toolCall.toolCallError && {
         key: "error",
         label: "Error",
         children: (
            <Typography.Text type="danger">
               {toolCall.toolCallError}
            </Typography.Text>
         )
      }
   ].filter(Boolean) as DescriptionsProps["items"];

   return (
      <div
         style={{
            marginBottom: token.marginXS,
            marginTop: token.marginXS
         }}
      >
         <div
            style={{
               display: "flex",
               alignItems: "center",
               justifyContent: "space-between",
               gap: token.paddingXXS,
               padding: `${token.paddingXXS}px ${token.paddingXS}px`,
               backgroundColor: token.colorFillTertiary,
               borderRadius: token.borderRadiusSM,
               fontSize: token.fontSizeSM
            }}
         >
            <div
               style={{
                  display: "flex",
                  alignItems: "center",
                  gap: token.paddingXXS,
                  minWidth: 0,
                  flex: 1
               }}
            >
               {getStatusIcon(toolCall)}
               <Text
                  strong
                  title={displayTitle}
                  style={{
                     fontSize: token.fontSizeSM,
                     minWidth: 0,
                     overflow: "hidden",
                     textOverflow: "ellipsis",
                     whiteSpace: "nowrap"
                  }}
               >
                  {displayTitle}
               </Text>
            </div>
            {(hasArguments || toolCall.result || hasNested) && (
               <Button
                  type="text"
                  size="small"
                  icon={
                     <RightOutlined
                        rotate={expanded ? 90 : 0}
                        style={{ fontSize: "10px" }}
                     />
                  }
                  onClick={() => setExpanded(!expanded)}
                  style={{
                     height: "20px",
                     padding: "0 4px",
                     color: token.colorTextSecondary
                  }}
               />
            )}
         </div>
         {expanded && (
            <div
               style={{
                  marginTop: 4,
                  padding: "4px 8px",
                  backgroundColor: token.colorFillQuaternary,
                  borderRadius: token.borderRadiusSM,
                  fontSize: "12px",
                  overflow: "auto",
                  maxHeight: "max-content"
               }}
            >
               {hasNested && (
                  <div style={{ marginBottom: token.marginXS }}>
                     {renderNestedSegments?.({
                        nestedSegments,
                        allSegments,
                        toolCall
                     })}
                  </div>
               )}

               <Descriptions
                  column={1}
                  size="small"
                  layout="vertical"
                  items={descriptionItems}
               />
            </div>
         )}
      </div>
   );
};

export default ToolCallDisplay;
