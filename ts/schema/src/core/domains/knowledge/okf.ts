import { z } from "zod";

const IsoDateTimeStringSchema = z.string().datetime({ offset: true });

export const OkfProvenanceActorSchema = z.object({
   by: z.string(),
   // OKF §5.2 marks only `by` as REQUIRED. The timestamp is recommended but a
   // consumer MUST NOT reject a concept for a missing optional trust field.
   at: IsoDateTimeStringSchema.optional()
});

export const OkfSourceSchema = z.object({
   // OKF §5.1: `id` is optional (a stable key used only for per-claim footnotes).
   id: z.string().optional(),
   resource: z.string(),
   title: z.string().optional(),
   author: z.string().optional(),
   last_modified: IsoDateTimeStringSchema.optional(),
   usage_count: z.number().int().optional(),
   // OKF §5.1: a single entry MAY carry its own `usage_window` to override the
   // shared top-level one.
   usage_window: z.record(z.string(), z.unknown()).optional()
});

export const OkfAttestationSchema = z.object({
   generated: OkfProvenanceActorSchema.optional(),
   // OKF v0.2 defines `verified` as a list of verification events.
   verified: z.array(OkfProvenanceActorSchema).default([]),
   stale_after: IsoDateTimeStringSchema.optional(),
   sources: z.array(OkfSourceSchema).default([]),
   runtime: z.string().optional(),
   parameters: z.array(z.record(z.string(), z.unknown())).default([]),
   //: OKF §10.2 `computation` — path to a file holding an Attested
   //: Computation, used instead of an inline `# Computation` body fence.
   computation: z.string().optional(),
   executor: z.record(z.string(), z.unknown()).optional(),
   attester: z.record(z.string(), z.unknown()).optional(),
   usage_window: z.record(z.string(), z.unknown()).optional()
});

export const OkfConceptSchema = z
   .object({
      type: z.string(),
      title: z.string().optional(),
      description: z.string().optional(),
      //: Canonical URI of the underlying asset (OKF v0.2 `resource`).
      resource: z.string().optional(),
      tags: z.array(z.string()).default([]),
      status: z.string().optional(),
      //: OKF `timestamp` — ISO 8601 datetime of the last significant change.
      timestamp: IsoDateTimeStringSchema.optional(),
      body: z.string().default(""),
      attestation: OkfAttestationSchema.optional(),
      //: Optional stable identity. OKF itself keys concepts by file path; when
      //: absent, the storage layer derives the id from the file path.
      id: z.string().optional(),
      metadata: z.record(z.string(), z.unknown()).default({})
   })
   // OKF §4.1: consumers MUST preserve unknown keys and MUST NOT reject
   // documents with unrecognized frontmatter fields.
   .catchall(z.unknown());

export type OkfProvenanceActor = z.infer<typeof OkfProvenanceActorSchema>;
export type OkfSource = z.infer<typeof OkfSourceSchema>;
export type OkfAttestation = z.infer<typeof OkfAttestationSchema>;
export type OkfConcept = z.infer<typeof OkfConceptSchema>;
