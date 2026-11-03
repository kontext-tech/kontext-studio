import { z } from "zod";

const unknownRecordSchema = z.record(z.string(), z.unknown());
const defaultCapabilities = {
   supportsSync: true,
   supportsSearch: true,
   supportsQuery: false,
   supportsQueryPushdown: false,
   supportsDuckdbFederation: false,
   supportsMaterialization: false,
   supportsWrite: false
} as const;

export const CatalogSourceCategorySchema = z.enum(["lakehouse", "sql", "api"]);

export type CatalogSourceCategory = z.infer<typeof CatalogSourceCategorySchema>;
export const CatalogSourceCategory = CatalogSourceCategorySchema.enum;

export const CatalogConnectionAuthTypeSchema = z.enum([
   "none",
   "username_password",
   "secret_ref",
   "api_key",
   "oauth_client_credentials",
   "service_account"
]);

export type CatalogConnectionAuthType = z.infer<
   typeof CatalogConnectionAuthTypeSchema
>;
export const CatalogConnectionAuthType = CatalogConnectionAuthTypeSchema.enum;

export const CatalogExecutionModeSchema = z.enum([
   "native_pushdown",
   "duckdb_federated",
   "materialized"
]);

export type CatalogExecutionMode = z.infer<typeof CatalogExecutionModeSchema>;
export const CatalogExecutionMode = CatalogExecutionModeSchema.enum;

export const CatalogConnectionKindSchema = z.enum([
   "internal",
   "external",
   "managed"
]);

export type CatalogConnectionKind = z.infer<typeof CatalogConnectionKindSchema>;
export const CatalogConnectionKind = CatalogConnectionKindSchema.enum;

export const CatalogSourceKindSchema = z.enum([
   "iceberg_internal",
   "duckdb_external",
   "mysql_external",
   "oracle_external",
   "postgresql_external",
   "sqlserver_external",
   "snowflake_external",
   "bigquery_external",
   "teradata_external",
   "sqlite_external",
   "http_api_external"
]);

export type CatalogSourceKind = z.infer<typeof CatalogSourceKindSchema>;
export const CatalogSourceKind = CatalogSourceKindSchema.enum;

export const CatalogEntityTypeSchema = z.enum(["table", "view"]);

export type CatalogEntityType = z.infer<typeof CatalogEntityTypeSchema>;
export const CatalogEntityType = CatalogEntityTypeSchema.enum;

export const CatalogConnectionCapabilitiesSchema = z
   .object({
      supportsSync: z.boolean().default(true),
      supportsSearch: z.boolean().default(true),
      supportsQuery: z.boolean().default(false),
      supportsQueryPushdown: z.boolean().default(false),
      supportsDuckdbFederation: z.boolean().default(false),
      supportsMaterialization: z.boolean().default(false),
      supportsWrite: z.boolean().default(false)
   })
   .describe("Capabilities exposed by a catalog provider");

export type CatalogConnectionCapabilities = z.infer<
   typeof CatalogConnectionCapabilitiesSchema
>;

export const CatalogConnectionConfigSchema = z
   .object({
      warehousePath: z.string().nullable().optional(),
      databasePath: z.string().nullable().optional(),
      host: z.string().nullable().optional(),
      port: z.number().int().nullable().optional(),
      databaseName: z.string().nullable().optional(),
      username: z.string().nullable().optional(),
      instanceName: z.string().nullable().optional(),
      serviceName: z.string().nullable().optional(),
      account: z.string().nullable().optional(),
      warehouse: z.string().nullable().optional(),
      role: z.string().nullable().optional(),
      project: z.string().nullable().optional(),
      location: z.string().nullable().optional(),
      defaultNamespace: z.string().nullable().optional(),
      options: unknownRecordSchema.default({})
   })
   .describe("Provider-specific catalog connection configuration");

export type CatalogConnectionConfig = z.infer<
   typeof CatalogConnectionConfigSchema
>;

export const CatalogConnectionSchema = z
   .object({
      id: z.guid().optional(),
      projectId: z.guid().nullable().optional(),
      providerKind: z.lazy(() => CatalogSourceKindSchema),
      connectionKind: z.lazy(() => CatalogConnectionKindSchema),
      displayName: z.string().max(255),
      description: z.string().max(2048).nullable().optional(),
      enabled: z.boolean().default(true),
      ownerId: z.guid().nullable().optional(),
      sourceCategory: z
         .lazy(() => CatalogSourceCategorySchema)
         .nullable()
         .optional(),
      authType: z
         .lazy(() => CatalogConnectionAuthTypeSchema)
         .nullable()
         .optional(),
      executionMode: z
         .lazy(() => CatalogExecutionModeSchema)
         .nullable()
         .optional(),
      config: z.lazy(() => CatalogConnectionConfigSchema),
      secretRef: z.string().max(512).nullable().optional(),
      secretConfigured: z.boolean().default(false),
      capabilities: z
         .lazy(() => CatalogConnectionCapabilitiesSchema)
         .default(defaultCapabilities),
      healthStatus: z.string().max(64).nullable().optional(),
      lastValidatedAt: z.iso.datetime({ offset: true }).nullable().optional(),
      validationError: z.string().max(4096).nullable().optional(),
      syncMode: z.string().max(64).nullable().optional(),
      syncSchedule: z.string().max(256).nullable().optional(),
      lastSyncedAt: z.iso.datetime({ offset: true }).nullable().optional(),
      lastSyncStatus: z.string().max(64).nullable().optional(),
      lastSyncError: z.string().max(4096).nullable().optional(),
      catalogRevision: z
         .string()
         .max(64)
         .nullable()
         .optional()
         .describe(
            "Content hash of the normalized snapshot; changes only when the materialized catalog shape changes"
         ),
      isQueryReady: z.boolean().default(false),
      readinessReason: z.string().max(64).nullable().optional()
   })
   .describe("Secret-safe catalog connection");

export type CatalogConnection = z.infer<typeof CatalogConnectionSchema>;

export const CatalogConnectionRequestSchema = z
   .object({
      providerKind: z.lazy(() => CatalogSourceKindSchema),
      connectionKind: z.lazy(() => CatalogConnectionKindSchema),
      displayName: z.string().max(255),
      description: z.string().max(2048).nullable().optional(),
      enabled: z.boolean().default(true),
      sourceCategory: z
         .lazy(() => CatalogSourceCategorySchema)
         .nullable()
         .optional(),
      authType: z
         .lazy(() => CatalogConnectionAuthTypeSchema)
         .nullable()
         .optional(),
      executionMode: z
         .lazy(() => CatalogExecutionModeSchema)
         .nullable()
         .optional(),
      config: z.lazy(() => CatalogConnectionConfigSchema),
      secretRef: z.string().max(512).nullable().optional(),
      secretValue: z.string().max(4096).nullable().optional(),
      syncMode: z.string().max(64).nullable().optional(),
      syncSchedule: z.string().max(256).nullable().optional(),
      capabilities: z
         .lazy(() => CatalogConnectionCapabilitiesSchema)
         .nullable()
         .optional()
   })
   .describe("Create or update catalog connection request");

export type CatalogConnectionRequest = z.infer<
   typeof CatalogConnectionRequestSchema
>;

export const CatalogNamespaceSummarySchema = z
   .object({
      id: z.guid(),
      connectionId: z.guid(),
      name: z.string(),
      displayName: z.string().nullable().optional(),
      entityCount: z.number().int().default(0)
   })
   .describe("Catalog namespace summary");

export type CatalogNamespaceSummary = z.infer<
   typeof CatalogNamespaceSummarySchema
>;

export const CatalogColumnSchema = z
   .object({
      id: z.guid().nullable().optional(),
      entityId: z.guid().nullable().optional(),
      name: z.string(),
      ordinalPosition: z.number().int().nullable().optional(),
      dataType: z.string().nullable().optional(),
      nullable: z.boolean().default(true),
      description: z.string().nullable().optional(),
      metadata: unknownRecordSchema.default({})
   })
   .describe("Normalized catalog column metadata");

export type CatalogColumn = z.infer<typeof CatalogColumnSchema>;

export const CatalogEntitySummarySchema = z
   .object({
      id: z.guid(),
      connectionId: z.guid(),
      namespaceId: z.guid().nullable().optional(),
      namespaceName: z.string(),
      entityName: z.string(),
      displayName: z.string().nullable().optional(),
      entityType: z.lazy(() => CatalogEntityTypeSchema),
      description: z.string().nullable().optional(),
      rowCount: z.number().int().nullable().optional(),
      location: z.string().nullable().optional(),
      columnCount: z.number().int().default(0),
      metadata: unknownRecordSchema.default({})
   })
   .describe("Catalog entity summary");

export type CatalogEntitySummary = z.infer<typeof CatalogEntitySummarySchema>;

export const CatalogEntityDetailSchema = z
   .object({
      entity: z.lazy(() => CatalogEntitySummarySchema),
      columns: z.array(z.lazy(() => CatalogColumnSchema)).default([])
   })
   .describe("Detailed catalog entity including columns");

export type CatalogEntityDetail = z.infer<typeof CatalogEntityDetailSchema>;

export const CatalogSyncStatusSchema = z
   .object({
      connectionId: z.guid(),
      status: z.string(),
      lastSyncedAt: z.iso.datetime({ offset: true }).nullable().optional(),
      entityCount: z.number().int().default(0),
      errorMessage: z.string().nullable().optional(),
      catalogRevision: z
         .string()
         .max(64)
         .nullable()
         .optional()
         .describe("Content hash of the synchronized snapshot")
   })
   .describe("Catalog sync status");

export type CatalogSyncStatus = z.infer<typeof CatalogSyncStatusSchema>;

export const CatalogConnectionValidationResultSchema = z
   .object({
      connectionId: z.guid(),
      status: z.string(),
      validatedAt: z.iso.datetime({ offset: true }),
      message: z.string().max(2048).nullable().optional(),
      errorMessage: z.string().max(4096).nullable().optional()
   })
   .describe("Catalog connection validation result");

export type CatalogConnectionValidationResult = z.infer<
   typeof CatalogConnectionValidationResultSchema
>;

export const CatalogProviderDefinitionSchema = z
   .object({
      providerKind: z.lazy(() => CatalogSourceKindSchema),
      connectionKind: z.lazy(() => CatalogConnectionKindSchema),
      displayName: z.string(),
      sourceCategory: z
         .lazy(() => CatalogSourceCategorySchema)
         .nullable()
         .optional(),
      authTypes: z
         .array(z.lazy(() => CatalogConnectionAuthTypeSchema))
         .default([]),
      executionModes: z
         .array(z.lazy(() => CatalogExecutionModeSchema))
         .default([]),
      capabilities: z
         .lazy(() => CatalogConnectionCapabilitiesSchema)
         .default(defaultCapabilities)
   })
   .describe("Catalog provider definition");

export type CatalogProviderDefinition = z.infer<
   typeof CatalogProviderDefinitionSchema
>;
