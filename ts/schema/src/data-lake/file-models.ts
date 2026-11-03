/**
 * File-related models for schema and statistics
 * These models represent the output of file profilers (JSON, Parquet, etc.)
 * Separated into its own file to avoid circular dependencies between
 * resource.ts and data-lake.ts.
 */

import { z } from "zod";
import { ColumnDataTypeSchema, ColumnStatsModelSchema } from "../base";
import { FileFormatTypeSchema } from "../core/domains/base/types.js";

// =============================================================================
// Column Model (rich column definition from file profilers)
// =============================================================================

/**
 * Rich column model with full type information from file profilers.
 * This is the detailed column information extracted from files.
 */
export const ColumnModelSchema = z.object({
   name: z.string(),
   dataType: ColumnDataTypeSchema.optional().nullable(),
   nullable: z.boolean().optional().nullable(),
   description: z.string().optional().nullable(),
   maxLength: z.number().int().optional().nullable(),
   precision: z.number().int().optional().nullable(),
   scale: z.number().int().optional().nullable(),
   physicalType: z.string().optional().nullable(),
   logicalType: z.string().optional().nullable(),
   encoding: z.string().optional().nullable(),
   columnOrder: z.number().int().optional().nullable()
});

// =============================================================================
// File Metadata Model
// =============================================================================

export const FileMetadataModelSchema = z.object({
   fileName: z.string(),
   fileType: FileFormatTypeSchema.optional().nullable(),
   encoding: z.string().optional().nullable(),
   compressionType: z.string().optional().nullable(),
   delimiter: z.string().optional().nullable(),
   hasHeader: z.boolean().optional().nullable(),
   formatSpecificMetadata: z
      .record(z.string(), z.unknown())
      .optional()
      .nullable()
});

// =============================================================================
// Table Schema Model (for tables/sheets in files)
// Used in array format for both single-table and multi-table files
// =============================================================================

export const TableSchemaModelSchema = z.object({
   tableName: z.string(), // Required: name of table/sheet
   columns: z.array(ColumnModelSchema),
   isPartitioned: z.boolean().optional().nullable(),
   partitionColumns: z.array(z.string()).optional().nullable()
});

// =============================================================================
// Table Stats Model (statistics for tables/sheets in files)
// Used in array format for both single-table and multi-table files
// =============================================================================

export const TableStatsModelSchema = z.object({
   tableName: z.string(), // Required: name of table/sheet (matches TableSchemaModel)
   estimatedRowCount: z
      .number()
      .int()
      .describe("format: int64")
      .optional()
      .nullable(),
   nullPercentage: z.number().optional().nullable(),
   columnStats: z.array(ColumnStatsModelSchema).optional().nullable()
});

// =============================================================================
// File Stats Model (statistics from file profiling)
// Always uses array-based subSchemas for consistency
// =============================================================================

export const FileStatsModelSchema = z.object({
   profilingDate: z.iso.datetime({ offset: true }).optional().nullable(),
   profilingMethod: z.string().optional().nullable(),

   // Array of table/sheet statistics (length=1 for single-table files)
   subSchemas: z.array(TableStatsModelSchema),

   warnings: z.array(z.string()).optional().nullable(),
   additionalMetadata: z.record(z.string(), z.unknown()).optional().nullable()
});

// =============================================================================
// File Schema Model (schema from file profiling)
// Always uses array-based subSchemas for consistency
// =============================================================================

export const FileSchemaModelSchema = z.object({
   metadata: FileMetadataModelSchema,

   // Array of table/sheet schemas (length=1 for single-table files)
   subSchemas: z.array(TableSchemaModelSchema),

   serdeInfo: z.record(z.string(), z.unknown()).optional().nullable(),
   version: z.string().optional().nullable(),
   lastModified: z.iso.datetime({ offset: true }).optional().nullable()
});

// =============================================================================
// Type Exports
// =============================================================================

export type ColumnModel = z.infer<typeof ColumnModelSchema>;
export type FileMetadataModel = z.infer<typeof FileMetadataModelSchema>;
export type TableSchemaModel = z.infer<typeof TableSchemaModelSchema>;
export type TableStatsModel = z.infer<typeof TableStatsModelSchema>;
export type FileStatsModel = z.infer<typeof FileStatsModelSchema>;
export type FileSchemaModel = z.infer<typeof FileSchemaModelSchema>;
