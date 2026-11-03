import { z } from "zod";

/**
 * Common AI-related types and enums to avoid circular dependencies.
 */

export const ArtifactTypeSchema = z.enum([
   "DataTable",
   "Notebook",
   "Chart",
   "Image"
]);
export type ArtifactType = z.infer<typeof ArtifactTypeSchema>;
export const ArtifactType = ArtifactTypeSchema.enum;

export const ArtifactEventKindSchema = z.enum(["created", "updated"]);
export type ArtifactEventKind = z.infer<typeof ArtifactEventKindSchema>;
export const ArtifactEventKind = ArtifactEventKindSchema.enum;

/**
 * All possible artifact action types.
 */
export const ArtifactActionTypeSchema = z.enum([
   "upsertBlock",
   "patchBlockContent",
   "setBlockOutput",
   "removeBlock",
   "updateMetadata",
   "updateChartConfig",
   "setChartData",
   "openDataTable"
]);
export type ArtifactActionType = z.infer<typeof ArtifactActionTypeSchema>;
export const ArtifactActionType = ArtifactActionTypeSchema.enum;

/**
 * All possible tool call result types. (Discriminated union discriminators)
 */
export const ToolCallResultTypeSchema = z.enum([
   "sql_execution",
   "sql_execution_batch",
   "sql_validation",
   "sql_validation_batch",
   "python_validation",
   "python_execution",
   "catalog_listing",
   "catalog_entity_stats",
   "catalog_entity_stats_batch",
   "discovery",
   "project_retrieval",
   "chart_mutation",
   "chart_batch",
   "notebook_info",
   "notebook_batch",
   "notebook_list",
   "notebook_mutation",
   "notebook_block_mutation",
   "notebook_block_batch",
   "notebook_block_list",
   "notebook_multi_block_mutation",
   "notebook_data_list",
   "catalog_search",
   "knowledge_search",
   "knowledge_proposal"
]);
export type ToolCallResultType = z.infer<typeof ToolCallResultTypeSchema>;
export const ToolCallResultType = ToolCallResultTypeSchema.enum;
