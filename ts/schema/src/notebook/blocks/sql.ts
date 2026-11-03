import { z } from "zod";
import { DataRefSchema, InlineDataSchema } from "../../core/data";
import { BaseBlockSchema } from "../base";

export const SqlBlockDataSchema = z
   .object({
      title: z
         .string()
         .max(100)
         .optional()
         .describe(
            "Optional title for the SQL block to provide context about the query purpose"
         ),
      alias: z
         .string()
         .regex(/^[A-Za-z_][A-Za-z0-9_]{0,63}$/)
         .optional()
         .describe(
            "Notebook-scoped alias for this block's result table, loadable from Python blocks via kontext.load_data(alias). Free-form snake_case name or auto-assigned df_N; bound only when saved with results and unique within the notebook."
         ),
      code: z
         .string()
         .max(50000)
         .describe(
            "SQL query code to be executed against the selected catalog scope. May be empty for a freshly inserted block."
         ),
      dataRef: DataRefSchema.optional().describe(
         "Reference to the data table file (e.g., .dt) representing the results of this query"
      ),
      inlineData: InlineDataSchema.optional().describe(
         "Inline results of the query execution"
      ),
      showResults: z
         .boolean()
         .optional()
         .describe("Flag to show or hide the SQL results table"),
      // Runtime state (not persisted to document)
      isExecuting: z
         .boolean()
         .optional()
         .describe("Runtime flag indicating if query is currently executing"),
      isEditorOpen: z
         .boolean()
         .optional()
         .describe("Runtime flag indicating if the SQL editor drawer is open"),
      lastExecuted: z.coerce
         .number()
         .int()
         .optional()
         .describe("format: int64 | Timestamp of last query execution"),
      executionRunId: z
         .string()
         .optional()
         .describe(
            "Run id of the last managed execution that produced the results"
         )
   })
   .describe("Data schema for SQL block configuration and execution state");

export const SqlBlockSchema = BaseBlockSchema.extend({
   type: z.literal("sql"),
   data: SqlBlockDataSchema
}).describe(
   "SQL block for database queries with execution state and catalog references"
);

export type SqlBlock = z.infer<typeof SqlBlockSchema>;
export type SqlBlockData = z.infer<typeof SqlBlockDataSchema>;
