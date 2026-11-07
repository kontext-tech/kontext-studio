import type {
   ChatErrorSegment,
   ChatMessage,
   ChatMessageSegment,
   ChatMessageSegmentType,
   ChatMessageStatus,
   ChatMessageType,
   ChatObjectSegment,
   ChatReasoningSegment,
   ChatTextSegment,
   ChatToolCallSegment,
   ToolCallState
} from "@kontext-tech/schema";

/**
 * Re-export chat message types from schemas for use in frontend
 * These are now the single source of truth, defined in ts/schema/src/ai/
 */

export type {
   ChatErrorSegment,
   ChatMessage,
   ChatMessageSegment,
   ChatMessageSegmentType,
   ChatMessageStatus,
   ChatMessageType,
   ChatObjectSegment,
   ChatReasoningSegment,
   ChatToolCallSegment,
   ToolCallState
};

/**
 * Convenience aliases for backward compatibility
 */
export type ChatMessageRole = ChatMessageType;

// Type guards for segments with discriminated union pattern
export const isTextSegment = (
   segment: ChatMessageSegment
): segment is ChatTextSegment =>
   typeof segment === "object" &&
   segment !== null &&
   (segment as { segmentType: string }).segmentType === "text";

export const isToolCallSegment = (
   segment: ChatMessageSegment
): segment is ChatToolCallSegment =>
   typeof segment === "object" &&
   segment !== null &&
   (segment as { segmentType: string }).segmentType === "tool_call";

export const isChatErrorSegment = (
   segment: ChatMessageSegment
): segment is ChatErrorSegment & { segmentType: "error" } =>
   typeof segment === "object" &&
   segment !== null &&
   (segment as { segmentType: string }).segmentType === "error";

export const isReasoningSegment = (
   segment: ChatMessageSegment
): segment is ChatReasoningSegment & { segmentType: "reasoning" } =>
   typeof segment === "object" &&
   segment !== null &&
   (segment as { segmentType: string }).segmentType === "reasoning";
