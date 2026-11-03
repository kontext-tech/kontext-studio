import { z } from "zod";

import { ArtifactOriginSchema } from "./artifact-provenance";
import { TriggerActorTypeSchema } from "./domains/jobs/types.js";

export const DataColumnSchema = z
   .object({
      name: z.string().describe("Column name"),
      type: z.string().describe("Column data type"),
      isNullable: z
         .boolean()
         .nullable()
         .optional()
         .describe("Whether the column can contain null values")
   })
   .describe("Data column metadata");

export const DataTableSchema = z
   .object({
      columns: z
         .array(DataColumnSchema)
         .nullable()
         .optional()
         .describe("Column definitions"),
      rows: z
         .array(z.array(z.any()))
         .nullable()
         .optional()
         .describe("Data rows as arrays of values"),
      rowCount: z
         .number()
         .int()
         .nullable()
         .optional()
         .describe("Total number of rows in the result set")
   })
   .describe("Individual data table result set");

export const DataTableSummarySchema = z
   .object({
      columns: z.array(DataColumnSchema).describe("Column definitions"),
      rowCount: z
         .number()
         .int()
         .describe("Total number of rows in the result set"),
      dataId: z
         .guid()
         .nullable()
         .optional()
         .describe(
            "Optional unique identifier for the external data table file"
         )
   })
   .describe(
      "Summary of a data table providing schema and size info without full row data."
   );

export const CodeLanguageSchema = z
   .enum(["sql", "python"])
   .describe("Language of the query code");

export const CodeLanguage = CodeLanguageSchema.enum;

export const InlineDataMetadataSchema = z
   .object({
      notebookId: z
         .guid()
         .nullable()
         .optional()
         .describe("Notebook file ID that generated or owns this data table"),
      querySessionId: z
         .guid()
         .nullable()
         .optional()
         .describe("Query session ID that produced this data table"),
      chatSessionId: z
         .guid()
         .nullable()
         .optional()
         .describe("AI chat session ID that generated this data table"),
      sql: z
         .string()
         .nullable()
         .optional()
         .describe("SQL statement that produced this data table, when known"),
      createdAt: z.iso
         .datetime({ offset: true })
         .nullable()
         .optional()
         .describe("Timestamp when this data table was persisted"),
      dataPath: z
         .string()
         .nullable()
         .optional()
         .describe(
            "Storage path of the columnar Parquet row store holding the full result; when set, the inline table carries only a bounded preview"
         ),
      rowCount: z
         .number()
         .int()
         .nullable()
         .optional()
         .describe("Total number of rows in the full result row store"),
      origin: ArtifactOriginSchema.nullable()
         .optional()
         .describe(
            "Origin channel of this data table (upload vs SQL vs agent runs)"
         ),
      createdByType: TriggerActorTypeSchema.nullable()
         .optional()
         .describe("Actor type that produced this data table"),
      createdById: z
         .string()
         .nullable()
         .optional()
         .describe("Actor identifier that produced this data table"),
      executionRunId: z
         .string()
         .nullable()
         .optional()
         .describe("Managed execution run that produced this data table"),
      identityKey: z
         .string()
         .nullable()
         .optional()
         .describe(
            "Result identity key (hash of the normalized SQL + execution scope) used for " +
               "reuse/dedupe of identical query results; not a derivation lineage"
         )
   })
   .describe("Provenance metadata for a persisted inline data table");

export const InlineDataSchema = z
   .object({
      title: z.string().describe("Inline data display title"),
      table: DataTableSchema.nullable()
         .optional()
         .describe("Inline data table"),
      metadata: InlineDataMetadataSchema.nullable()
         .optional()
         .describe(
            "Optional provenance metadata describing how this data table was generated"
         )
   })
   .describe(
      "Inline data reflecting query/code execution results or explicit payload."
   );

export const DataRefSchema = z
   .object({
      dataId: z
         .guid()
         .optional()
         .describe("Unique identifier for the data resource when applicable"),
      connectionId: z
         .string()
         .optional()
         .describe("Optional catalog or external connection identifier"),
      tableName: z
         .string()
         .optional()
         .describe("Optional external table or view name"),
      path: z
         .string()
         .optional()
         .describe("Optional path for file-backed external data tables"),
      version: z
         .string()
         .optional()
         .describe("Optional snapshot, version, or revision identifier"),
      code: z
         .string()
         .nullable()
         .optional()
         .describe("The code that generated this data (if applicable)"),
      language: CodeLanguageSchema.nullable()
         .optional()
         .describe("Language of the code that generated this data")
   })
   .describe(
      "Data reference - supports persisted data tables, catalog sources, and external tables"
   );

export type DataColumn = z.infer<typeof DataColumnSchema>;
export type DataTable = z.infer<typeof DataTableSchema>;
export type DataTableSummary = z.infer<typeof DataTableSummarySchema>;
export type InlineData = z.infer<typeof InlineDataSchema>;
export type InlineDataMetadata = z.infer<typeof InlineDataMetadataSchema>;
export type CodeLanguage = z.infer<typeof CodeLanguageSchema>;
export type DataRef = z.infer<typeof DataRefSchema>;
