import { z } from "zod";
import { ArtifactTypeSchema } from "./types";

/**
 * Chat session schemas for Data-AI API
 *
 * Naming conventions:
 * - *ModelSchema: Pydantic data models (e.g., ChatSessionModel)
 * - *Response: API response wrappers (e.g., PaginatedChatSessionResponse)
 * - *Request: API request bodies (e.g., CreateChatSessionRequest)
 */

export const PythonExecutionApprovalModeSchema = z.enum([
   "always_ask",
   "auto_approve"
]);
export type PythonExecutionApprovalMode = z.infer<
   typeof PythonExecutionApprovalModeSchema
>;
export const PythonExecutionApprovalMode =
   PythonExecutionApprovalModeSchema.enum;

export const ChatSessionModelSchema = z
   .object({
      id: z.guid().describe("Unique chat session identifier"),
      projectId: z.guid().describe("Project ID"),
      sessionName: z.string().describe("Name of the chat session"),
      modelSelectionId: z
         .string()
         .optional()
         .nullable()
         .describe("Executable model selection used for this session"),
      tokensInbound: z
         .number()
         .int()
         .describe("format: int64")
         .optional()
         .nullable(),
      tokensOutbound: z
         .number()
         .int()
         .describe("format: int64")
         .optional()
         .nullable(),
      ownerId: z.guid().optional().describe("Owner user ID"),
      dateCreated: z.iso
         .datetime({ offset: true })
         .describe("ISO 8601 datetime string with timezone"),
      modifiedByUserId: z
         .guid()
         .optional()
         .nullable()
         .describe("Last modifier user ID"),
      dateModified: z.iso
         .datetime({ offset: true })
         .optional()
         .nullable()
         .describe("ISO 8601 datetime string with timezone"),
      querySessionId: z
         .guid()
         .optional()
         .nullable()
         .describe("Associated query session ID (DuckDB session)"),
      defaultCatalogConnectionId: z
         .guid()
         .optional()
         .nullable()
         .describe("Default catalog connection ID for this chat session"),
      defaultNamespace: z
         .string()
         .optional()
         .nullable()
         .describe("Default namespace for this chat session"),
      defaultEntityId: z
         .guid()
         .optional()
         .nullable()
         .describe("Default entity ID for this chat session"),
      engineType: z
         .string()
         .optional()
         .nullable()
         .describe("Sticky query engine type for this chat session"),
      pythonExecutionApprovalMode: PythonExecutionApprovalModeSchema.default(
         "always_ask"
      ).describe("Session policy for Python execution approval"),
      isDeleted: z.boolean().describe("Soft delete flag"),
      dateDeleted: z.iso
         .datetime({ offset: true })
         .optional()
         .nullable()
         .describe("ISO 8601 datetime string with timezone")
   })
   .describe("Chat session model");

// ============================================================================
// Chat Session Requests
// ============================================================================

export const CreateChatSessionRequestSchema = z
   .object({
      projectId: z.guid().describe("Project ID"),
      sessionName: z
         .string()
         .min(1)
         .max(256)
         .describe("Name of the chat session"),
      modelSelectionId: z
         .string()
         .optional()
         .nullable()
         .describe("Executable model selection for the chat session"),
      defaultCatalogConnectionId: z
         .guid()
         .optional()
         .nullable()
         .describe("Default catalog connection ID for the chat session"),
      defaultNamespace: z
         .string()
         .optional()
         .nullable()
         .describe("Default namespace for the chat session"),
      defaultEntityId: z
         .guid()
         .optional()
         .nullable()
         .describe("Default entity ID for the chat session"),
      engineType: z
         .string()
         .optional()
         .nullable()
         .describe("Sticky query engine type for the chat session"),
      pythonExecutionApprovalMode:
         PythonExecutionApprovalModeSchema.optional().describe(
            "Default Python execution approval policy for the chat session. Defaults to always_ask when omitted."
         )
   })
   .describe("Request model for creating a chat session");

export const UpdateChatSessionRequestSchema = z
   .object({
      sessionName: z
         .string()
         .min(1)
         .max(256)
         .optional()
         .describe("Updated name of the chat session"),
      modelSelectionId: z
         .string()
         .optional()
         .describe("Updated executable model selection"),
      querySessionId: z.guid().optional().describe("Updated query session ID"),
      defaultCatalogConnectionId: z
         .guid()
         .optional()
         .describe("Updated default catalog connection ID"),
      defaultNamespace: z
         .string()
         .optional()
         .describe("Updated default namespace"),
      defaultEntityId: z
         .guid()
         .optional()
         .describe("Updated default entity ID"),
      engineType: z
         .string()
         .optional()
         .describe("Updated sticky query engine type"),
      pythonExecutionApprovalMode:
         PythonExecutionApprovalModeSchema.optional().describe(
            "Updated Python execution approval policy"
         )
   })
   .describe("Request model for updating a chat session");

// ============================================================================
// Paginated Chat Session Response (API response wrapper)
// ============================================================================

export const PaginatedChatSessionResponseSchema = z
   .object({
      items: z.array(ChatSessionModelSchema).describe("List of chat sessions"),
      totalCount: z.number().int().describe("Total number of items"),
      pageIndex: z.number().int().describe("Current page index (1-based)"),
      pageSize: z.number().int().describe("Number of items per page"),
      totalPages: z.number().int().describe("Total number of pages")
   })
   .describe("Paginated response for chat sessions");

// ============================================================================
// Type Exports
// ============================================================================

export type ChatSessionModel = z.infer<typeof ChatSessionModelSchema>;
export type CreateChatSessionRequest = z.infer<
   typeof CreateChatSessionRequestSchema
>;
export type UpdateChatSessionRequest = z.infer<
   typeof UpdateChatSessionRequestSchema
>;
export type PaginatedChatSessionResponse = z.infer<
   typeof PaginatedChatSessionResponseSchema
>;

// ============================================================================
// Chat Session Artifacts
// ============================================================================

export const ChatSessionArtifactModelSchema = z
   .object({
      id: z.guid().describe("Unique record identifier"),
      sessionId: z.guid().describe("Chat session ID"),
      artifactId: z.guid().describe("Artifact ID (e.g. notebook ID)"),
      artifactType: ArtifactTypeSchema.describe(
         "Type of artifact (notebook, chart, image, etc.)"
      ),
      title: z.string().describe("Title of the artifact"),
      meta: z
         .record(z.string(), z.any())
         .optional()
         .nullable()
         .describe("Metadata"),
      createdAt: z.iso
         .datetime({ offset: true })
         .describe("Creation timestamp"),
      updatedAt: z.iso
         .datetime({ offset: true })
         .describe("Last update timestamp")
   })
   .describe("Chat session artifact model");

export type ChatSessionArtifactModel = z.infer<
   typeof ChatSessionArtifactModelSchema
>;

export const ArtifactListResponseSchema = z
   .object({
      artifacts: z
         .array(ChatSessionArtifactModelSchema)
         .describe("List of artifacts")
   })
   .describe("Response containing a list of artifacts for a session");

export type ArtifactListResponse = z.infer<typeof ArtifactListResponseSchema>;
