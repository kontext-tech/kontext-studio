import type {
   ChatErrorSegment,
   ChatReasoningSegment,
   ChatTextSegment
} from "@kontext-tech/schema";

// Helper functions for creating discriminated union segments
export const createTextSegment = (
   content: string,
   cid?: string | null,
   parentId?: string | null
): ChatTextSegment => ({
   segmentType: "text" as const,
   cid: cid ?? undefined,
   parentId: parentId ?? undefined,
   content
});

export const createReasoningSegment = (
   content: string,
   cid?: string | null,
   parentId?: string | null
): ChatReasoningSegment => ({
   segmentType: "reasoning" as const,
   cid: cid ?? undefined,
   parentId: parentId ?? undefined,
   content
});

export const createErrorSegment = (
   errorDetails: string,
   cid?: string | null,
   parentId?: string | null
): ChatErrorSegment => ({
   segmentType: "error" as const,
   cid: cid ?? undefined,
   parentId: parentId ?? undefined,
   errorDetails
});
