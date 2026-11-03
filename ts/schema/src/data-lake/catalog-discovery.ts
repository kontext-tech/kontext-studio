import { z } from "zod";

import { ColumnStatsModelSchema } from "../base";
import { TableSchemaModelSchema } from "./file-models";
import { QueryEngineTypeSchema } from "./query/sessions";

// =============================================================================
// Shared Schema Column Definition
// =============================================================================

export const SchemaColumnDefinitionSchema = z.object({
   name: z.string(),
   type: z.string(),
   nullable: z.boolean().optional().nullable(),
   description: z.string().optional().nullable(),
   ordinal: z.number().int().optional().nullable()
});

// =============================================================================
// Schema Consolidation Models
// =============================================================================

/**
 * Alias retained for lakehouse/catalog profiling compatibility.
 */
export const DataLakeColumnSchema = SchemaColumnDefinitionSchema;

export const TypePromotionInfoModelSchema = z.object({
   originalType: z.string(),
   promotedType: z.string(),
   reason: z.string()
});

export const SchemaConsolidationInfoModelSchema = z.object({
   consolidationMethod: z.string().optional(),
   warnings: z.array(z.string()).optional(),
   typePromotions: z
      .record(z.string(), TypePromotionInfoModelSchema)
      .optional(),
   optionalColumns: z.array(z.string()).optional()
});

export const CatalogEntityMetadataModelSchema = z.object({
   objectType: z.string().optional(),
   fileCount: z.number().int().optional(),
   fileTypes: z.array(z.string()).optional(),
   description: z.string().optional().nullable()
});

export const CatalogEntitySchemaModelSchema = z.object({
   metadata: CatalogEntityMetadataModelSchema,
   sourceFileIds: z.array(z.string()).optional(),
   consolidationInfo: SchemaConsolidationInfoModelSchema.optional(),
   version: z.string().optional(),
   columns: z.array(SchemaColumnDefinitionSchema).optional(),
   lastModified: z.iso.datetime({ offset: true }).optional().nullable()
});

/**
 * Internal model for catalog indexing that combines schema structure with
 * profiling statistics for Iceberg/catalog-backed discovery.
 */
export const CatalogEntityDiscoveryModelSchema = z.object({
   schema: CatalogEntitySchemaModelSchema,
   rowCount: z.number().int().optional().nullable(),
   columnStats: z
      .array(z.lazy(() => ColumnStatsModelSchema))
      .optional()
      .nullable(),
   lastStatsUpdate: z.iso.datetime({ offset: true }).optional().nullable()
});

export const SchemaConsolidationResultModelSchema = z.object({
   isCompatible: z.boolean().optional(),
   consolidatedSchema: CatalogEntitySchemaModelSchema.optional().nullable(),
   validationErrors: z.array(z.string()).optional(),
   warnings: z.array(z.string()).optional()
});

export const ConsolidateSchemasRequestSchema = z.object({
   projectId: z.guid(),
   fileIds: z.array(z.guid()),
   description: z.string().optional().nullable()
});

export const SuggestObjectNameRequestSchema = z.object({
   projectId: z.guid(),
   fileIds: z.array(z.guid())
});

export const SuggestObjectNameResultModelSchema = z.object({
   suggestedName: z.string()
});

// ============================================================================
// Schema Information
// ============================================================================

export const SchemaInfoSchema = z
   .object({
      catalogName: z.string().nullable().optional(),
      schemaName: z.string().nullable().optional(),
      owner: z.string().nullable().optional(),
      qualifiedName: z.string().nullable().optional(),
      tableNames: z.array(z.string()).nullable().optional(),
      tableCount: z.number().int().nullable().optional()
   })
   .describe("Information about a database schema and its tables");

// ============================================================================
// Discovery Models
// ============================================================================

/**
 * Detailed table discovery model designed for semantic + lexical indexing.
 * Includes full column definitions and metadata for RAG-based text-to-SQL.
 */
export const TableDiscoveryModelSchema = z.object({
   engineType: z.lazy(() => QueryEngineTypeSchema),
   catalogName: z.string().optional().nullable(),
   schemaName: z.string().optional().nullable(),
   table: z.lazy(() => TableSchemaModelSchema),
   metadata: z.record(z.string(), z.any()).default({}),
   updatedAt: z.iso.datetime({ offset: true }).optional().nullable()
});

// ============================================================================
// Catalog Search Models
// ============================================================================

export const CatalogSearchItemSchema = z.object({
   schemaName: z.string(),
   tableName: z.string(),
   description: z.string().optional().nullable(),
   content: z
      .string()
      .describe("The full indexed content/description of the table"),
   score: z
      .number()
      .optional()
      .nullable()
      .describe("Relevance score where higher means more relevant"),
   rank: z
      .number()
      .int()
      .optional()
      .nullable()
      .describe("1-based rank within the returned search results"),
   connectionId: z.guid().optional().nullable(),
   connectionName: z.string().optional().nullable(),
   entityId: z.guid().optional().nullable(),
   entityType: z.string().optional().nullable()
});

// ============================================================================
// Type Exports
// ============================================================================

export type SchemaColumnDefinition = z.infer<
   typeof SchemaColumnDefinitionSchema
>;
export type DataLakeColumn = z.infer<typeof DataLakeColumnSchema>;
export type TypePromotionInfoModel = z.infer<
   typeof TypePromotionInfoModelSchema
>;
export type SchemaConsolidationInfoModel = z.infer<
   typeof SchemaConsolidationInfoModelSchema
>;
export type CatalogEntityMetadataModel = z.infer<
   typeof CatalogEntityMetadataModelSchema
>;
export type CatalogEntitySchemaModel = z.infer<
   typeof CatalogEntitySchemaModelSchema
>;
export type CatalogEntityDiscoveryModel = z.infer<
   typeof CatalogEntityDiscoveryModelSchema
>;
export type SchemaConsolidationResultModel = z.infer<
   typeof SchemaConsolidationResultModelSchema
>;
export type ConsolidateSchemasRequest = z.infer<
   typeof ConsolidateSchemasRequestSchema
>;
export type SuggestObjectNameRequest = z.infer<
   typeof SuggestObjectNameRequestSchema
>;
export type SuggestObjectNameResultModel = z.infer<
   typeof SuggestObjectNameResultModelSchema
>;
export type SchemaInfo = z.infer<typeof SchemaInfoSchema>;
export type TableDiscoveryModel = z.infer<typeof TableDiscoveryModelSchema>;
export type CatalogSearchItem = z.infer<typeof CatalogSearchItemSchema>;
