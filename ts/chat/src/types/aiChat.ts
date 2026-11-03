/**
 * AI Chat streaming types for direct JSON streaming
 *
 * Simplified streaming approach that sends SimpleRunEvent objects directly as JSON
 * as NDJSON lines instead of wrapping them in a separate event envelope.
 */

// Import types from @kontext-tech/schema - single source of truth
import type { SimpleRunEvent, ToolCall } from "@kontext-tech/schema";

// Re-export SimpleRunEvent for backward compatibility
export type { SimpleRunEvent };

/**
 * Handler for streaming AI chat responses
 */
export type AIChatStreamHandler = (event: SimpleRunEvent) => void;

/**
 * Options for AI chat streaming
 */
export interface AIChatStreamOptions {
   /** Handler for individual events */
   onEvent?: AIChatStreamHandler;
   /** Handler for errors */
   onError?: (error: Error) => void;
   /** Handler for completion */
   onComplete?: () => void;
   /** Abort signal to cancel the stream */
   signal?: AbortSignal;
   /** Optional tool outputs for resuming a paused run */
   toolOutputs?: ToolCall[];
   /** Optional run ID to resume a specific paused run */
   runId?: string;
}
