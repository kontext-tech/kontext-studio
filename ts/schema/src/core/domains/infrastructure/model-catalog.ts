import { z } from "zod";

export const ModelAdapterTypeSchema = z.enum([
   "openai_compatible",
   "openai_native",
   "anthropic_native",
   "gemini_native",
   "bedrock_native",
   "ollama_native",
   "azure_native",
   "google_vertex_native"
]);

export type ModelAdapterType = z.infer<typeof ModelAdapterTypeSchema>;
export const ModelAdapterType = ModelAdapterTypeSchema.enum;

export const ModelConnectionSourceTypeSchema = z.enum([
   "user_managed",
   "platform_managed"
]);

export type ModelConnectionSourceType = z.infer<
   typeof ModelConnectionSourceTypeSchema
>;
export const ModelConnectionSourceType = ModelConnectionSourceTypeSchema.enum;

export const ModelConnectionKindSchema = z.enum([
   "lm_studio",
   "ollama",
   "ollama_cloud",
   "openai",
   "anthropic",
   "openai_compatible",
   "openrouter",
   "deepseek",
   "mistral",
   "gemini",
   "google_vertex",
   "azure_openai",
   "bedrock",
   "platform"
]);

export type ModelConnectionKind = z.infer<typeof ModelConnectionKindSchema>;
export const ModelConnectionKind = ModelConnectionKindSchema.enum;

export const ModelValidationStateSchema = z.enum([
   "unknown",
   "pending",
   "valid",
   "invalid"
]);

export type ModelValidationState = z.infer<typeof ModelValidationStateSchema>;
export const ModelValidationState = ModelValidationStateSchema.enum;

export const ModelAvailabilitySchema = z.enum(["available", "unavailable"]);

export type ModelAvailability = z.infer<typeof ModelAvailabilitySchema>;
export const ModelAvailability = ModelAvailabilitySchema.enum;

export const ModelReasoningEffortSchema = z.enum(["low", "medium", "high"]);

export type ModelReasoningEffort = z.infer<typeof ModelReasoningEffortSchema>;

export const ModelProviderConfigFieldSchema = z.enum([
   "endpointBaseUrl",
   "region",
   "projectId",
   "location",
   "apiVersion"
]);

export type ModelProviderConfigField = z.infer<
   typeof ModelProviderConfigFieldSchema
>;
export const ModelProviderConfigField = ModelProviderConfigFieldSchema.enum;

export const ModelCredentialRefFieldSchema = z.enum([
   "apiKeyRef",
   "accessKeyIdRef",
   "secretAccessKeyRef",
   "sessionTokenRef"
]);

export type ModelCredentialRefField = z.infer<
   typeof ModelCredentialRefFieldSchema
>;
export const ModelCredentialRefField = ModelCredentialRefFieldSchema.enum;

export const ModelProviderDefinitionSchema = z
   .object({
      connectionKind: z.lazy(() => ModelConnectionKindSchema),
      displayName: z.string().max(128),
      adapterType: z.lazy(() => ModelAdapterTypeSchema),
      description: z.string().max(512).nullable().optional(),
      defaultEndpointBaseUrl: z.string().max(512).nullable().optional(),
      requiredConfigFields: z
         .array(z.lazy(() => ModelProviderConfigFieldSchema))
         .default([]),
      optionalConfigFields: z
         .array(z.lazy(() => ModelProviderConfigFieldSchema))
         .default([]),
      requiredCredentialFields: z
         .array(z.lazy(() => ModelCredentialRefFieldSchema))
         .default([]),
      optionalCredentialFields: z
         .array(z.lazy(() => ModelCredentialRefFieldSchema))
         .default([]),
      supportsCustomEndpoint: z.boolean().default(false),
      defaultModelId: z.string().max(256).nullable().optional(),
      modelEnvVar: z.string().max(64).nullable().optional(),
      apiKeyEnvVar: z.string().max(64).nullable().optional(),
      apiBaseEnvVar: z.string().max(64).nullable().optional(),
      apiVersionEnvVar: z.string().max(64).nullable().optional(),
      projectIdEnvVar: z.string().max(64).nullable().optional(),
      locationEnvVar: z.string().max(64).nullable().optional(),
      regionEnvVar: z.string().max(64).nullable().optional()
   })
   .describe("Executable model provider definition");

export type ModelProviderDefinition = z.infer<
   typeof ModelProviderDefinitionSchema
>;

export const ModelConnectionProviderConfigSchema = z
   .object({
      endpointBaseUrl: z.string().max(512).nullable().optional(),
      providerModelName: z.string().max(256).nullable().optional(),
      region: z.string().max(128).nullable().optional(),
      projectId: z.string().max(256).nullable().optional(),
      location: z.string().max(128).nullable().optional(),
      apiVersion: z.string().max(64).nullable().optional()
   })
   .describe("Executable model provider configuration");

export type ModelConnectionProviderConfig = z.infer<
   typeof ModelConnectionProviderConfigSchema
>;

export const ModelConnectionCredentialRefsSchema = z
   .object({
      apiKeyRef: z.string().max(512).nullable().optional(),
      accessKeyIdRef: z.string().max(512).nullable().optional(),
      secretAccessKeyRef: z.string().max(512).nullable().optional(),
      sessionTokenRef: z.string().max(512).nullable().optional()
   })
   .describe("Secret references for executable model connections");

export type ModelConnectionCredentialRefs = z.infer<
   typeof ModelConnectionCredentialRefsSchema
>;

export const ModelConnectionSchema = z
   .object({
      id: z.guid().optional(),
      sourceType: z.lazy(() => ModelConnectionSourceTypeSchema),
      adapterType: z.lazy(() => ModelAdapterTypeSchema),
      connectionKind: z.lazy(() => ModelConnectionKindSchema),
      canonicalModelId: z.string().max(256),
      displayName: z.string().max(256),
      providerConfig: z
         .lazy(() => ModelConnectionProviderConfigSchema)
         .nullable()
         .optional(),
      credentialRefs: z
         .lazy(() => ModelConnectionCredentialRefsSchema)
         .nullable()
         .optional(),
      providerModelName: z.string().max(256).nullable().optional(),
      endpointBaseUrl: z.string().max(512).nullable().optional(),
      secretRef: z.string().max(512).nullable().optional(),
      secretConfigured: z.boolean().default(false),
      reasoningEffort: z
         .lazy(() => ModelReasoningEffortSchema)
         .nullable()
         .optional(),
      isDefault: z.boolean().default(false),
      enabled: z.boolean().default(true),
      validationState: z
         .lazy(() => ModelValidationStateSchema)
         .default("unknown"),
      ownerId: z.guid().nullable().optional()
   })
   .describe("Executable model connection");

export type ModelConnection = z.infer<typeof ModelConnectionSchema>;

export const ModelCatalogEntrySchema = z
   .object({
      selectionId: z.guid(),
      canonicalModelId: z.string().max(256),
      sourceType: z.lazy(() => ModelConnectionSourceTypeSchema),
      displayName: z.string().max(256),
      adapterType: z.lazy(() => ModelAdapterTypeSchema),
      connectionKind: z.lazy(() => ModelConnectionKindSchema),
      providerConfig: z
         .lazy(() => ModelConnectionProviderConfigSchema)
         .nullable()
         .optional(),
      providerModelName: z.string().max(256).nullable().optional(),
      endpointBaseUrl: z.string().max(512).nullable().optional(),
      reasoningEffort: z
         .lazy(() => ModelReasoningEffortSchema)
         .nullable()
         .optional(),
      reasoningSupported: z.boolean().default(false),
      availability: z.lazy(() => ModelAvailabilitySchema).default("available"),
      validationState: z
         .lazy(() => ModelValidationStateSchema)
         .default("unknown"),
      enabled: z.boolean().default(true)
   })
   .describe("Executable model catalog entry");

export type ModelCatalogEntry = z.infer<typeof ModelCatalogEntrySchema>;
