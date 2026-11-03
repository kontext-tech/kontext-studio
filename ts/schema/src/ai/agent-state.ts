import { z } from "zod";
import { AttachedDataSourceSchema } from "./chat-attachment-context";
import { ArtifactTypeSchema } from "./types";

/**
 * Agent session state schemas for Agno team/agent context
 *
 * These schemas define the structure of data stored in Agno's RunContext.session_state
 * dictionary, which is shared across all team members and persisted to the database.
 *
 * Shared session state is durable-only:
 * - transient payloads stay in local run state and are never stored here
 * - artifactsById contains only permanent artifact descriptors
 * - artifactAliases maps promoted local handles to permanent artifact IDs
 *
 * Naming conventions:
 * - *Schema: Zod schema definitions
 * - No *Request/*Response suffixes (these are not API DTOs, but internal state structures)
 */

// ============================================================================
// Data State Entry
// ============================================================================

/**
 * Type of data entry stored in session state
 * - "persistent": File-backed data table (.dt file)
 * - "transient": In-memory data table (not yet promoted to file)
 */
export const DataStateTypeSchema = z
   .enum(["persistent", "transient"])
   .describe("Type of data entry in session state");

export const DataStateType = DataStateTypeSchema.enum;

export type DataStateType = z.infer<typeof DataStateTypeSchema>;

/**
 * Data-state entry in Agno session state
 *
 * Tracks data tables created during a team/agent session for cross-agent
 * coordination (e.g., SQL Agent creates data, Chart Agent references it).
 *
 * When a transient data table is promoted to a persistent file:
 * - `id` remains the original transient UUID for backward compatibility
 * - `persistentId` stores the new file ID
 * - `type` changes from "transient" to "persistent"
 * This allows lookups by either the original transient ID or the file ID.
 */
export const DataStateEntrySchema = z
   .object({
      id: z.string().describe("Data ID (persistent file ID or transient UUID)"),
      type: DataStateTypeSchema.describe(
         "Whether this is a persistent file or transient in-memory data table"
      ),
      persistentId: z
         .string()
         .nullable()
         .optional()
         .describe(
            "Persistent file ID after promotion (if this data table was promoted from transient)"
         ),
      sql: z
         .string()
         .nullable()
         .optional()
         .describe("SQL query that generated this data table (if applicable)")
   })
   .describe(
      "Data-state entry in Agno session state for cross-agent coordination"
   );

export type DataStateEntry = z.infer<typeof DataStateEntrySchema>;

// ============================================================================
// Artifact State Entry
// ============================================================================

/**
 * Artifact entry in Agno session state
 *
 * Tracks artifacts (Notebooks, Charts) created or modified during a session.
 */
export const ArtifactStateEntrySchema = z
   .object({
      id: z.string().describe("Artifact ID (file ID)"),
      type: ArtifactTypeSchema.describe("Type of artifact (Notebook, Chart)"),
      title: z.string().describe("Display title of the artifact"),
      createdAt: z.string().describe("ISO timestamp of creation"),
      modifiedAt: z
         .string()
         .nullable()
         .optional()
         .describe("ISO timestamp of last modification")
   })
   .describe(
      "Artifact entry in Agno session state for cross-agent coordination"
   );

export type ArtifactStateEntry = z.infer<typeof ArtifactStateEntrySchema>;

/**
 * Durable artifact descriptor stored in shared session state.
 */
export const SharedArtifactDescriptorSchema = z
   .object({
      artifactId: z.string().describe("Durable artifact ID"),
      artifactType: ArtifactTypeSchema.describe("Artifact type"),
      title: z.string().nullable().optional().describe("Display title"),
      sql: z
         .string()
         .nullable()
         .optional()
         .describe(
            "Source SQL for data-table artifacts, kept for reference and re-derivation"
         ),
      identityKey: z
         .string()
         .nullable()
         .optional()
         .describe(
            "Result identity key (hash of the normalized SQL + execution scope) used to " +
               "reuse the same durable artifact when the identical query is re-executed " +
               "in the session; not a derivation lineage"
         ),
      createdAt: z
         .string()
         .nullable()
         .optional()
         .describe("ISO timestamp of creation"),
      modifiedAt: z
         .string()
         .nullable()
         .optional()
         .describe("ISO timestamp of last update"),
      rowCount: z
         .number()
         .int()
         .nullable()
         .optional()
         .describe("Row count summary for data tables"),
      columnNames: z
         .array(z.string())
         .nullable()
         .optional()
         .describe("Column-name summary for data tables")
   })
   .describe("Durable artifact descriptor in shared agent session state");

export type SharedArtifactDescriptor = z.infer<
   typeof SharedArtifactDescriptorSchema
>;

// ============================================================================
// Agent Session State
// ============================================================================

/**
 * Complete session state structure for Agno teams
 *
 * This is the root dictionary stored in RunContext.session_state and
 * persisted to the database across agent interactions.
 */
export const AgentSessionStateSchema = z
   .object({
      version: z
         .number()
         .int()
         .default(1)
         .describe("Version of the durable shared session-state structure"),
      artifactsById: z
         .record(z.string(), SharedArtifactDescriptorSchema)
         .default({})
         .describe(
            "Durable artifact descriptors keyed by permanent artifact ID"
         ),
      dataIdentityIndex: z
         .record(z.string(), z.string())
         .default({})
         .describe(
            "Index from result identity key to durable artifact ID, used for " +
               "reuse/dedupe of identical query results within the session; " +
               "not a derivation lineage"
         ),
      artifactAliases: z
         .record(z.string(), z.string())
         .default({})
         .describe(
            "Promoted local-handle aliases pointing at durable artifact IDs"
         ),
      attachedDataSources: z
         .array(AttachedDataSourceSchema)
         .default([])
         .describe(
            "Structured attached-file data sources available to the chat session"
         )
   })
   .describe("Session state structure for Agno team agents");

export type AgentSessionState = z.infer<typeof AgentSessionStateSchema>;
