import { z } from "zod";
import { ArtifactProvenanceSchema } from "../../core/artifact-provenance";
import { DataTableSchema } from "../../core/data";
import { TriggerActorModelSchema } from "../../core/domains/jobs/types.js";

// Core tabular primitives shared across API and Notebook

export const QueryResponseSchema = z
   .object({
      result: DataTableSchema.nullable()
         .optional()
         .describe("Single data table result set"),
      totalExecutionTimeMs: z
         .number()
         .nullable()
         .optional()
         .describe("Total execution time for all queries"),
      success: z
         .boolean()
         .optional()
         .describe("Whether execution was successful"),
      errorMessage: z
         .string()
         .nullable()
         .optional()
         .describe("Error message if execution failed"),
      dataId: z
         .guid()
         .nullable()
         .optional()
         .describe("Resource ID where results are stored, if applicable"),
      sql: z
         .string()
         .nullable()
         .optional()
         .describe("The SQL query that generated this data (if applicable)"),
      provenance: z
         .lazy(() => ArtifactProvenanceSchema)
         .nullable()
         .optional()
         .describe(
            "Provenance of the produced result (origin, actor, execution run) " +
               "when the execution produced or stored result data"
         ),
      alias: z
         .string()
         .nullable()
         .optional()
         .describe(
            "Notebook-scoped alias bound to this result when the execution " +
               "originated from a notebook SQL block; null when no notebook " +
               "context was provided"
         )
   })
   .describe("Complete query execution response");

export const QueryExecRequestSchema = z
   .object({
      projectId: z.guid().describe("Project ID for the query execution"),
      sessionId: z.string().describe("Session ID for the query execution"),
      sqlQuery: z.string().describe("SQL query to execute"),
      queryTimeoutSeconds: z
         .number()
         .optional()
         .describe("Query timeout in seconds"),
      triggeredBy: z
         .lazy(() => TriggerActorModelSchema)
         .optional()
         .describe("Actor or artifact that triggered this query"),
      chatSessionId: z
         .guid()
         .optional()
         .describe(
            "Optional chat session ID to associate with the query execution"
         ),
      parentRunId: z
         .guid()
         .optional()
         .describe("Optional parent execution run ID for hierarchical linkage"),
      storeResultName: z
         .string()
         .optional()
         .describe(
            "Optional name to use when storing query results as a resource file"
         ),
      storeResultAsResource: z
         .boolean()
         .optional()
         .default(false)
         .describe("Whether to store the query response as a resource file"),
      storeResultThresholdRows: z
         .number()
         .int()
         .optional()
         .describe(
            "Threshold row count to automatically store results as a resource file"
         ),
      existingDataId: z
         .guid()
         .optional()
         .describe(
            "Existing data table ID to update if re-running a query and storeResultAsResource is true"
         ),
      notebookId: z
         .guid()
         .optional()
         .describe(
            "Notebook ID when the query runs on behalf of a notebook SQL block; " +
               "enables server-side alias binding for the block's result"
         ),
      blockId: z
         .string()
         .optional()
         .describe(
            "Notebook block ID accompanying notebookId; identifies which SQL " +
               "block's result the alias binds to"
         )
   })
   .describe("Request model for query execution");

export type QueryResponse = z.infer<typeof QueryResponseSchema>;
export type QueryExecRequest = z.infer<typeof QueryExecRequestSchema>;
