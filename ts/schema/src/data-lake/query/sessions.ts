import { z } from "zod";

/**
 * Query Session schemas - Data-AI API session management
 *
 * Naming conventions:
 * - *ModelSchema: Pydantic data models (e.g., QuerySessionModel, QueryModel)
 * - *Response: API response wrappers (e.g., CreateQuerySessionResponse)
 * - *Request: API request bodies (e.g., CreateQuerySessionRequest)
 */

// ============================================================================
// Query Session Status
// ============================================================================

export const QuerySessionStatusSchema = z
   .enum(["Active", "Initializing", "Error", "Closed", "Deleted"])
   .describe("Query session status");

export const QuerySessionStatus = QuerySessionStatusSchema.enum;

export type QuerySessionStatus = z.infer<typeof QuerySessionStatusSchema>;

// ============================================================================
// Query Engine Type
// ============================================================================

export const QueryEngineTypeSchema = z
   .enum([
      "DuckDB",
      "Snowflake",
      "PostgreSQL",
      "SQLServer",
      "Oracle",
      "Teradata"
   ])
   .describe("Supported query execution engines");

export const QueryEngineType = QueryEngineTypeSchema.enum;

export type QueryEngineType = z.infer<typeof QueryEngineTypeSchema>;

// ============================================================================
// Query Session Model
// ============================================================================

export const QuerySessionModelSchema = z
   .object({
      id: z.guid().optional(),
      sessionName: z.string(),
      projectId: z.guid(),
      catalogConnectionId: z.guid().nullable().optional(),
      defaultNamespace: z.string().nullable().optional(),
      defaultEntityId: z.guid().nullable().optional(),
      ownerId: z.guid().nullable().optional(),
      status: z.lazy(() => QuerySessionStatusSchema).optional(),
      engineType: z
         .lazy(() => QueryEngineTypeSchema)
         .default("DuckDB")
         .describe("Execution engine type for this session"),
      jobRunId: z
         .guid()
         .nullable()
         .optional()
         .describe("Job run ID for tracking initialization status"),
      createdAt: z.iso
         .datetime({ offset: true })
         .describe("ISO 8601 datetime string with timezone")
         .optional(),
      updatedAt: z.iso
         .datetime({ offset: true })
         .describe("ISO 8601 datetime string with timezone")
         .nullable()
         .optional(),
      lastAccessedAt: z.iso
         .datetime({ offset: true })
         .describe("ISO 8601 datetime string with timezone")
         .nullable()
         .optional(),
      isPersistent: z.boolean().nullable().optional(),
      databaseSizeBytes: z
         .number()
         .int()
         .describe("format: int64")
         .nullable()
         .optional(),
      catalogRevision: z
         .string()
         .max(64)
         .nullable()
         .optional()
         .describe(
            "Catalog content revision this session materialized; used to detect stale sessions"
         ),
      errorMessage: z.string().nullable().optional()
   })
   .describe("Query session model");

export type QuerySessionModel = z.infer<typeof QuerySessionModelSchema>;

// ============================================================================
// Paginated List of Query Session Models
// ============================================================================

export const PaginatedListOfQuerySessionModelSchema = z
   .object({
      items: z.array(z.lazy(() => QuerySessionModelSchema)).default([]),
      totalCount: z.number().int(),
      pageIndex: z.number().int(),
      pageSize: z.number().int(),
      totalPages: z.number().int(),
      hasPreviousPage: z.boolean(),
      hasNextPage: z.boolean()
   })
   .describe("Paginated list of query session models");

export type PaginatedListOfQuerySessionModel = z.infer<
   typeof PaginatedListOfQuerySessionModelSchema
>;

// ============================================================================
// Create Query Session Request
// ============================================================================

export const CreateQuerySessionRequestSchema = z
   .object({
      projectId: z.guid(),
      catalogConnectionId: z.guid().nullable().optional(),
      defaultNamespace: z.string().nullable().optional(),
      defaultEntityId: z.guid().nullable().optional(),
      sessionName: z.string().min(0).max(255).nullable().optional(),
      engineType: z
         .lazy(() => QueryEngineTypeSchema)
         .optional()
         .describe(
            "Execution engine type for this session. If omitted, project default is used."
         ),
      isPersistent: z.boolean().optional()
   })
   .describe("Request to create a query session");

export type CreateQuerySessionRequest = z.infer<
   typeof CreateQuerySessionRequestSchema
>;

// ============================================================================
// Create Query Session Response (API response wrapper)
// ============================================================================

export const CreateQuerySessionResponseSchema = z
   .object({
      session: z.lazy(() => QuerySessionModelSchema)
   })
   .describe("Response from creating a query session");

export type CreateQuerySessionResponse = z.infer<
   typeof CreateQuerySessionResponseSchema
>;

// ============================================================================
// Update Query Session Request
// ============================================================================

export const UpdateQuerySessionRequestSchema = z
   .object({
      sessionName: z.string().min(0).max(255).optional(),
      status: z.lazy(() => QuerySessionStatusSchema).optional(),
      metadata: z.string().min(0).max(2000).optional(),
      databaseSizeBytes: z
         .number()
         .int()
         .min(0)
         .describe("Database size in bytes")
         .optional()
   })
   .describe("Request to update a query session");

export type UpdateQuerySessionRequest = z.infer<
   typeof UpdateQuerySessionRequestSchema
>;

// ============================================================================
// Query Session Table Model
// ============================================================================

export const QuerySessionTableModelSchema = z
   .object({
      name: z.string(),
      type: z.string(),
      fileCount: z.number().int().optional(),
      columnCount: z.number().int().optional()
   })
   .describe("Query session table information");

export type QuerySessionTableModel = z.infer<
   typeof QuerySessionTableModelSchema
>;

// ============================================================================
// Query Session Stats Response (API response wrapper)
// ============================================================================

export const QuerySessionStatsResponseSchema = z
   .object({
      session: z.lazy(() => QuerySessionModelSchema),
      tableCount: z.number().int().optional(),
      tables: z.array(z.lazy(() => QuerySessionTableModelSchema)).optional()
   })
   .describe("Query session stats response");

export type QuerySessionStatsResponse = z.infer<
   typeof QuerySessionStatsResponseSchema
>;

// ============================================================================
// Session Initialization Request
// ============================================================================

export const SessionInitRequestSchema = z
   .object({
      projectId: z.guid().describe("Project ID"),
      catalogConnectionId: z
         .guid()
         .nullable()
         .optional()
         .describe("Optional catalog connection ID"),
      defaultNamespace: z
         .string()
         .nullable()
         .optional()
         .describe("Optional default namespace"),
      defaultEntityId: z
         .guid()
         .nullable()
         .optional()
         .describe("Optional default entity ID"),
      sessionId: z.guid().describe("Session ID"),
      userId: z.guid().optional().describe("User ID"),
      persistent: z
         .boolean()
         .default(true)
         .describe("Whether session is persistent")
   })
   .describe("Request model for session initialization");

export type SessionInitRequest = z.infer<typeof SessionInitRequestSchema>;

// ============================================================================
// Session Initialization Response (API response wrapper)
// ============================================================================

export const SessionInitResponseSchema = z
   .object({
      session: z
         .lazy(() => QuerySessionModelSchema)
         .describe("Session details (may be null for async initialization)")
         .nullish(),
      success: z.boolean().describe("Whether the request was accepted"),
      errorMessage: z
         .string()
         .nullish()
         .describe("Error message if request failed"),
      jobRunId: z
         .guid()
         .nullish()
         .describe("Job run ID for tracking async initialization progress")
   })
   .describe("Response model for session initialization");

export type SessionInitResponse = z.infer<typeof SessionInitResponseSchema>;

// ============================================================================
// Query Request
// ============================================================================

export const CreateQueryRequestSchema = z
   .object({
      code: z.string(),
      succeeded: z.boolean(),
      recordCount: z
         .number()
         .int()
         .describe("format: int64")
         .nullable()
         .optional(),
      message: z.string().max(2000).nullable().optional(),
      sessionId: z.guid().nullable().optional(),
      jobRunId: z
         .guid()
         .nullable()
         .optional()
         .describe("Job run ID for tracking query execution status"),
      durationMs: z.number().int().describe("format: int64")
   })
   .describe("Request to create a query record");

export type CreateQueryRequest = z.infer<typeof CreateQueryRequestSchema>;

// ============================================================================
// Query Model
// ============================================================================

export const QueryModelSchema = z
   .object({
      id: z.guid().optional(),
      code: z.string(),
      succeeded: z.boolean().optional(),
      recordCount: z
         .number()
         .int()
         .describe("format: int64")
         .nullable()
         .optional(),
      message: z.string().nullable().optional(),
      ownerId: z.guid().optional(),
      sessionId: z.guid().nullable().optional(),
      jobRunId: z
         .guid()
         .nullable()
         .optional()
         .describe("Job run ID for tracking query execution status"),
      createdAt: z.iso
         .datetime({ offset: true })
         .describe("ISO 8601 datetime string with timezone")
         .optional(),
      durationMs: z.number().int().describe("format: int64").optional()
   })
   .describe("Query model");

export type QueryModel = z.infer<typeof QueryModelSchema>;
