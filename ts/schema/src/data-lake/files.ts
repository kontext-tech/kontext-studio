/**
 * File schemas for Data-AI API
 * Defines file (project file) structures.
 * FileFormatTypeSchema (file format enum) and AccessLevelSchema imported from core for .NET API consistency.
 *
 * Note: FileFormatTypeSchema describes file formats (CSV, Markdown, etc.)
 * while this module's schemas describe the File entity (formerly Resource entity).
 *
 * Naming conventions:
 * - *ModelSchema: Pydantic data models (e.g., FileModel)
 * - *NavModelSchema: Navigation/summary models (e.g., FileNavModel)
 * - *Response: API response wrappers (e.g., PaginatedFileResponse, FileUploadResponse)
 * - *Request: API request bodies (e.g., CreateFileRequest)
 */

import { z } from "zod";
import { FileFormatTypeSchema } from "../core/domains/base/types.js";
import { AccessLevelSchema } from "../core/domains/projects/types.js";
import { ArtifactProvenanceSchema } from "../core/artifact-provenance.js";
import { FileSchemaModelSchema, FileStatsModelSchema } from "./file-models";

// Note: AccessLevelSchema and FileFormatTypeSchema are imported from core
// but not re-exported to avoid conflicts when both modules are exported from index.ts

// =============================================================================
// File Models
// =============================================================================

export const FileModelSchema = z.object({
   id: z.guid(),
   name: z.string().max(1024),
   prefix: z.string().max(1024).optional().nullable(),
   path: z.string().max(2048),
   uri: z.string().max(2048).optional().nullable(),
   projectId: z.guid(),
   fileType: FileFormatTypeSchema,
   contentType: z.string().max(256).optional().nullable(),
   size: z.number().int().describe("format: int64").optional().nullable(),
   accessLevel: AccessLevelSchema.optional().nullable(),
   schemaDefinition: FileSchemaModelSchema.optional().nullable(),
   statisticsData: FileStatsModelSchema.optional().nullable(),
   columnCount: z.number().int().optional().nullable(),
   rowCount: z.number().int().describe("format: int64").optional().nullable(),
   lastSchemaUpdate: z.iso.datetime({ offset: true }).optional().nullable(),
   lastStatsUpdate: z.iso.datetime({ offset: true }).optional().nullable(),
   ownerId: z.guid().optional().nullable(),
   dateCreated: z.iso.datetime({ offset: true }),
   modifiedByUserId: z.guid().optional().nullable(),
   dateModified: z.iso.datetime({ offset: true }).optional().nullable(),
   isDeleted: z.boolean(),
   dateDeleted: z.iso.datetime({ offset: true }).optional().nullable(),
   provenance: ArtifactProvenanceSchema.optional()
      .nullable()
      .describe(
         "How this file record was produced (upload channel / SQL result / agent run). Mirrors the document-level provenance for generated artifacts and is stamped at write time for uploads"
      )
});

export const FileNavModelSchema = z.object({
   id: z.guid(),
   name: z.string().max(1024),
   fileType: FileFormatTypeSchema,
   contentType: z.string().max(256).optional().nullable(),
   size: z.number().int().describe("format: int64").optional().nullable()
});

export const SimpleFileModelSchema = z.object({
   id: z.guid(),
   name: z.string().max(1024),
   uri: z.string().max(2048).optional().nullable(),
   fileType: FileFormatTypeSchema,
   contentType: z.string().max(256).optional().nullable(),
   size: z.number().int().describe("format: int64").optional().nullable()
});

export const FileSchemaExportModelSchema = z.object({
   id: z.guid(),
   name: z.string().max(1024),
   fileType: FileFormatTypeSchema,
   schemaDefinition: FileSchemaModelSchema.optional().nullable()
});

export const CreateFileRequestSchema = z.object({
   name: z.string().max(1024),
   prefix: z.string().max(1024).optional().nullable(),
   projectId: z.guid(),
   fileType: FileFormatTypeSchema,
   contentType: z.string().max(256).optional()
});

export const UpdateFileRequestSchema = z.object({
   name: z.string().max(1024).optional(),
   prefix: z.string().max(1024).optional().nullable(),
   fileType: FileFormatTypeSchema.optional(),
   contentType: z.string().max(256).optional(),
   schemaDefinition: FileSchemaModelSchema.optional().nullable(),
   statisticsData: FileStatsModelSchema.optional().nullable()
});

export const FileUploadMetadataSchema = z
   .object({
      name: z.string().min(1).max(1024).describe("File name/filename"),
      projectId: z.guid().describe("Project ID"),
      fileType: FileFormatTypeSchema.describe("Type of file"),
      contentType: z.string().min(1).max(256).describe("MIME content type"),
      size: z.number().int().min(0).describe("format: int64")
   })
   .describe("Metadata for streaming file uploads");

// =============================================================================
// Upload Response Schemas (API response wrappers)
// =============================================================================

export const FileUploadResponseSchema = z.object({
   file: FileModelSchema,
   uploadUrl: z.url().optional().nullable(),
   uploadExpiry: z.iso.datetime({ offset: true }).optional().nullable()
});

export const CreateMultipleFilesResponseSchema = z.object({
   files: z.array(FileModelSchema),
   successCount: z.number().int(),
   failureCount: z.number().int(),
   errors: z.array(z.string()).optional().nullable()
});

// =============================================================================
// Paginated Response (API response wrapper)
// =============================================================================

export const PaginatedFileResponseSchema = z.object({
   items: z.array(FileModelSchema),
   totalCount: z.number().int(),
   pageIndex: z.number().int(),
   pageSize: z.number().int(),
   totalPages: z.number().int()
});

// =============================================================================
// File Schema Update Request
// =============================================================================

export const UpdateFileSchemaRequestSchema = z.object({
   schemaDefinition: FileSchemaModelSchema.optional().nullable(),
   statisticsData: FileStatsModelSchema.optional().nullable(),
   columnCount: z.number().int().optional().nullable(),
   rowCount: z.number().int().describe("format: int64").optional().nullable(),
   size: z.number().int().describe("format: int64").optional().nullable()
});

export const BulkFileIdsRequestSchema = z.object({
   fileIds: z.array(z.guid()).min(1).max(100)
});

export const ExecuteNotebookPythonRequestSchema = z.object({
   codeOverride: z.string().optional().nullable(),
   runId: z
      .guid()
      .optional()
      .nullable()
      .describe(
         "Optional client-supplied run ID (idempotency key). Supplying it lets the caller cancel the run while it is still executing."
      )
});

// =============================================================================
// Multipart Request Bodies
// =============================================================================
//
// These describe the multipart/form-data bodies of the file upload endpoints.
// FastAPI derives a multipart body from the endpoint's flat `File()` parameters
// and synthesizes an anonymous `Body_<OperationId>` component for it, which
// surfaces in the OpenAPI spec as a generator artifact rather than a real model
// name. Declaring the bodies here gives each endpoint a stable, canonical name.
//
// These are *documented body shapes*, not constructible request objects:
//
// - The endpoints keep flat `File()` parameters. FastAPI builds the multipart
//   body from those parameters, so there is no server-side model to bind to and
//   nothing validates incoming uploads against these schemas.
// - Neither generated client emits a first-class model for a multipart body;
//   both flatten it into operation parameters. A body that names a `$ref` to one of
//   these is inlined at its request body by `openapi-normalize.cjs`, and the
//   canonical name below becomes the inlined schema's `title`.
// - The `file` property is declared as a non-empty string because the spec
//   describes the file part after multipart parsing. It is `format: binary` on
//   the wire, so these schemas must not be used to parse raw multipart data.
//
// They are named `*Body` rather than `*Request` to reflect that distinction.

export const UploadFileBodySchema = z
   .object({
      file: z.string().describe("File to upload")
   })
   .describe("Multipart request body for uploading a single file");

export const UploadMultipleFilesBodySchema = z
   .object({
      files: z.array(z.string()).min(1).describe("Files to upload")
   })
   .describe("Multipart request body for uploading multiple files");

export const UpdateFileContentBodySchema = z
   .object({
      file: z.string().describe("File to upload")
   })
   .describe("Multipart request body for replacing a file's content");

export const StartChatUploadPreparationBodySchema = z
   .object({
      files: z
         .array(z.string())
         .min(1)
         .describe("Files to prepare before starting chat")
   })
   .describe("Multipart request body for preparing chat uploads");

export const ImportOkfBundleBodySchema = z
   .object({
      file: z.string().describe("OKF bundle (.tar.gz) to import")
   })
   .describe("Multipart request body for importing an OKF bundle");

// =============================================================================
// Type Exports
// =============================================================================

export type FileModel = z.infer<typeof FileModelSchema>;
export type FileNavModel = z.infer<typeof FileNavModelSchema>;
export type SimpleFileModel = z.infer<typeof SimpleFileModelSchema>;
export type FileSchemaExportModel = z.infer<typeof FileSchemaExportModelSchema>;
export type CreateFileRequest = z.infer<typeof CreateFileRequestSchema>;
export type UpdateFileRequest = z.infer<typeof UpdateFileRequestSchema>;
export type FileUploadMetadata = z.infer<typeof FileUploadMetadataSchema>;
export type FileUploadResponse = z.infer<typeof FileUploadResponseSchema>;
export type CreateMultipleFilesResponse = z.infer<
   typeof CreateMultipleFilesResponseSchema
>;
export type PaginatedFileResponse = z.infer<typeof PaginatedFileResponseSchema>;
export type UpdateFileSchemaRequest = z.infer<
   typeof UpdateFileSchemaRequestSchema
>;
export type BulkFileIdsRequest = z.infer<typeof BulkFileIdsRequestSchema>;
export type ExecuteNotebookPythonRequest = z.infer<
   typeof ExecuteNotebookPythonRequestSchema
>;
export type UploadFileBody = z.infer<typeof UploadFileBodySchema>;
export type UploadMultipleFilesBody = z.infer<
   typeof UploadMultipleFilesBodySchema
>;
export type UpdateFileContentBody = z.infer<typeof UpdateFileContentBodySchema>;
export type StartChatUploadPreparationBody = z.infer<
   typeof StartChatUploadPreparationBodySchema
>;
export type ImportOkfBundleBody = z.infer<typeof ImportOkfBundleBodySchema>;
