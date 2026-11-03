import { z } from "zod";
import { ArtifactActionSchema } from "./actions";
import { ChatSessionArtifactModelSchema } from "./chat-session";
import {
   ExternalExecutionRequirementSchema,
   ToolCallResultSchema
} from "./tool-results";
import { ArtifactEventKindSchema, ArtifactTypeSchema } from "./types";

/**
 * AI/ML Event and Request/Response schemas for chat streaming and AI services.
 */

// RunEvent: the neutral wire vocabulary for agent run events.
//
// Contract note: these are behavior-named events any harness adapter may emit.
// Adapter-emitted today:
//   RunContent, RunIntermediateContent, RunCompleted, RunError, RunCancelled,
//   RunPaused, RunContinued, ToolCallStarted, ToolCallCompleted, CustomEvent
// and (optionally) RunStarted and the Reasoning* family; ArtifactEvent carries
// artifact lifecycle payloads. CustomEvent may wrap harness-internal events the
// client policy declines to surface as structured events; consumers must
// ignore unknown/unhandled values.
export const RunEventSchema = z.enum([
   // Core run lifecycle events
   "RunStarted",
   "RunContent",
   "RunIntermediateContent",
   "RunCompleted",
   "RunError",
   "RunCancelled",
   "RunPaused",
   "RunContinued",

   // Tool interaction events
   "ToolCallStarted",
   "ToolCallCompleted",

   // Reasoning events
   "ReasoningStarted",
   "ReasoningStep",
   "ReasoningCompleted",

   "ArtifactEvent",

   // Custom events
   "CustomEvent"
]);

export type RunEvent = z.infer<typeof RunEventSchema>;
// Export enum constants directly for runtime usage - TypeScript will infer the type
export const RunEvent = RunEventSchema.enum;

// Tool call model
export const ToolCallSchema = z.object({
   toolCallId: z
      .string()
      .nullable()
      .optional()
      .describe("Unique tool call identifier"),
   toolName: z.string().nullable().optional().describe("Name of the tool"),
   toolArgs: z
      .record(z.string(), z.any())
      .nullable()
      .optional()
      .describe("Arguments passed to the tool"),
   toolCallError: z
      .string()
      .nullable()
      .optional()
      .describe("Error message if the tool call failed"),
   result: ToolCallResultSchema.nullish().describe(
      "Result of the tool execution"
   )
});

export type ToolCall = z.infer<typeof ToolCallSchema>;

// Event data models for different event types
export const RunStartedEventDataSchema = z.object({
   model: z.string().nullable().optional().describe("Model name"),
   modelSelectionId: z
      .string()
      .nullable()
      .optional()
      .describe("Executable model selection"),
   canonicalModelId: z
      .string()
      .nullable()
      .optional()
      .describe("Canonical model identifier"),
   adapterType: z.string().nullable().optional().describe("Model adapter type"),
   connectionKind: z.string().nullable().optional().describe("Connection kind"),
   sessionId: z.string().nullable().optional().describe("Chat session ID")
});
export type RunStartedEventData = z.infer<typeof RunStartedEventDataSchema>;

export const RunContentEventDataSchema = z.object({
   contentType: z.string().nullable().optional().describe("Type of content")
});
export type RunContentEventData = z.infer<typeof RunContentEventDataSchema>;

export const RunCompletedEventDataSchema = z.object({
   contentType: z.string().nullable().optional().describe("Type of content")
});
export type RunCompletedEventData = z.infer<typeof RunCompletedEventDataSchema>;

export const RunPausedEventDataSchema = z.object({
   model: z.string().nullish().describe("Model name"),
   runId: z.string().nullish().describe("Run identifier"),
   platformRunId: z
      .guid()
      .nullish()
      .describe("Platform execution run identifier"),
   activeRequirements: z
      .array(ExternalExecutionRequirementSchema)
      .nullish()
      .describe("Active requirements for resuming the run"),
   toolCalls: z
      .array(ToolCallSchema)
      .nullish()
      .describe("Tool calls that require external execution")
});
export type RunPausedEventData = z.infer<typeof RunPausedEventDataSchema>;

export const ToolCallStartedEventDataSchema = z.object({
   tool: ToolCallSchema.nullable().optional().describe("Tool information")
});
export type ToolCallStartedEventData = z.infer<
   typeof ToolCallStartedEventDataSchema
>;

export const ToolCallCompletedEventDataSchema = z.object({
   tool: ToolCallSchema.nullable().optional().describe("Tool information")
});
export type ToolCallCompletedEventData = z.infer<
   typeof ToolCallCompletedEventDataSchema
>;

export const ReasoningEventDataSchema = z.object({
   content: z.string().nullable().optional().describe("Reasoning content")
});
export type ReasoningEventData = z.infer<typeof ReasoningEventDataSchema>;

export const ArtifactSchema = ChatSessionArtifactModelSchema.describe(
   "Durable chat session artifact descriptor"
);

export type Artifact = z.infer<typeof ArtifactSchema>;

export const ArtifactEventDataSchema = z.object({
   kind: ArtifactEventKindSchema.describe("Artifact lifecycle kind"),
   artifact: ChatSessionArtifactModelSchema.describe("Artifact descriptor"),
   actions: z.array(ArtifactActionSchema).optional(),
   sourceToolCallId: z
      .string()
      .nullable()
      .optional()
      .describe("Tool call identifier that produced the artifact update")
});

export type ArtifactEventData = z.infer<typeof ArtifactEventDataSchema>;

// Union type for all event data
export const EventDataSchema = z.union([
   RunStartedEventDataSchema,
   RunContentEventDataSchema,
   RunCompletedEventDataSchema,
   RunPausedEventDataSchema,
   ToolCallStartedEventDataSchema,
   ToolCallCompletedEventDataSchema,
   ReasoningEventDataSchema,
   ArtifactEventDataSchema
]);

export type EventData = z.infer<typeof EventDataSchema>;

// Simple run event model for streaming

export const SimpleRunEventSchema = z.object({
   eventType: RunEventSchema.describe("Event type identifier"),
   content: z.string().nullable().optional().describe("Event content"),
   eventId: z
      .string()
      .nullable()
      .optional()
      .describe("Unique event identifier"),
   eventData: EventDataSchema.nullable()
      .optional()
      .describe("Event-specific data"),
   done: z
      .boolean()
      .nullable()
      .optional()
      .describe("Whether streaming is complete"),
   errorDetails: z.string().nullable().optional().describe("Error details"),
   reasoning: z.string().nullable().optional().describe("Reasoning content")
});

export type SimpleRunEvent = z.infer<typeof SimpleRunEventSchema>;

// Stream-level validator. Validates the event envelope against
// SimpleRunEventSchema, then validates/normalizes `eventData` by `eventType`.
// `eventData` payloads whose event type has no registered data schema pass
// through untouched, which keeps the stream forward-compatible with adapters
// and harnesses that attach richer payloads than this contract knows about.
const simpleRunEventDataSchemas: Partial<Record<RunEvent, z.ZodType>> = {
   RunStarted: RunStartedEventDataSchema,
   RunContent: RunContentEventDataSchema,
   RunCompleted: RunCompletedEventDataSchema,
   RunPaused: RunPausedEventDataSchema,
   ToolCallStarted: ToolCallStartedEventDataSchema,
   ToolCallCompleted: ToolCallCompletedEventDataSchema,
   ReasoningStarted: ReasoningEventDataSchema,
   ReasoningStep: ReasoningEventDataSchema,
   ReasoningCompleted: ReasoningEventDataSchema,
   ArtifactEvent: ArtifactEventDataSchema
};

export const SimpleRunEventStreamSchema = SimpleRunEventSchema.extend({
   eventData: z.unknown().nullish()
}).transform((value, ctx) => {
   const dataSchema = simpleRunEventDataSchemas[value.eventType];
   if (!dataSchema || value.eventData == null) {
      return value;
   }

   const parsed = dataSchema.safeParse(value.eventData);
   if (!parsed.success) {
      for (const issue of parsed.error.issues) {
         ctx.addIssue({
            code: "custom",
            message: issue.message,
            path: ["eventData", ...issue.path]
         });
      }
      return z.NEVER;
   }

   return { ...value, eventData: parsed.data };
}) as z.ZodType<SimpleRunEvent, unknown>;

// Chat Message enums and models
export const ToolCallStatusSchema = z.enum(["started", "completed", "error"]);

export type ToolCallStatus = z.infer<typeof ToolCallStatusSchema>;
// Export enum constants directly for runtime usage
export const ToolCallStatus = ToolCallStatusSchema.enum;

// Tool call state extending ToolCall with status tracking
export const ToolCallStateSchema = ToolCallSchema.extend({
   status: ToolCallStatusSchema.default("completed").describe(
      "Status of the tool call"
   ),
   error: z
      .string()
      .nullable()
      .optional()
      .describe("Error message if tool call failed")
});

export type ToolCallState = z.infer<typeof ToolCallStateSchema>;

// Chat message type enum
export const ChatMessageTypeSchema = z.enum(["user", "assistant", "system"]);

export type ChatMessageType = z.infer<typeof ChatMessageTypeSchema>;
// Export enum constants directly for runtime usage
export const ChatMessageType = ChatMessageTypeSchema.enum;

// Chat message status enum
export const ChatMessageStatusSchema = z.enum([
   "loading",
   "streaming",
   "completed",
   "error"
]);

export type ChatMessageStatus = z.infer<typeof ChatMessageStatusSchema>;
// Export enum constants directly for runtime usage
export const ChatMessageStatus = ChatMessageStatusSchema.enum;

// Chat message segment type discriminator enum
// Used to discriminate between different segment types in the segments array
export const ChatMessageSegmentTypeSchema = z.enum([
   "text",
   "tool_call",
   "error",
   "object",
   "reasoning"
]);

export type ChatMessageSegmentType = z.infer<
   typeof ChatMessageSegmentTypeSchema
>;
// Export enum constants directly for runtime usage
export const ChatMessageSegmentType = ChatMessageSegmentTypeSchema.enum;

// Chat message segment types with discriminators
// Following the notebook block pattern: each segment type has a discriminator field

// Base segment fields common to all
export const ChatBaseSegmentSchema = z.object({
   cid: z.string().nullish().describe("Unique segment instance identifier"),
   parentId: z
      .string()
      .nullish()
      .describe("Parent tool call identifier for nested segments")
});

// Text segment
export const ChatTextSegmentSchema = ChatBaseSegmentSchema.extend({
   segmentType: z
      .literal("text")
      .default("text")
      .describe("Segment type discriminator"),
   content: z.string().describe("Text content")
});

export type ChatTextSegment = z.infer<typeof ChatTextSegmentSchema>;

// Error segment
export const ChatErrorSegmentSchema = ChatBaseSegmentSchema.extend({
   segmentType: z
      .literal("error")
      .default("error")
      .describe("Segment type discriminator"),
   errorDetails: z.string().describe("Error details to display")
});

export type ChatErrorSegment = z.infer<typeof ChatErrorSegmentSchema>;

// Reasoning segment
export const ChatReasoningSegmentSchema = ChatBaseSegmentSchema.extend({
   segmentType: z
      .literal("reasoning")
      .default("reasoning")
      .describe("Segment type discriminator"),
   content: z.string().describe("Reasoning content")
});

export type ChatReasoningSegment = z.infer<typeof ChatReasoningSegmentSchema>;

// Generic object segment
export const ChatObjectSegmentSchema = ChatBaseSegmentSchema.extend({
   segmentType: z
      .literal("object")
      .default("object")
      .describe("Segment type discriminator"),
   data: z.record(z.string(), z.any()).describe("Generic object data")
});

export type ChatObjectSegment = z.infer<typeof ChatObjectSegmentSchema>;

// Tool call segment
export const ChatToolCallSegmentSchema = ToolCallStateSchema.merge(
   ChatBaseSegmentSchema
).extend({
   segmentType: z
      .literal("tool_call")
      .default("tool_call")
      .describe("Segment type discriminator")
});

export type ChatToolCallSegment = ToolCallState &
   z.infer<typeof ChatBaseSegmentSchema> & {
      segmentType: "tool_call";
   };

// Chat message segments union using discriminated union
// This generates proper Pydantic models without RootModel wrappers
export const ChatMessageSegmentSchema = z.discriminatedUnion("segmentType", [
   ChatTextSegmentSchema,
   ChatToolCallSegmentSchema,
   ChatErrorSegmentSchema,
   ChatReasoningSegmentSchema,
   ChatObjectSegmentSchema
]);

export type ChatMessageSegment = z.infer<typeof ChatMessageSegmentSchema>;

// Chat message model
export const ChatMessageSchema = z.object({
   id: z.string().describe("Unique message identifier"),
   type: ChatMessageTypeSchema.describe("Message role/type"),
   status: ChatMessageStatusSchema.describe("Current status of the message"),
   segments: z
      .array(ChatMessageSegmentSchema)
      .describe(
         "Message segments - text, tool calls, errors, artifacts, or generic objects"
      ),
   error: z
      .string()
      .nullable()
      .optional()
      .describe("Error message if message failed")
});

export type ChatMessage = z.infer<typeof ChatMessageSchema>;

// AI Chat request/response models
export const ChatRequestSchema = z.object({
   projectId: z.guid().describe("The project ID"),
   sessionId: z.guid().describe("The chat session ID"),
   querySessionId: z
      .guid()
      .optional()
      .nullable()
      .describe("Optional query session ID to use for SQL tools"),
   message: z.string().describe("The message to send to the AI"),
   toolOutputs: z
      .array(ToolCallSchema)
      .optional()
      .nullable()
      .describe("Optional tool outputs for resuming a paused run"),
   runId: z
      .string()
      .optional()
      .nullable()
      .describe("Optional run ID to resume a specific paused run")
});

export type ChatRequest = z.infer<typeof ChatRequestSchema>;

// Token usage statistics models
export const TokenUsageStatsModelSchema = z.object({
   month: z.string().describe("Month in YYYY-MM format"),
   modelSelectionId: z
      .string()
      .optional()
      .nullable()
      .describe("Executable model selection"),
   canonicalModelId: z
      .string()
      .optional()
      .nullable()
      .describe("Canonical model identifier"),
   modelDisplayName: z
      .string()
      .optional()
      .nullable()
      .describe("Human-readable model name resolved at aggregation time"),
   inboundTokens: z.number().int().describe("Total inbound tokens"),
   outboundTokens: z.number().int().describe("Total outbound tokens"),
   totalTokens: z.number().int().describe("Total tokens (inbound + outbound)")
});

export type TokenUsageStatsModel = z.infer<typeof TokenUsageStatsModelSchema>;

export const TokenUsageDailyStatsModelSchema = z.object({
   day: z.string().describe("Day in YYYY-MM-DD format"),
   modelSelectionId: z
      .string()
      .optional()
      .nullable()
      .describe("Executable model selection"),
   canonicalModelId: z
      .string()
      .optional()
      .nullable()
      .describe("Canonical model identifier"),
   modelDisplayName: z
      .string()
      .optional()
      .nullable()
      .describe("Human-readable model name resolved at aggregation time"),
   inboundTokens: z.number().int().describe("Total inbound tokens"),
   outboundTokens: z.number().int().describe("Total outbound tokens"),
   totalTokens: z.number().int().describe("Total tokens (inbound + outbound)")
});

export type TokenUsageDailyStatsModel = z.infer<
   typeof TokenUsageDailyStatsModelSchema
>;

export const ProjectTokenUsageResponseSchema = z.object({
   projectId: z.guid().describe("The project ID"),
   usages: z
      .array(TokenUsageStatsModelSchema)
      .describe("List of token usage statistics"),
   totalInboundTokens: z.number().int().describe("Total inbound tokens"),
   totalOutboundTokens: z.number().int().describe("Total outbound tokens"),
   totalTokens: z.number().int().describe("Total tokens")
});

export type ProjectTokenUsageResponse = z.infer<
   typeof ProjectTokenUsageResponseSchema
>;

export const ProjectDailyTokenUsageResponseSchema = z.object({
   projectId: z.guid().describe("The project ID"),
   month: z.string().describe("The month in YYYY-MM format"),
   usages: z
      .array(TokenUsageDailyStatsModelSchema)
      .describe("List of daily token usage statistics"),
   totalInboundTokens: z.number().int().describe("Total inbound tokens"),
   totalOutboundTokens: z.number().int().describe("Total outbound tokens"),
   totalTokens: z.number().int().describe("Total tokens")
});

export type ProjectDailyTokenUsageResponse = z.infer<
   typeof ProjectDailyTokenUsageResponseSchema
>;

// Export all schemas for global registry
// Discriminated union approach generates proper Pydantic models without RootModel wrappers
export const AISchemas: Record<string, z.ZodTypeAny> = {
   RunEventSchema,
   ToolCallSchema,
   RunStartedEventDataSchema,
   RunContentEventDataSchema,
   RunCompletedEventDataSchema,
   ToolCallStartedEventDataSchema,
   ToolCallCompletedEventDataSchema,
   ReasoningEventDataSchema,
   ArtifactEventDataSchema,
   EventDataSchema,
   SimpleRunEventSchema,
   ArtifactTypeSchema,
   ArtifactSchema,
   ToolCallStatusSchema,
   ToolCallStateSchema,
   ChatMessageTypeSchema,
   ChatMessageStatusSchema,
   ChatMessageSegmentTypeSchema,
   ChatTextSegmentSchema,
   ChatReasoningSegmentSchema,
   ChatToolCallSegmentSchema,
   ChatErrorSegmentSchema,
   ChatObjectSegmentSchema,
   ChatMessageSegmentSchema,
   ChatMessageSchema,
   ChatRequestSchema,
   TokenUsageStatsModelSchema,
   TokenUsageDailyStatsModelSchema,
   ProjectTokenUsageResponseSchema,
   ProjectDailyTokenUsageResponseSchema
} as const;
