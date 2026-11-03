/**
 * Base Zod schemas for notebook blocks
 */

import { z } from "zod";

// ============================================================================
// Notebook Block Type Enum
// ============================================================================

export const NotebookBlockTypeSchema = z
   .enum([
      "paragraph",
      "header",
      "list",
      "code",
      "quote",
      "table",
      "delimiter",
      "image",
      "imagePicker",
      "sql",
      "mermaid",
      "chart"
   ])
   .describe("Supported notebook block types");

export type NotebookBlockType = z.infer<typeof NotebookBlockTypeSchema>;
export const NotebookBlockType = NotebookBlockTypeSchema.enum;

// ============================================================================
// Base Block Schema
// ============================================================================

export const BaseBlockSchema = z
   .object({
      type: z.string().describe("Block type identifier"),
      id: z.guid().describe("Unique identifier for the block (UUID format)")
   })
   .describe("Base schema for all notebook blocks");

// ============================================================================
// Notebook Metadata Schema
// ============================================================================

export const NotebookMetadataSchema = z
   .object({
      description: z.string().optional().describe("Document description"),
      languageCode: z
         .string()
         .optional()
         .describe("Document language code (ISO 639-1)"),
      tags: z
         .array(z.string())
         .optional()
         .describe("Document tags for categorization"),
      keyWords: z.string().optional().describe("Article keywords"),
      imageUrl: z.string().optional().describe("Article image URL"),
      isPublished: z
         .boolean()
         .optional()
         .describe("Whether the article is published")
   })
   .describe("Optional document metadata");

export const NotebookDocumentMetadataSchema = NotebookMetadataSchema;
export type NotebookDocumentMetadata = z.infer<
   typeof NotebookDocumentMetadataSchema
>;

// ============================================================================
// Data Table Content Schema (REMOVED - now in core/data.ts)
// ============================================================================

// ============================================================================
// Data Table Schema (REMOVED - now in core/data.ts)
// ============================================================================

// ============================================================================
// Validation Result Types
// ============================================================================

export const NotebookValidationErrorSchema = z
   .object({
      field: z.string().describe("Field path where validation failed"),
      message: z.string().describe("Human-readable error message"),
      code: z.string().optional().describe("Zod error code")
   })
   .describe("Individual validation error");

export const NotebookValidationResultSchema = z
   .object({
      valid: z.boolean().describe("Whether validation passed"),
      errors: z
         .array(NotebookValidationErrorSchema)
         .describe("Array of validation errors")
   })
   .describe("Validation result with error details");

// ============================================================================
// Type Exports
// ============================================================================

export type NotebookMetadata = z.infer<typeof NotebookMetadataSchema>;
// Re-export types from core for use in notebook package
// Note: We don't export these from index.ts to avoid collisions with @kontext-tech/schema core exports
