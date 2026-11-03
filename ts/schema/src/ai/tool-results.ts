import { z } from "zod";

import { ColumnStatsModelSchema } from "../base";
import { ChartDocumentSchema } from "../charts/document";
import {
   DataRefSchema,
   DataTableSummarySchema,
   InlineDataSchema
} from "../core/data";
import { ArtifactProvenanceSchema } from "../core/artifact-provenance";
import { ProjectModelSchema } from "../core/domains/projects/index.js";
import { OkfConceptSchema } from "../core/domains/knowledge/index.js";
import { CatalogSearchItemSchema } from "../data-lake";
import { FileModelSchema } from "../data-lake/files";
import { NotebookBlockSchema, NotebookDocumentSchema } from "../notebook";
import { CodeExecutionOutputSchema } from "../notebook/blocks/code";
import { ArtifactActionSchema } from "./actions";
import { ToolCallResultType, ToolCallResultTypeSchema } from "./types";

/**
 * Base schema for all tool execution results.
 * This is the payload that gets JSON-stringified into ToolCall.result field.
 */
export const BaseToolResultSchema = z.object({
   type: ToolCallResultTypeSchema.optional().describe(
      "Type of the tool result"
   ),
   success: z.boolean().describe("Whether the operation succeeded"),
   message: z.string().describe("Operation result message"),
   error: z.string().nullish().describe("Error details if any")
});

/**
 * SQL Tool Results
 */
export const SqlExecutionResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.sql_execution)
      .default(ToolCallResultType.sql_execution),
   executionTimeMs: z.number().int().default(0),
   dataRef: DataRefSchema.nullish(),
   preview: InlineDataSchema.nullish().describe(
      "Preview of the result data (e.g. first 3 rows), useful for the agent to inspect the data"
   ),
   actions: z.array(ArtifactActionSchema).nullish(),
   provenance: ArtifactProvenanceSchema.nullish().describe(
      "Provenance of the artifacts produced by this execution"
   )
}).describe("Result for SQL execution");

export const SqlValidationResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.sql_validation)
      .default(ToolCallResultType.sql_validation)
}).describe("Result for SQL validation");

/**
 * Catalog Search Result
 */
export const CatalogSearchResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.catalog_search)
      .default(ToolCallResultType.catalog_search),
   tables: z
      .array(z.lazy(() => CatalogSearchItemSchema))
      .default([])
      .describe("List of relevant tables found in the catalog")
}).describe("Result for catalog semantic search");

/**
 * Knowledge (OKF curation) Tool Results
 */
export const KnowledgeSearchResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.knowledge_search)
      .default(ToolCallResultType.knowledge_search),
   concepts: z
      .array(z.lazy(() => OkfConceptSchema))
      .default([])
      .describe("Curated OKF concepts relevant to the request")
}).describe("Result for curated knowledge search");

export const KnowledgeProposalResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.knowledge_proposal)
      .default(ToolCallResultType.knowledge_proposal),
   concept: z
      .lazy(() => OkfConceptSchema)
      .nullish()
      .describe("The proposed concept awaiting user approval")
}).describe("Result for proposing a new curated knowledge concept");

/**
 * Python Tool Results
 */
export const PythonValidationResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.python_validation)
      .default(ToolCallResultType.python_validation),
   valid: z.boolean().describe("Whether the Python code is valid and safe"),
   issues: z.array(z.string()).nullish().describe("Security or syntax issues")
}).describe("Result for Python validation");

export const PythonExecutionModeSchema = z.enum(["draft", "persisted"]);

export type PythonExecutionMode = z.infer<typeof PythonExecutionModeSchema>;
export const PythonExecutionMode = PythonExecutionModeSchema.enum;
export const PythonExecutionTargetTypeSchema = z.enum(["notebook", "session"]);
export type PythonExecutionTargetType = z.infer<
   typeof PythonExecutionTargetTypeSchema
>;
export const PythonExecutionTargetType = PythonExecutionTargetTypeSchema.enum;

/**
 * Python code execution result.
 * Used when backend executes Python code and returns results.
 */
export const PythonExecutionResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.python_execution)
      .default(ToolCallResultType.python_execution),
   notebookId: z.string().nullish(),
   executionRunId: z.string().nullish(),
   executionMode: z.lazy(() => PythonExecutionModeSchema).nullish(),
   targetType: z.lazy(() => PythonExecutionTargetTypeSchema).nullish(),
   outputs: z
      .array(CodeExecutionOutputSchema)
      .default([])
      .describe("Structured execution outputs (text, images, json)"),
   actions: z.array(ArtifactActionSchema).nullish(),
   provenance: ArtifactProvenanceSchema.nullish().describe(
      "Provenance for artifacts produced or owned by this run"
   ),
   savedTables: z
      .array(z.lazy(() => PythonSavedTableSchema))
      .nullish()
      .describe(
         "Durable data tables persisted via kontext.save_table during this run"
      )
}).describe("Result for external Python execution");

export const PythonSavedTableSchema = z
   .object({
      dataTableId: z
         .string()
         .describe("Durable data table file ID of the saved table"),
      title: z.string().nullish().describe("Title the table was saved under"),
      rowCount: z
         .number()
         .int()
         .describe("format: int64")
         .nullish()
         .describe("Saved row count")
   })
   .describe(
      "Summary of a durable data table persisted via kontext.save_table"
   );

export type PythonSavedTable = z.infer<typeof PythonSavedTableSchema>;

/**
 * Catalog Tool Results
 */
export const CatalogListingResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.catalog_listing)
      .default(ToolCallResultType.catalog_listing),
   catalogConnectionId: z.string().nullish(),
   objectsCount: z.number().int().default(0),
   objects: z.string().default("")
}).describe("Result for catalog namespace or entity listing");

export const CatalogEntityStatsResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.catalog_entity_stats)
      .default(ToolCallResultType.catalog_entity_stats),
   catalogConnectionId: z.string().nullish(),
   namespaceName: z.string().nullish(),
   objectId: z.string().nullish(),
   objectName: z.string().nullish(),
   columnStats: z.array(ColumnStatsModelSchema).default([]),
   statsCount: z.number().int().default(0)
}).describe("Result for catalog entity column inspection");

/**
 * Project Tool Results
 */
export const ProjectResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.project_retrieval)
      .default(ToolCallResultType.project_retrieval),
   project: ProjectModelSchema.nullish()
}).describe("Result for project retrieval");

/**
 * Chart Tool Results
 */
export const ChartResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.chart_mutation)
      .default(ToolCallResultType.chart_mutation),
   chartId: z.string().nullish(),
   chart: ChartDocumentSchema.nullish(),
   chartDocumentUrl: z.string().nullish(),
   dataSummary: DataTableSummarySchema.nullish(),
   dataId: z.string().nullish(),
   actions: z.array(ArtifactActionSchema).nullish()
}).describe("Result for chart operations");

/**
 * Notebook Tool Results
 */
export const NotebookResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_info)
      .default(ToolCallResultType.notebook_info),
   notebookId: z.string().nullish(),
   notebook: NotebookDocumentSchema.nullish()
}).describe("Result for single notebook operations");

export const NotebookListResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_list)
      .default(ToolCallResultType.notebook_list),
   notebooks: z.array(FileModelSchema).default([])
}).describe("Result for notebook listing");

export const NotebookMutationResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_mutation)
      .default(ToolCallResultType.notebook_mutation),
   notebookId: z.string().nullish(),
   name: z.string().nullish(),
   actions: z.array(ArtifactActionSchema).nullish()
}).describe("Result for notebook creation/update");

export const NotebookBlockResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_block_mutation)
      .default(ToolCallResultType.notebook_block_mutation),
   notebookId: z.string(),
   blockId: z.string().nullish(),
   block: NotebookBlockSchema.nullish(),
   dataId: z.string().nullish(),
   actions: z.array(ArtifactActionSchema).nullish()
}).describe("Result for single notebook block operations");

export const NotebookBlockListResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_block_list)
      .default(ToolCallResultType.notebook_block_list),
   notebookId: z.string(),
   blocksCount: z.number().int().default(0),
   blocks: z.array(NotebookBlockSchema).default([])
}).describe("Result for notebook block list operations");

export const NotebookMultiBlockResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_multi_block_mutation)
      .default(ToolCallResultType.notebook_multi_block_mutation),
   notebookId: z.string(),
   blocksCount: z.number().int().default(0),
   blockIds: z.array(z.string()).default([]),
   actions: z.array(ArtifactActionSchema).nullish()
}).describe("Result for multi-block operations");

export const NotebookDataResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_data_list)
      .default(ToolCallResultType.notebook_data_list),
   notebookId: z.string(),
   dataCount: z.number().int().default(0),
   inlineDataList: z.array(InlineDataSchema).default([])
}).describe("Result for notebook data table operations");

/**
 * Batch Tool Results
 *
 * These wrap the single-item result models above so one tool call can return
 * several results without a roundtrip per item. Each item keeps its own
 * success/message so partial failures stay visible to the model.
 */
export const SqlExecutionBatchResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.sql_execution_batch)
      .default(ToolCallResultType.sql_execution_batch),
   results: z
      .array(SqlExecutionResultSchema)
      .default([])
      .describe("Per-statement execution results, in request order"),
   resultsCount: z.number().int().default(0),
   failedCount: z.number().int().default(0),
   executionTimeMs: z.number().int().default(0)
}).describe("Result for batch SQL execution");

export const SqlValidationBatchResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.sql_validation_batch)
      .default(ToolCallResultType.sql_validation_batch),
   results: z
      .array(SqlValidationResultSchema)
      .default([])
      .describe("Per-statement validation results, in request order"),
   resultsCount: z.number().int().default(0),
   failedCount: z.number().int().default(0)
}).describe("Result for batch SQL validation");

export const CatalogEntityStatsBatchResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.catalog_entity_stats_batch)
      .default(ToolCallResultType.catalog_entity_stats_batch),
   catalogConnectionId: z.string().nullish(),
   entities: z
      .array(CatalogEntityStatsResultSchema)
      .default([])
      .describe("Per-entity column inspection results, in request order"),
   entitiesCount: z.number().int().default(0),
   failedCount: z.number().int().default(0)
}).describe("Result for batch catalog entity column inspection");

export const ChartBatchResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.chart_batch)
      .default(ToolCallResultType.chart_batch),
   charts: z
      .array(ChartResultSchema)
      .default([])
      .describe("Per-chart retrieval results, in request order"),
   chartsCount: z.number().int().default(0),
   failedCount: z.number().int().default(0)
}).describe("Result for batch chart retrieval");

export const NotebookBatchResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_batch)
      .default(ToolCallResultType.notebook_batch),
   notebooks: z
      .array(NotebookResultSchema)
      .default([])
      .describe("Per-notebook retrieval results, in request order"),
   notebooksCount: z.number().int().default(0),
   failedCount: z.number().int().default(0)
}).describe("Result for batch notebook retrieval");

export const NotebookBlockBatchResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.notebook_block_batch)
      .default(ToolCallResultType.notebook_block_batch),
   blocks: z
      .array(NotebookBlockResultSchema)
      .default([])
      .describe("Per-block retrieval results, in request order"),
   blocksCount: z.number().int().default(0),
   failedCount: z.number().int().default(0)
}).describe("Result for batch notebook block retrieval");

export const DocumentSearchItemSchema = z
   .object({
      source: z.string().nullish(),
      content: z.string().default(""),
      score: z.number().nullish()
   })
   .describe("A single document search hit");

export const DiscoveryResultSchema = BaseToolResultSchema.extend({
   type: z
      .literal(ToolCallResultType.discovery)
      .default(ToolCallResultType.discovery),
   query: z.string(),
   tables: z
      .array(z.lazy(() => CatalogSearchItemSchema))
      .default([])
      .describe("Relevant catalog tables"),
   concepts: z
      .array(z.lazy(() => OkfConceptSchema))
      .default([])
      .describe("Relevant curated knowledge concepts"),
   documents: z
      .array(DocumentSearchItemSchema)
      .default([])
      .describe("Relevant document excerpts"),
   errors: z
      .record(z.string(), z.string())
      .nullish()
      .describe("Sources that could not be searched, keyed by source name")
}).describe(
   "Result for unified discovery across tables, curated knowledge, and documents"
);

/**
 * HITL / External Execution Models
 */
export const ToolExecutionSchema = z
   .object({
      toolName: z.string().nullish(),
      toolArgs: z.record(z.string(), z.any()).nullish(),
      toolCallId: z.string().nullish(),
      externalExecutionRequired: z.boolean().default(true)
   })
   .describe("Execution record for a tool call requiring external processing");

export const ExternalExecutionRequirementSchema = z
   .object({
      toolExecution: ToolExecutionSchema.nullish(),
      externalExecutionResult: z.any().nullish() // Typed more broadly as any for runtime flexibility
   })
   .describe(
      "Requirement for an external execution result to resume an agent run"
   );

/**
 * Union type for any tool result that can be produced by Kontext Agentic tools.
 *
 * NOTE: keep this a flat `z.union` with the untyped `BaseToolResult` fallback
 * last. Runtime typing/discrimination is enforced by the generated Pydantic
 * models (`extra="forbid"`), so mis-matched payloads are rejected there.
 *
 * Deliberately NOT `z.discriminatedUnion`: the OpenAPI exporter emits each
 * member of a discriminated union as a *nested* wrapper model
 * (`ToolCallResultAnyOf`), which would force every consumer that unwraps
 * `ToolCallResult.root` (artifact linking, pause/resume, error classification)
 * through an extra layer. Flatten the exporter first if stricter TS-side
 * matching is ever needed.
 */
export const ToolCallResultSchema = z.union([
   z.string(),
   SqlExecutionResultSchema,
   SqlExecutionBatchResultSchema,
   SqlValidationResultSchema,
   SqlValidationBatchResultSchema,
   CatalogSearchResultSchema,
   KnowledgeSearchResultSchema,
   KnowledgeProposalResultSchema,
   PythonValidationResultSchema,
   PythonExecutionResultSchema,
   CatalogListingResultSchema,
   CatalogEntityStatsResultSchema,
   CatalogEntityStatsBatchResultSchema,
   DiscoveryResultSchema,
   ProjectResultSchema,
   ChartResultSchema,
   ChartBatchResultSchema,
   NotebookResultSchema,
   NotebookBatchResultSchema,
   NotebookListResultSchema,
   NotebookMutationResultSchema,
   NotebookBlockResultSchema,
   NotebookBlockBatchResultSchema,
   NotebookBlockListResultSchema,
   NotebookMultiBlockResultSchema,
   NotebookDataResultSchema,
   BaseToolResultSchema
]);

// Export types
export type BaseToolResult = z.infer<typeof BaseToolResultSchema>;
export type SqlExecutionResult = z.infer<typeof SqlExecutionResultSchema>;
export type SqlExecutionBatchResult = z.infer<
   typeof SqlExecutionBatchResultSchema
>;
export type SqlValidationResult = z.infer<typeof SqlValidationResultSchema>;
export type SqlValidationBatchResult = z.infer<
   typeof SqlValidationBatchResultSchema
>;
export type CatalogSearchResult = z.infer<typeof CatalogSearchResultSchema>;
export type KnowledgeSearchResult = z.infer<typeof KnowledgeSearchResultSchema>;
export type KnowledgeProposalResult = z.infer<
   typeof KnowledgeProposalResultSchema
>;
export type PythonValidationResult = z.infer<
   typeof PythonValidationResultSchema
>;
export type PythonExecutionResult = z.infer<typeof PythonExecutionResultSchema>;
export type CatalogListingResult = z.infer<typeof CatalogListingResultSchema>;
export type CatalogEntityStatsResult = z.infer<
   typeof CatalogEntityStatsResultSchema
>;
export type CatalogEntityStatsBatchResult = z.infer<
   typeof CatalogEntityStatsBatchResultSchema
>;
export type DiscoveryResult = z.infer<typeof DiscoveryResultSchema>;
export type DocumentSearchItem = z.infer<typeof DocumentSearchItemSchema>;
export type ProjectResult = z.infer<typeof ProjectResultSchema>;
export type ChartResult = z.infer<typeof ChartResultSchema>;
export type ChartBatchResult = z.infer<typeof ChartBatchResultSchema>;
export type NotebookResult = z.infer<typeof NotebookResultSchema>;
export type NotebookBatchResult = z.infer<typeof NotebookBatchResultSchema>;
export type NotebookListResult = z.infer<typeof NotebookListResultSchema>;
export type NotebookMutationResult = z.infer<
   typeof NotebookMutationResultSchema
>;
export type NotebookBlockResult = z.infer<typeof NotebookBlockResultSchema>;
export type NotebookBlockBatchResult = z.infer<
   typeof NotebookBlockBatchResultSchema
>;
export type NotebookBlockListResult = z.infer<
   typeof NotebookBlockListResultSchema
>;
export type NotebookMultiBlockResult = z.infer<
   typeof NotebookMultiBlockResultSchema
>;
export type NotebookDataResult = z.infer<typeof NotebookDataResultSchema>;
export type ToolExecution = z.infer<typeof ToolExecutionSchema>;
export type ExternalExecutionRequirement = z.infer<
   typeof ExternalExecutionRequirementSchema
>;
export type ToolCallResult = z.infer<typeof ToolCallResultSchema>;
