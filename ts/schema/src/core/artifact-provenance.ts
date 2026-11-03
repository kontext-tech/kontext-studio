import { z } from "zod";

import { TriggerActorModelSchema } from "./domains/jobs/types.js";

/**
 * How an artifact was produced.
 *
 * Deliberately a coarse production-channel taxonomy; `ArtifactProvenance.createdBy`
 * carries *who* produced it (agent kind vs. end user), so e.g. an agent-driven
 * notebook block run and a user's notebook "Run" click share
 * `origin: "notebook_run"` but differ in `createdBy`.
 */
export const ArtifactOriginSchema = z
   .enum([
      "upload",
      "sql_query",
      "agent_python",
      "notebook_run",
      "chart_compose"
   ])
   .describe(
      "How an artifact was produced: uploaded raw by a user, created by SQL " +
         "query results, produced by an agent-driven managed Python run, " +
         "produced by a notebook block execution, or composed as a chart"
   );

export type ArtifactOrigin = z.infer<typeof ArtifactOriginSchema>;
export const ArtifactOrigin = ArtifactOriginSchema.enum;

/**
 * Provenance of an artifact: how it was produced and by whom.
 *
 * Keeps agent-generated artifacts (SQL handles, notebook runs, future
 * `agent_python` outputs) distinguishable from raw uploads across chats,
 * artifact surfaces, and the lakehouse, and gives every produced table a
 * stable path back to the run/speech that created it.
 */
export const ArtifactProvenanceSchema = z
   .object({
      origin: ArtifactOriginSchema.describe("How this artifact was produced"),
      createdBy: TriggerActorModelSchema.nullish().describe(
         "Actor that produced the artifact (agent kind or user)"
      ),
      executionRunId: z
         .string()
         .nullish()
         .describe(
            "Managed execution run that produced the artifact (UUID-style run id)"
         ),
      chatSessionId: z
         .string()
         .nullish()
         .describe("Chat session the producing run belongs to (UUID-style id)"),
      blockId: z
         .string()
         .nullish()
         .describe(
            "Notebook block that produced or owns the artifact (UUID-style id)"
         ),
      identityKey: z
         .string()
         .nullish()
         .describe(
            "Result identity key (hash of the normalized SQL + execution scope) " +
               "shared with the shared session identity index; not a derivation lineage"
         )
   })
   .describe(
      "Provenance of an artifact: how it was produced and by whom, so " +
         "agent-generated artifacts remain distinguishable from uploaded ones"
   );

export type ArtifactProvenance = z.infer<typeof ArtifactProvenanceSchema>;
