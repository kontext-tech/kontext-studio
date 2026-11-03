import { z } from "zod";
import { CodeExecutionOutputSchema } from "../notebook/blocks/code";
import { ArtifactActionType, ArtifactActionTypeSchema } from "./types";

/**
 * Universal Artifact Action schemas for streaming granular updates.
 *
 * These actions enable real-time, incremental updates to artifacts during agent execution,
 * eliminating the need for full-page refreshes and providing smooth "live-typing" UX.
 */

// Base schema shared by all actions
const BaseArtifactActionSchema = z.object({
   actionType: ArtifactActionTypeSchema.describe(
      "Type of action being performed"
   ),
   sequence: z
      .number()
      .nonnegative()
      .describe(
         "Sequence number for ordering; ideally high-precision timestamp to ensure global uniqueness within artifact"
      )
});

// ============================================================================
// Notebook Action Payloads
// ============================================================================

/**
 * NotebookUpsertBlockActionPayload
 */
export const NotebookUpsertBlockActionPayloadSchema = z.object({
   cid: z.string().describe("Content identifier (CID) of the block"),
   blockType: z
      .string()
      .describe("Type of block (e.g., 'markdown', 'code', 'chart')"),
   data: z.record(z.string(), z.any()).describe("Block-specific data object"),
   position: z
      .number()
      .int()
      .nonnegative()
      .nullable()
      .optional()
      .describe("Optional insertion index; omit to append at end")
});
export type NotebookUpsertBlockActionPayload = z.infer<
   typeof NotebookUpsertBlockActionPayloadSchema
>;

/**
 * UPSERT_BLOCK: Create a new block or update an existing one.
 * Used when agent adds a new cell or replaces an entire cell's content.
 */
export const NotebookUpsertBlockActionSchema = BaseArtifactActionSchema.extend({
   actionType: z.literal("upsertBlock"),
   payload: NotebookUpsertBlockActionPayloadSchema
});
export type NotebookUpsertBlockAction = z.infer<
   typeof NotebookUpsertBlockActionSchema
>;

/**
 * NotebookPatchBlockContentActionPayload
 */
export const NotebookPatchBlockContentActionPayloadSchema = z.object({
   cid: z.string().describe("Content identifier of the target block"),
   field: z
      .string()
      .optional()
      .describe("Field name to update (e.g., 'content', 'language')"),
   value: z.any().optional().describe("New value for the field"),
   patch: z.string().optional().describe("Incremental text patch"),
   replace: z.boolean().optional().describe("Whether to replace or append")
});
export type NotebookPatchBlockContentActionPayload = z.infer<
   typeof NotebookPatchBlockContentActionPayloadSchema
>;

/**
 * PATCH_BLOCK_CONTENT: Incrementally update a specific field within a block.
 * Used for streaming text/code content character-by-character.
 */
export const NotebookPatchBlockContentActionSchema =
   BaseArtifactActionSchema.extend({
      actionType: z.literal("patchBlockContent"),
      payload: NotebookPatchBlockContentActionPayloadSchema
   });
export type NotebookPatchBlockContentAction = z.infer<
   typeof NotebookPatchBlockContentActionSchema
>;

export const NotebookSetBlockOutputActionPayloadOutputSchema =
   CodeExecutionOutputSchema;
export type NotebookSetBlockOutputActionPayloadOutput = z.infer<
   typeof NotebookSetBlockOutputActionPayloadOutputSchema
>;

export const NotebookSetBlockOutputActionPayloadSchema = z.object({
   cid: z.string().describe("Content identifier of the code block"),
   outputs: z
      .array(CodeExecutionOutputSchema)
      .nullable()
      .describe("Execution outputs; null to clear outputs")
});
export type NotebookSetBlockOutputActionPayload = z.infer<
   typeof NotebookSetBlockOutputActionPayloadSchema
>;

/**
 * SET_BLOCK_OUTPUT: Update the execution output of a code block.
 * Used when agent runs code and receives results.
 */
export const NotebookSetBlockOutputActionSchema =
   BaseArtifactActionSchema.extend({
      actionType: z.literal("setBlockOutput"),
      payload: NotebookSetBlockOutputActionPayloadSchema
   });
export type NotebookSetBlockOutputAction = z.infer<
   typeof NotebookSetBlockOutputActionSchema
>;

/**
 * NotebookRemoveBlockActionPayload
 */
export const NotebookRemoveBlockActionPayloadSchema = z.object({
   cid: z.string().describe("Content identifier of the block to remove")
});
export type NotebookRemoveBlockActionPayload = z.infer<
   typeof NotebookRemoveBlockActionPayloadSchema
>;

/**
 * REMOVE_BLOCK: Delete a block from the notebook.
 */
export const NotebookRemoveBlockActionSchema = BaseArtifactActionSchema.extend({
   actionType: z.literal("removeBlock"),
   payload: NotebookRemoveBlockActionPayloadSchema
});
export type NotebookRemoveBlockAction = z.infer<
   typeof NotebookRemoveBlockActionSchema
>;

/**
 * NotebookUpdateMetadataActionPayload
 */
export const NotebookUpdateMetadataActionPayloadSchema = z.object({
   varField: z
      .string()
      .describe("Metadata field to update (e.g., 'title', 'tags')"),
   value: z
      .any()
      .optional()
      .describe("New value for the metadata field; absent for unset fields")
});
export type NotebookUpdateMetadataActionPayload = z.infer<
   typeof NotebookUpdateMetadataActionPayloadSchema
>;

/**
 * UPDATE_METADATA: Modify notebook-level metadata (title, tags, etc.).
 */
export const NotebookUpdateMetadataActionSchema =
   BaseArtifactActionSchema.extend({
      actionType: z.literal("updateMetadata"),
      payload: NotebookUpdateMetadataActionPayloadSchema
   });
export type NotebookUpdateMetadataAction = z.infer<
   typeof NotebookUpdateMetadataActionSchema
>;

// Union of all notebook actions
export const NotebookActionPayloadSchema = z.discriminatedUnion("actionType", [
   NotebookUpsertBlockActionSchema,
   NotebookPatchBlockContentActionSchema,
   NotebookSetBlockOutputActionSchema,
   NotebookRemoveBlockActionSchema,
   NotebookUpdateMetadataActionSchema
]);

export type NotebookActionPayload = z.infer<typeof NotebookActionPayloadSchema>;

// ============================================================================
// Chart Action Payloads (future expansion)
// ============================================================================

/**
 * ChartUpdateConfigActionPayload
 */
export const ChartUpdateConfigActionPayloadSchema = z.object({
   configPath: z
      .array(z.string())
      .describe("JSONPath to the config field (e.g., ['xAxis', 'title'])"),
   value: z.any().describe("New value for the config field")
});
export type ChartUpdateConfigActionPayload = z.infer<
   typeof ChartUpdateConfigActionPayloadSchema
>;

/**
 * UPDATE_CHART_CONFIG: Modify chart configuration.
 * Placeholder for future chart streaming support.
 */
export const ChartUpdateConfigActionSchema = BaseArtifactActionSchema.extend({
   actionType: z.literal("updateChartConfig"),
   payload: ChartUpdateConfigActionPayloadSchema
});
export type ChartUpdateConfigAction = z.infer<
   typeof ChartUpdateConfigActionSchema
>;

/**
 * ChartSetDataActionPayload
 */
export const ChartSetDataActionPayloadSchema = z.object({
   dataId: z.string().describe("Identifier of the new data table")
});
export type ChartSetDataActionPayload = z.infer<
   typeof ChartSetDataActionPayloadSchema
>;

/**
 * SET_CHART_DATA: Replace chart data table input.
 */
export const ChartSetDataActionSchema = BaseArtifactActionSchema.extend({
   actionType: z.literal("setChartData"),
   payload: ChartSetDataActionPayloadSchema
});
export type ChartSetDataAction = z.infer<typeof ChartSetDataActionSchema>;

// Union of all chart actions
export const ChartActionPayloadSchema = z.discriminatedUnion("actionType", [
   ChartUpdateConfigActionSchema,
   ChartSetDataActionSchema
]);

export type ChartActionPayload = z.infer<typeof ChartActionPayloadSchema>;

// ============================================================================
// Data Table Action Payloads
// ============================================================================

/**
 * DataTableOpenActionPayload
 */
export const DataTableOpenActionPayloadSchema = z.object({
   dataId: z.string().describe("Identifier of the data table to open"),
   title: z.string().optional().describe("Optional title for context")
});
export type DataTableOpenActionPayload = z.infer<
   typeof DataTableOpenActionPayloadSchema
>;

/**
 * OPEN_DATA_TABLE: Instruct the frontend to open a data table tab or view.
 */
export const DataTableOpenActionSchema = BaseArtifactActionSchema.extend({
   actionType: z.literal("openDataTable"),
   payload: DataTableOpenActionPayloadSchema
});
export type DataTableOpenAction = z.infer<typeof DataTableOpenActionSchema>;

// Union of all data table actions
export const DataTableActionPayloadSchema = z.discriminatedUnion("actionType", [
   DataTableOpenActionSchema
]);

export type DataTableActionPayload = z.infer<
   typeof DataTableActionPayloadSchema
>;

// ============================================================================
// Universal Artifact Action Union
// ============================================================================

/**
 * ArtifactAction: Discriminated union of all possible artifact actions.
 * Backend emits these; frontend stores replay them.
 *
 * Contract note: today only the Notebook* actions are replayed live by the
 * frontend notebook editor. The chart/data-table actions are emitted by
 * backend tools and persisted, but the UI reacts to chart/data-table changes
 * via artifact metadata (e.g. chart refreshToken) instead — keep them in the
 * contract for persistence fidelity until live replay is implemented or the
 * emitters are removed.
 */
export const ArtifactActionSchema = z.discriminatedUnion("actionType", [
   NotebookUpsertBlockActionSchema,
   NotebookPatchBlockContentActionSchema,
   NotebookSetBlockOutputActionSchema,
   NotebookRemoveBlockActionSchema,
   NotebookUpdateMetadataActionSchema,
   ChartUpdateConfigActionSchema,
   ChartSetDataActionSchema,
   DataTableOpenActionSchema
]);

export type ArtifactAction = z.infer<typeof ArtifactActionSchema>;

// ============================================================================
// Helper Types for Action Handling
// ============================================================================

/**
 * Type guard to check if an action targets notebooks.
 */
export function isNotebookAction(
   action: ArtifactAction
): action is NotebookActionPayload {
   const notebookActions: ArtifactActionType[] = [
      "upsertBlock",
      "patchBlockContent",
      "setBlockOutput",
      "removeBlock",
      "updateMetadata"
   ];
   return notebookActions.includes(action.actionType as ArtifactActionType);
}

/**
 * Type guard to check if an action targets charts.
 */
export function isChartAction(
   action: ArtifactAction
): action is ChartActionPayload {
   const chartActions: ArtifactActionType[] = [
      "updateChartConfig",
      "setChartData"
   ];
   return chartActions.includes(action.actionType as ArtifactActionType);
}

/**
 * Type guard to check if an action targets data tables.
 */
export function isDataTableAction(
   action: ArtifactAction
): action is DataTableActionPayload {
   const dataTableActions: ArtifactActionType[] = ["openDataTable"];
   return dataTableActions.includes(action.actionType as ArtifactActionType);
}
