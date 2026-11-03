import { z } from "zod";
export * from "./model-catalog.js";
export * from "./catalog.js";
import {
   ModelAdapterTypeSchema,
   ModelConnectionKindSchema
} from "./model-catalog.js";

/**
 * Core Domain: Infrastructure
 *
 * Source: backend/Kontext.Data/ViewModels/FoundationModel.cs
 */

export const FoundationModelSchema = z
   .object({
      canonicalModelId: z.string(),
      name: z.string(),
      vendor: z.string(),
      adapterType: z.lazy(() => ModelAdapterTypeSchema),
      description: z.string().nullable().optional(),
      capabilities: z.array(z.string()).default([]),
      maxTokens: z.number().int().nullable().optional(),
      reasoningSupported: z.boolean().default(false),
      supportedConnectionKinds: z
         .array(z.lazy(() => ModelConnectionKindSchema))
         .default([]),
      providerModelAliases: z.record(z.string(), z.string()).default({})
   })
   .describe("Foundation Model");

export type FoundationModel = z.infer<typeof FoundationModelSchema>;

// Export config schemas (culture info, file type configuration)
export * from "./config.js";
