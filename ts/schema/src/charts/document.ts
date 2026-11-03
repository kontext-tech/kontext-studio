/**
 * Chart Document Schema for .chart files in the data lake
 *
 * Provides a reusable schema for chart configuration that supports:
 * - Embedded data (for standalone charts)
 * - References to data tables in the data lake
 * - Priority given to the external data reference if both embedded data and ref are present
 */

import { z } from "zod";
import { ArtifactOriginSchema } from "../core/artifact-provenance";
import { TriggerActorTypeSchema } from "../core/domains/jobs/types.js";
import { ChartSpecSchema } from "./spec";

// =============================================================================
// Chart Document Schema
// =============================================================================

/**
 * Chart document - complete schema for .chart files
 * Can reference data from the data lake or contain embedded data
 * Shares the same chart configuration as chart blocks
 */
export const ChartDocumentMetadataSchema = z
   .object({
      description: z
         .string()
         .max(2048)
         .optional()
         .describe("Description of the chart and its purpose"),
      tags: z
         .array(z.string())
         .optional()
         .describe("Tags for categorizing and searching charts"),
      author: z.string().optional().describe("Author of the chart"),
      createdAt: z.iso
         .datetime({ offset: true })
         .describe("Chart creation timestamp"),
      modifiedAt: z.iso
         .datetime({ offset: true })
         .describe("Last modification timestamp"),
      version: z
         .string()
         .optional()
         .describe("Semantic version of the chart document"),
      notebookId: z
         .guid()
         .optional()
         .describe("Notebook file ID that generated or owns this chart"),
      querySessionId: z
         .guid()
         .optional()
         .describe("Query session ID associated with this chart's data"),
      chatSessionId: z
         .guid()
         .optional()
         .describe("AI chat session ID that generated this chart"),
      origin: ArtifactOriginSchema.optional().describe(
         "Origin channel of this chart (who/how it was composed)"
      ),
      createdByType: TriggerActorTypeSchema.optional().describe(
         "Actor type that produced this chart"
      ),
      createdById: z
         .string()
         .optional()
         .describe("Actor identifier that produced this chart"),
      executionRunId: z
         .string()
         .optional()
         .describe("Managed execution run that produced this chart's data"),
      identityKey: z
         .string()
         .optional()
         .describe(
            "Result identity key of the data behind this chart, when known; not a derivation lineage"
         )
   })
   .describe("Metadata for chart document");

/**
 * Main chart document schema
 * Includes chart configuration and data table specification via ChartSpec
 * Note: The chart document has no id field - the file_id serves as the chart identifier
 */
export const ChartDocumentSchema = z
   .object({
      name: z.string().min(1).max(200).describe("Name of the chart"),
      metadata: ChartDocumentMetadataSchema.optional().describe(
         "Optional chart metadata"
      )
   })
   .extend(ChartSpecSchema.shape)
   .describe(
      "Chart document for .chart files with configuration and data table specification. The file ID serves as the chart identifier."
   );

export type ChartDocument = z.infer<typeof ChartDocumentSchema>;
export type ChartDocumentMetadata = z.infer<typeof ChartDocumentMetadataSchema>;
