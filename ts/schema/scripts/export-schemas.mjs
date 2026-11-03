#!/usr/bin/env node

import { mkdirSync, writeFileSync } from "fs";
import { createRequire } from "module";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { z } from "zod";

// Get __dirname equivalent for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const require = createRequire(import.meta.url);
const {
   fixRefsToComponents,
   normalizeSchemaComponents,
   stripTopLevelSchemaIds
} = require("./openapi-normalize.cjs");

import {
   ArtifactActionSchema,
   ChartSetDataActionPayloadSchema,
   ChartSetDataActionSchema,
   ChartUpdateConfigActionPayloadSchema,
   ChartUpdateConfigActionSchema,
   DataTableOpenActionPayloadSchema,
   DataTableOpenActionSchema,
   NotebookPatchBlockContentActionPayloadSchema,
   NotebookPatchBlockContentActionSchema,
   NotebookRemoveBlockActionPayloadSchema,
   NotebookRemoveBlockActionSchema,
   NotebookSetBlockOutputActionPayloadOutputSchema,
   NotebookSetBlockOutputActionPayloadSchema,
   NotebookSetBlockOutputActionSchema,
   NotebookUpdateMetadataActionPayloadSchema,
   NotebookUpdateMetadataActionSchema,
   NotebookUpsertBlockActionPayloadSchema,
   NotebookUpsertBlockActionSchema
} from "../src/ai/actions.js";
import {
   AgentSessionStateSchema,
   ArtifactStateEntrySchema,
   DataStateEntrySchema,
   DataStateTypeSchema,
   SharedArtifactDescriptorSchema
} from "../src/ai/agent-state.js";
import {
   AttachedDataSourceSchema,
   AttachedDataTableSchema,
   ChatAttachmentContextFileSchema,
   ChatAttachmentContextSchema,
   ChatAttachmentContextTableSchema,
   SeedChatAttachmentContextRequestSchema
} from "../src/ai/chat-attachment-context.js";
import {
   ArtifactListResponseSchema,
   ChatSessionArtifactModelSchema,
   ChatSessionModelSchema,
   CreateChatSessionRequestSchema,
   PaginatedChatSessionResponseSchema,
   PythonExecutionApprovalModeSchema,
   UpdateChatSessionRequestSchema
} from "../src/ai/chat-session.js";
import {
   ChatUploadPreparationAcceptedFileSchema,
   ChatUploadPreparationFailureSchema,
   ChatUploadPreparationStatusSchema,
   ChatUploadPreparationStepSchema,
   StartChatUploadPreparationResponseSchema
} from "../src/ai/chat-upload-preparations.js";
import { ExecutePythonScriptRequestSchema } from "../src/ai/python.js";
import {
   ArtifactEventDataSchema,
   ChatErrorSegmentSchema,
   ChatMessageSchema,
   ChatMessageSegmentSchema,
   ChatMessageSegmentTypeSchema,
   ChatMessageStatusSchema,
   ChatMessageTypeSchema,
   ChatObjectSegmentSchema,
   ChatReasoningSegmentSchema,
   ChatRequestSchema,
   ChatTextSegmentSchema,
   ChatToolCallSegmentSchema,
   EventDataSchema,
   ProjectDailyTokenUsageResponseSchema,
   ProjectTokenUsageResponseSchema,
   ReasoningEventDataSchema,
   RunCompletedEventDataSchema,
   RunContentEventDataSchema,
   RunEventSchema,
   RunPausedEventDataSchema,
   RunStartedEventDataSchema,
   SimpleRunEventSchema,
   TokenUsageDailyStatsModelSchema,
   TokenUsageStatsModelSchema,
   ToolCallCompletedEventDataSchema,
   ToolCallSchema,
   ToolCallStartedEventDataSchema,
   ToolCallStateSchema,
   ToolCallStatusSchema
} from "../src/ai/streaming.js";
import {
   BaseToolResultSchema,
   CatalogEntityStatsBatchResultSchema,
   CatalogEntityStatsResultSchema,
   CatalogListingResultSchema,
   CatalogSearchResultSchema,
   ChartBatchResultSchema,
   ChartResultSchema,
   DiscoveryResultSchema,
   DocumentSearchItemSchema,
   ExternalExecutionRequirementSchema,
   KnowledgeProposalResultSchema,
   KnowledgeSearchResultSchema,
   NotebookBatchResultSchema,
   NotebookBlockBatchResultSchema,
   NotebookBlockListResultSchema,
   NotebookBlockResultSchema,
   NotebookDataResultSchema,
   NotebookListResultSchema,
   NotebookMultiBlockResultSchema,
   NotebookMutationResultSchema,
   NotebookResultSchema,
   ProjectResultSchema,
   PythonExecutionTargetTypeSchema,
   PythonExecutionModeSchema,
   PythonExecutionResultSchema,
   PythonSavedTableSchema,
   PythonValidationResultSchema,
   SqlExecutionBatchResultSchema,
   SqlExecutionResultSchema,
   SqlValidationBatchResultSchema,
   SqlValidationResultSchema,
   ToolCallResultSchema,
   ToolExecutionSchema
} from "../src/ai/tool-results.js";
import {
   ArtifactActionTypeSchema,
   ArtifactEventKindSchema,
   ArtifactTypeSchema,
   ToolCallResultTypeSchema
} from "../src/ai/types.js";
import {
   ColumnDataTypeSchema,
   ColumnStatsModelSchema,
   HTTPValidationErrorSchema,
   ValidationErrorLocInnerSchema,
   ValidationErrorResponseSchema,
   ValidationErrorSchema
} from "../src/base.js";
import {
   ChartDocumentMetadataSchema,
   ChartDocumentSchema
} from "../src/charts/document.js";
import {
   AggregateMethodSchema,
   BoxChartConfigLegendSchema,
   BoxChartTypeSchema,
   CHART_SCHEMAS,
   ChartConfigSchema,
   chartGroupConfigSchema,
   ChartSpecSchema,
   chartStackConfigSchema,
   ChartTypeSchema,
   ColorPaletteSchema,
   ConnectNullsObjectSchema,
   ConnectNullsSchema,
   DualAxesChartTypeSchema,
   MarkTypesSchema,
   NumberFormatSchema,
   RadarCoordinateTypeSchema
} from "../src/charts/index.js";
import {
   CatalogEntityCreatedEventDataSchema,
   CatalogEntityDeletedEventDataSchema,
   CatalogEntityUpdatedEventDataSchema,
   FileCreatedEventDataSchema,
   FileDeletedEventDataSchema,
   FileSchemaUpdatedEventDataSchema,
   SimpleFileEventDataSchema
} from "../src/core/domains/events/payloads.js";
import { CORE_DOMAIN_SCHEMAS } from "../src/core/domains/index.js";
import { INLINE_ENUM_REFERENCE_OVERRIDES } from "../src/inline-enum-references.js";
import {
   JobDispatchResponseSchema,
   JobExecutionMessageSchema
} from "../src/core/domains/jobs/execution.js";
import { ProjectStatsModelSchema } from "../src/core/domains/projects/stats.js";
import {
   HealthCheckRequestSchema,
   HealthCheckResponseSchema,
   PingRequestSchema,
   PingResponseSchema
} from "../src/core/health.js";
import {
   ArtifactOriginSchema,
   ArtifactProvenanceSchema,
   CodeLanguageSchema,
   DataColumnSchema,
   DataRefSchema,
   DataTableSchema,
   DataTableSummarySchema,
   InlineDataMetadataSchema,
   InlineDataSchema
} from "../src/core/index.js";
import {
   CatalogEntityDiscoveryModelSchema,
   CatalogEntityMetadataModelSchema,
   CatalogEntitySchemaModelSchema,
   CatalogSearchItemSchema,
   ConsolidateSchemasRequestSchema,
   DataLakeColumnSchema,
   SchemaColumnDefinitionSchema,
   SchemaConsolidationInfoModelSchema,
   SchemaConsolidationResultModelSchema,
   SchemaInfoSchema,
   SuggestObjectNameRequestSchema,
   SuggestObjectNameResultModelSchema,
   TableDiscoveryModelSchema,
   TypePromotionInfoModelSchema
} from "../src/data-lake/catalog-discovery.js";
import {
   ColumnModelSchema,
   FileMetadataModelSchema,
   FileSchemaModelSchema,
   FileStatsModelSchema,
   TableSchemaModelSchema,
   TableStatsModelSchema
} from "../src/data-lake/file-models.js";
import {
   BulkFileIdsRequestSchema,
   CreateFileRequestSchema,
   CreateMultipleFilesResponseSchema,
   ExecuteNotebookPythonRequestSchema,
   FileModelSchema,
   FileNavModelSchema,
   FileSchemaExportModelSchema,
   FileUploadMetadataSchema,
   FileUploadResponseSchema,
   ImportOkfBundleBodySchema,
   PaginatedFileResponseSchema,
   SimpleFileModelSchema,
   StartChatUploadPreparationBodySchema,
   UpdateFileContentBodySchema,
   UpdateFileRequestSchema,
   UpdateFileSchemaRequestSchema,
   UploadFileBodySchema,
   UploadMultipleFilesBodySchema
} from "../src/data-lake/files.js";
import {
   QueryExecRequestSchema,
   QueryResponseSchema
} from "../src/data-lake/query/execution.js";
import {
   CreateQueryRequestSchema,
   CreateQuerySessionRequestSchema,
   CreateQuerySessionResponseSchema,
   PaginatedListOfQuerySessionModelSchema,
   QueryEngineTypeSchema,
   QueryModelSchema,
   QuerySessionModelSchema,
   QuerySessionStatsResponseSchema,
   QuerySessionStatusSchema,
   QuerySessionTableModelSchema,
   SessionInitRequestSchema,
   SessionInitResponseSchema,
   UpdateQuerySessionRequestSchema
} from "../src/data-lake/query/sessions.js";
import { EnumNumericMappings } from "../src/enumMappings.js";
import {
   BLOCK_DATA_SCHEMAS,
   BLOCK_SCHEMAS,
   BlockDataSchema,
   CodeExecutionOutputSchema,
   CodeExecutionOutputTypeSchema,
   CodeImageOutputSchema,
   CodeImageRefOutputSchema,
   CodeJsonOutputSchema,
   CodeResourceOutputSchema,
   CodeRuntimePreferenceSchema,
   CodeTextOutputSchema,
   CounterTypeSchema,
   ListBlockMetaSchema,
   ListItemMetaSchema,
   ListItemSchema,
   ListStyleSchema,
   ImageBlockDataFileSchema,
   NotebookBlockSchema,
   NotebookBlockTypeSchema,
   NotebookDocumentMetadataSchema,
   NotebookDocumentSchema,
   QuoteAlignmentSchema
} from "../src/notebook";

const outDir = join(__dirname, "../src/schemas");
const outFile =
   process.env.KONTEXT_SCHEMA_OUT_FILE ||
   join(outDir, "kontext.models.openapi.json");

// zod's `.describe()` stores descriptions as registry metadata, and the
// `add(schema, { id })` registrations below replace that metadata. Stash the
// import-time descriptions (keyed by component id) before they are lost, then
// re-attach them to the converted components.
const preConversionDescriptions = new Map();
const originalRegistryAdd = z.globalRegistry.add.bind(z.globalRegistry);
z.globalRegistry.add = (schema, metadata) => {
   const existingMetadata = z.globalRegistry.get(schema);
   if (existingMetadata?.description && metadata?.id) {
      preConversionDescriptions.set(metadata.id, existingMetadata.description);
   }
   return originalRegistryAdd(schema, metadata);
};

function registerDefinitions() {
   console.log("🔗 Registering all schemas in global registry...");

   console.log("📦 Registering core domain schemas...");
   CORE_DOMAIN_SCHEMAS.forEach(({ id, schema }) => {
      z.globalRegistry.add(schema, { id });
   });

   // Register project schemas
   z.globalRegistry.add(ProjectStatsModelSchema, { id: "ProjectStatsModel" });

   // Register sql schemas
   z.globalRegistry.add(DataColumnSchema, { id: "DataColumn" });
   z.globalRegistry.add(DataTableSchema, { id: "DataTable" });
   z.globalRegistry.add(DataTableSummarySchema, { id: "DataTableSummary" });
   z.globalRegistry.add(QueryResponseSchema, { id: "QueryResponse" });
   z.globalRegistry.add(QueryExecRequestSchema, {
      id: "QueryExecRequest"
   });

   // Register session schemas
   z.globalRegistry.add(SessionInitRequestSchema, {
      id: "SessionInitRequest"
   });
   z.globalRegistry.add(SessionInitResponseSchema, {
      id: "SessionInitResponse"
   });

   // Register query session schemas
   z.globalRegistry.add(QuerySessionStatusSchema, {
      id: "QuerySessionStatus"
   });
   z.globalRegistry.add(QueryEngineTypeSchema, {
      id: "QueryEngineType"
   });
   z.globalRegistry.add(QuerySessionModelSchema, {
      id: "QuerySessionModel"
   });
   z.globalRegistry.add(PaginatedListOfQuerySessionModelSchema, {
      id: "PaginatedListOfQuerySessionModel"
   });
   z.globalRegistry.add(CreateQuerySessionRequestSchema, {
      id: "CreateQuerySessionRequest"
   });
   z.globalRegistry.add(CreateQuerySessionResponseSchema, {
      id: "CreateQuerySessionResponse"
   });
   z.globalRegistry.add(UpdateQuerySessionRequestSchema, {
      id: "UpdateQuerySessionRequest"
   });
   z.globalRegistry.add(QuerySessionTableModelSchema, {
      id: "QuerySessionTableModel"
   });
   z.globalRegistry.add(QuerySessionStatsResponseSchema, {
      id: "QuerySessionStatsResponse"
   });
   z.globalRegistry.add(SchemaInfoSchema, { id: "SchemaInfo" });
   z.globalRegistry.add(TableDiscoveryModelSchema, {
      id: "TableDiscoveryModel"
   });
   z.globalRegistry.add(CatalogSearchItemSchema, {
      id: "CatalogSearchItem"
   });
   z.globalRegistry.add(CatalogSearchResultSchema, {
      id: "CatalogSearchResult"
   });
   z.globalRegistry.add(KnowledgeSearchResultSchema, {
      id: "KnowledgeSearchResult"
   });
   z.globalRegistry.add(KnowledgeProposalResultSchema, {
      id: "KnowledgeProposalResult"
   });
   // Register query schemas
   z.globalRegistry.add(CreateQueryRequestSchema, {
      id: "CreateQueryRequest"
   });
   z.globalRegistry.add(QueryModelSchema, {
      id: "QueryModel"
   });

   // Agent session state schemas
   z.globalRegistry.add(DataStateTypeSchema, {
      id: "DataStateType"
   });
   z.globalRegistry.add(DataStateEntrySchema, {
      id: "DataStateEntry"
   });

   z.globalRegistry.add(ArtifactStateEntrySchema, {
      id: "ArtifactStateEntry"
   });
   z.globalRegistry.add(SharedArtifactDescriptorSchema, {
      id: "SharedArtifactDescriptor"
   });
   z.globalRegistry.add(AttachedDataTableSchema, {
      id: "AttachedDataTable"
   });
   z.globalRegistry.add(AttachedDataSourceSchema, {
      id: "AttachedDataSource"
   });
   z.globalRegistry.add(AgentSessionStateSchema, {
      id: "AgentSessionState"
   });
   z.globalRegistry.add(ChatAttachmentContextFileSchema, {
      id: "ChatAttachmentContextFile"
   });
   z.globalRegistry.add(ChatAttachmentContextTableSchema, {
      id: "ChatAttachmentContextTable"
   });
   z.globalRegistry.add(ChatAttachmentContextSchema, {
      id: "ChatAttachmentContext"
   });
   z.globalRegistry.add(SeedChatAttachmentContextRequestSchema, {
      id: "SeedChatAttachmentContextRequest"
   });
   z.globalRegistry.add(ChatUploadPreparationAcceptedFileSchema, {
      id: "ChatUploadPreparationAcceptedFile"
   });
   z.globalRegistry.add(ChatUploadPreparationFailureSchema, {
      id: "ChatUploadPreparationFailure"
   });
   z.globalRegistry.add(ChatUploadPreparationStepSchema, {
      id: "ChatUploadPreparationStep"
   });
   z.globalRegistry.add(ChatUploadPreparationStatusSchema, {
      id: "ChatUploadPreparationStatus"
   });
   z.globalRegistry.add(StartChatUploadPreparationResponseSchema, {
      id: "StartChatUploadPreparationResponse"
   });

   z.globalRegistry.add(ChatSessionModelSchema, {
      id: "ChatSessionModel"
   });
   z.globalRegistry.add(CreateChatSessionRequestSchema, {
      id: "CreateChatSessionRequest"
   });
   z.globalRegistry.add(UpdateChatSessionRequestSchema, {
      id: "UpdateChatSessionRequest"
   });
   z.globalRegistry.add(PaginatedChatSessionResponseSchema, {
      id: "PaginatedChatSessionResponse"
   });

   z.globalRegistry.add(ChatSessionArtifactModelSchema, {
      id: "ChatSessionArtifactModel"
   });
   z.globalRegistry.add(ArtifactListResponseSchema, {
      id: "ArtifactListResponse"
   });

   // Schema consolidation models
   z.globalRegistry.add(DataLakeColumnSchema, {
      id: "DataLakeColumn"
   });
   z.globalRegistry.add(TypePromotionInfoModelSchema, {
      id: "TypePromotionInfoModel"
   });
   z.globalRegistry.add(SchemaConsolidationInfoModelSchema, {
      id: "SchemaConsolidationInfoModel"
   });
   z.globalRegistry.add(CatalogEntityMetadataModelSchema, {
      id: "CatalogEntityMetadataModel"
   });
   z.globalRegistry.add(CatalogEntitySchemaModelSchema, {
      id: "CatalogEntitySchemaModel"
   });
   z.globalRegistry.add(CatalogEntityDiscoveryModelSchema, {
      id: "CatalogEntityDiscoveryModel"
   });
   z.globalRegistry.add(SchemaConsolidationResultModelSchema, {
      id: "SchemaConsolidationResultModel"
   });
   z.globalRegistry.add(ConsolidateSchemasRequestSchema, {
      id: "ConsolidateSchemasRequest"
   });
   z.globalRegistry.add(SuggestObjectNameRequestSchema, {
      id: "SuggestObjectNameRequest"
   });
   z.globalRegistry.add(SuggestObjectNameResultModelSchema, {
      id: "SuggestObjectNameResultModel"
   });

   // Column models
   z.globalRegistry.add(ColumnDataTypeSchema, { id: "ColumnDataType" });
   z.globalRegistry.add(ColumnModelSchema, { id: "ColumnModel" });
   z.globalRegistry.add(ColumnStatsModelSchema, { id: "ColumnStatsModel" });

   // File models (for schema profiling)
   z.globalRegistry.add(FileMetadataModelSchema, { id: "FileMetadataModel" });
   z.globalRegistry.add(TableSchemaModelSchema, { id: "TableSchemaModel" });
   z.globalRegistry.add(TableStatsModelSchema, { id: "TableStatsModel" });
   z.globalRegistry.add(FileStatsModelSchema, { id: "FileStatsModel" });
   z.globalRegistry.add(FileSchemaModelSchema, { id: "FileSchemaModel" });

   z.globalRegistry.add(SchemaColumnDefinitionSchema, {
      id: "SchemaColumnDefinition"
   });
   z.globalRegistry.add(FileModelSchema, { id: "FileModel" });
   z.globalRegistry.add(FileNavModelSchema, {
      id: "FileNavModel"
   });
   z.globalRegistry.add(SimpleFileModelSchema, {
      id: "SimpleFileModel"
   });
   z.globalRegistry.add(FileSchemaExportModelSchema, {
      id: "FileSchemaExportModel"
   });
   z.globalRegistry.add(CreateFileRequestSchema, {
      id: "CreateFileRequest"
   });
   z.globalRegistry.add(UpdateFileRequestSchema, {
      id: "UpdateFileRequest"
   });
   z.globalRegistry.add(FileUploadMetadataSchema, {
      id: "FileUploadMetadata"
   });
   z.globalRegistry.add(FileUploadResponseSchema, {
      id: "FileUploadResponse"
   });
   z.globalRegistry.add(CreateMultipleFilesResponseSchema, {
      id: "CreateMultipleFilesResponse"
   });
   z.globalRegistry.add(PaginatedFileResponseSchema, {
      id: "PaginatedFileResponse"
   });
   z.globalRegistry.add(UpdateFileSchemaRequestSchema, {
      id: "UpdateFileSchemaRequest"
   });
   z.globalRegistry.add(BulkFileIdsRequestSchema, {
      id: "BulkFileIdsRequest"
   });
   z.globalRegistry.add(ExecuteNotebookPythonRequestSchema, {
      id: "ExecuteNotebookPythonRequest"
   });

   // Multipart request bodies. Naming these explicitly keeps the FileUpload
   // endpoints' request bodies documented instead of surfacing FastAPI's
   // synthesized `Body_<OperationId>` component names.
   //
   // `*Body` (not `*Request`): the endpoints bind these as flat `File()`
   // parameters, so nothing validates request payloads against them. They name
   // the documented multipart body shape only.
   z.globalRegistry.add(UploadFileBodySchema, {
      id: "UploadFileBody"
   });
   z.globalRegistry.add(UploadMultipleFilesBodySchema, {
      id: "UploadMultipleFilesBody"
   });
   z.globalRegistry.add(UpdateFileContentBodySchema, {
      id: "UpdateFileContentBody"
   });
   z.globalRegistry.add(StartChatUploadPreparationBodySchema, {
      id: "StartChatUploadPreparationBody"
   });
   z.globalRegistry.add(ImportOkfBundleBodySchema, {
      id: "ImportOkfBundleBody"
   });
   z.globalRegistry.add(ExecutePythonScriptRequestSchema, {
      id: "ExecutePythonScriptRequest"
   });

   z.globalRegistry.add(SimpleFileEventDataSchema, {
      id: "SimpleFileEventData"
   });
   z.globalRegistry.add(FileCreatedEventDataSchema, {
      id: "FileCreatedEventData"
   });
   z.globalRegistry.add(FileDeletedEventDataSchema, {
      id: "FileDeletedEventData"
   });
   z.globalRegistry.add(FileSchemaUpdatedEventDataSchema, {
      id: "FileSchemaUpdatedEventData"
   });
   z.globalRegistry.add(CatalogEntityCreatedEventDataSchema, {
      id: "CatalogEntityCreatedEventData"
   });
   z.globalRegistry.add(CatalogEntityUpdatedEventDataSchema, {
      id: "CatalogEntityUpdatedEventData"
   });
   z.globalRegistry.add(CatalogEntityDeletedEventDataSchema, {
      id: "CatalogEntityDeletedEventData"
   });

   z.globalRegistry.add(HealthCheckResponseSchema, {
      id: "HealthCheckResponse"
   });
   z.globalRegistry.add(PingResponseSchema, { id: "PingResponse" });
   z.globalRegistry.add(HealthCheckRequestSchema, { id: "HealthCheckRequest" });
   z.globalRegistry.add(PingRequestSchema, { id: "PingRequest" });

   z.globalRegistry.add(JobExecutionMessageSchema, {
      id: "JobExecutionMessage"
   });
   z.globalRegistry.add(JobDispatchResponseSchema, {
      id: "JobDispatchResponse"
   });

   // Register base schemas
   z.globalRegistry.add(ValidationErrorResponseSchema, {
      id: "ValidationErrorResponse"
   });
   z.globalRegistry.add(ValidationErrorLocInnerSchema, {
      id: "ValidationErrorLocInner"
   });
   z.globalRegistry.add(ValidationErrorSchema, {
      id: "ValidationError"
   });
   z.globalRegistry.add(HTTPValidationErrorSchema, {
      id: "HTTPValidationError"
   });

   // Register AI schemas
   z.globalRegistry.add(ArtifactTypeSchema, { id: "ArtifactType" });
   z.globalRegistry.add(ArtifactEventKindSchema, { id: "ArtifactEventKind" });
   z.globalRegistry.add(ArtifactActionTypeSchema, { id: "ArtifactActionType" });
   z.globalRegistry.add(ToolCallResultTypeSchema, { id: "ToolCallResultType" });
   z.globalRegistry.add(ArtifactActionSchema, { id: "ArtifactAction" });
   z.globalRegistry.add(DataTableOpenActionPayloadSchema, {
      id: "DataTableOpenActionPayload"
   });
   z.globalRegistry.add(DataTableOpenActionSchema, {
      id: "DataTableOpenAction"
   });

   // Tool Results
   z.globalRegistry.add(BaseToolResultSchema, { id: "BaseToolResult" });
   z.globalRegistry.add(ArtifactOriginSchema, { id: "ArtifactOrigin" });
   z.globalRegistry.add(ArtifactProvenanceSchema, {
      id: "ArtifactProvenance"
   });
   z.globalRegistry.add(SqlExecutionResultSchema, {
      id: "SqlExecutionResult"
   });
   z.globalRegistry.add(SqlValidationResultSchema, {
      id: "SqlValidationResult"
   });
   z.globalRegistry.add(PythonValidationResultSchema, {
      id: "PythonValidationResult"
   });
   z.globalRegistry.add(PythonExecutionApprovalModeSchema, {
      id: "PythonExecutionApprovalMode"
   });
   z.globalRegistry.add(PythonExecutionModeSchema, {
      id: "PythonExecutionMode"
   });
   z.globalRegistry.add(PythonExecutionTargetTypeSchema, {
      id: "PythonExecutionTargetType"
   });
   z.globalRegistry.add(PythonSavedTableSchema, {
      id: "PythonSavedTable"
   });
   z.globalRegistry.add(PythonExecutionResultSchema, {
      id: "PythonExecutionResult"
   });
   z.globalRegistry.add(CatalogListingResultSchema, {
      id: "CatalogListingResult"
   });
   z.globalRegistry.add(CatalogEntityStatsResultSchema, {
      id: "CatalogEntityStatsResult"
   });
   z.globalRegistry.add(ProjectResultSchema, {
      id: "ProjectResult"
   });
   z.globalRegistry.add(ChartResultSchema, {
      id: "ChartResult"
   });
   z.globalRegistry.add(NotebookResultSchema, {
      id: "NotebookResult"
   });
   z.globalRegistry.add(NotebookListResultSchema, {
      id: "NotebookListResult"
   });
   z.globalRegistry.add(NotebookMutationResultSchema, {
      id: "NotebookMutationResult"
   });
   z.globalRegistry.add(NotebookBlockResultSchema, {
      id: "NotebookBlockResult"
   });
   z.globalRegistry.add(NotebookBlockListResultSchema, {
      id: "NotebookBlockListResult"
   });
   z.globalRegistry.add(NotebookMultiBlockResultSchema, {
      id: "NotebookMultiBlockResult"
   });
   z.globalRegistry.add(NotebookDataResultSchema, {
      id: "NotebookDataResult"
   });
   z.globalRegistry.add(SqlExecutionBatchResultSchema, {
      id: "SqlExecutionBatchResult"
   });
   z.globalRegistry.add(SqlValidationBatchResultSchema, {
      id: "SqlValidationBatchResult"
   });
   z.globalRegistry.add(CatalogEntityStatsBatchResultSchema, {
      id: "CatalogEntityStatsBatchResult"
   });
   z.globalRegistry.add(ChartBatchResultSchema, {
      id: "ChartBatchResult"
   });
   z.globalRegistry.add(NotebookBatchResultSchema, {
      id: "NotebookBatchResult"
   });
   z.globalRegistry.add(NotebookBlockBatchResultSchema, {
      id: "NotebookBlockBatchResult"
   });
   z.globalRegistry.add(DocumentSearchItemSchema, {
      id: "DocumentSearchItem"
   });
   z.globalRegistry.add(DiscoveryResultSchema, {
      id: "DiscoveryResult"
   });
   z.globalRegistry.add(ExternalExecutionRequirementSchema, {
      id: "ExternalExecutionRequirement"
   });
   z.globalRegistry.add(ToolExecutionSchema, {
      id: "ToolExecution"
   });
   z.globalRegistry.add(ToolCallResultSchema, {
      id: "ToolCallResult"
   });

   // Notebook Actions
   z.globalRegistry.add(NotebookUpsertBlockActionSchema, {
      id: "NotebookUpsertBlockAction"
   });
   z.globalRegistry.add(NotebookUpsertBlockActionPayloadSchema, {
      id: "NotebookUpsertBlockActionPayload"
   });

   z.globalRegistry.add(NotebookPatchBlockContentActionSchema, {
      id: "NotebookPatchBlockContentAction"
   });
   z.globalRegistry.add(NotebookPatchBlockContentActionPayloadSchema, {
      id: "NotebookPatchBlockContentActionPayload"
   });

   z.globalRegistry.add(NotebookSetBlockOutputActionSchema, {
      id: "NotebookSetBlockOutputAction"
   });
   z.globalRegistry.add(NotebookSetBlockOutputActionPayloadSchema, {
      id: "NotebookSetBlockOutputActionPayload"
   });
   z.globalRegistry.add(NotebookSetBlockOutputActionPayloadOutputSchema, {
      id: "NotebookSetBlockOutputActionPayloadOutput"
   });

   z.globalRegistry.add(NotebookRemoveBlockActionSchema, {
      id: "NotebookRemoveBlockAction"
   });
   z.globalRegistry.add(NotebookRemoveBlockActionPayloadSchema, {
      id: "NotebookRemoveBlockActionPayload"
   });

   z.globalRegistry.add(NotebookUpdateMetadataActionSchema, {
      id: "NotebookUpdateMetadataAction"
   });
   z.globalRegistry.add(NotebookUpdateMetadataActionPayloadSchema, {
      id: "NotebookUpdateMetadataActionPayload"
   });

   // Chart Actions
   z.globalRegistry.add(ChartUpdateConfigActionSchema, {
      id: "ChartUpdateConfigAction"
   });
   z.globalRegistry.add(ChartUpdateConfigActionPayloadSchema, {
      id: "ChartUpdateConfigActionPayload"
   });

   z.globalRegistry.add(ChartSetDataActionSchema, {
      id: "ChartSetDataAction"
   });
   z.globalRegistry.add(ChartSetDataActionPayloadSchema, {
      id: "ChartSetDataActionPayload"
   });
   z.globalRegistry.add(RunEventSchema, { id: "RunEvent" });
   z.globalRegistry.add(ToolCallSchema, { id: "ToolCall" });
   z.globalRegistry.add(RunStartedEventDataSchema, {
      id: "RunStartedEventData"
   });
   z.globalRegistry.add(RunContentEventDataSchema, {
      id: "RunContentEventData"
   });
   z.globalRegistry.add(RunCompletedEventDataSchema, {
      id: "RunCompletedEventData"
   });
   z.globalRegistry.add(RunPausedEventDataSchema, {
      id: "RunPausedEventData"
   });
   z.globalRegistry.add(ToolCallStartedEventDataSchema, {
      id: "ToolCallStartedEventData"
   });
   z.globalRegistry.add(ToolCallCompletedEventDataSchema, {
      id: "ToolCallCompletedEventData"
   });
   z.globalRegistry.add(ReasoningEventDataSchema, { id: "ReasoningEventData" });
   z.globalRegistry.add(ArtifactTypeSchema, { id: "ArtifactType" });
   z.globalRegistry.add(ArtifactEventDataSchema, { id: "ArtifactEventData" });
   z.globalRegistry.add(EventDataSchema, { id: "EventData" });
   z.globalRegistry.add(SimpleRunEventSchema, { id: "SimpleRunEvent" });
   z.globalRegistry.add(ToolCallStatusSchema, { id: "ToolCallStatus" });
   z.globalRegistry.add(ToolCallStateSchema, { id: "ToolCallState" });
   z.globalRegistry.add(ChatMessageTypeSchema, { id: "ChatMessageType" });
   z.globalRegistry.add(ChatMessageStatusSchema, { id: "ChatMessageStatus" });
   z.globalRegistry.add(ChatMessageSegmentTypeSchema, {
      id: "ChatMessageSegmentType"
   });
   z.globalRegistry.add(ChatTextSegmentSchema, { id: "ChatTextSegment" });
   z.globalRegistry.add(ChatReasoningSegmentSchema, {
      id: "ChatReasoningSegment"
   });
   z.globalRegistry.add(ChatToolCallSegmentSchema, {
      id: "ChatToolCallSegment"
   });
   z.globalRegistry.add(ChatErrorSegmentSchema, { id: "ChatErrorSegment" });
   z.globalRegistry.add(ChatObjectSegmentSchema, { id: "ChatObjectSegment" });
   z.globalRegistry.add(ChatMessageSegmentSchema, {
      id: "ChatMessageSegment"
   });
   z.globalRegistry.add(ChatMessageSchema, { id: "ChatMessage" });
   z.globalRegistry.add(ChatRequestSchema, { id: "ChatRequest" });
   z.globalRegistry.add(TokenUsageStatsModelSchema, {
      id: "TokenUsageStatsModel"
   });
   z.globalRegistry.add(TokenUsageDailyStatsModelSchema, {
      id: "TokenUsageDailyStatsModel"
   });
   z.globalRegistry.add(ProjectTokenUsageResponseSchema, {
      id: "ProjectTokenUsageResponse"
   });
   z.globalRegistry.add(ProjectDailyTokenUsageResponseSchema, {
      id: "ProjectDailyTokenUsageResponse"
   });

   // Register chart schemas
   z.globalRegistry.add(ColorPaletteSchema, { id: "ColorPalette" });
   z.globalRegistry.add(MarkTypesSchema, { id: "MarkTypes" });
   z.globalRegistry.add(NumberFormatSchema, { id: "NumberFormat" });
   z.globalRegistry.add(DualAxesChartTypeSchema, { id: "DualAxesChartType" });
   z.globalRegistry.add(BoxChartTypeSchema, { id: "BoxChartType" });
   z.globalRegistry.add(RadarCoordinateTypeSchema, {
      id: "RadarCoordinateType"
   });
   z.globalRegistry.add(ChartTypeSchema, { id: "ChartType" });
   z.globalRegistry.add(AggregateMethodSchema, { id: "AggregateMethod" });
   z.globalRegistry.add(ConnectNullsSchema, { id: "ConnectNulls" });
   z.globalRegistry.add(ConnectNullsObjectSchema, {
      id: "ConnectNullsObject"
   });
   // Register standalone configuration schemas (reusable types)
   z.globalRegistry.add(chartStackConfigSchema, { id: "ChartStackConfig" });
   z.globalRegistry.add(chartGroupConfigSchema, { id: "ChartGroupConfig" });
   Object.entries(CHART_SCHEMAS).forEach(([chartType, schema]) => {
      const capitalizedType =
         chartType.charAt(0).toUpperCase() + chartType.slice(1);
      z.globalRegistry.add(schema, { id: `${capitalizedType}ChartConfig` });
   });
   z.globalRegistry.add(ChartConfigSchema, { id: "ChartConfig" });
   z.globalRegistry.add(ChartSpecSchema, { id: "ChartSpec" });
   z.globalRegistry.add(ChartDocumentSchema, { id: "ChartDocument" });
   z.globalRegistry.add(ChartDocumentMetadataSchema, {
      id: "ChartDocumentMetadata"
   });
   // Hoist the box chart legend union into a named component so the API
   // spec and the comprehensive models spec agree on component names.
   z.globalRegistry.add(BoxChartConfigLegendSchema, {
      id: "BoxChartConfigLegend"
   });

   // Register notebook schemas
   z.globalRegistry.add(ListBlockMetaSchema, { id: "ListBlockMeta" });
   z.globalRegistry.add(CounterTypeSchema, { id: "CounterType" });
   z.globalRegistry.add(ListStyleSchema, { id: "ListStyle" });
   z.globalRegistry.add(ListItemMetaSchema, { id: "ListItemMeta" });
   z.globalRegistry.add(ListItemSchema, { id: "ListItem" });
   z.globalRegistry.add(InlineDataSchema, { id: "InlineData" });
   z.globalRegistry.add(InlineDataMetadataSchema, { id: "InlineDataMetadata" });
   z.globalRegistry.add(CodeLanguageSchema, { id: "CodeLanguage" });
   z.globalRegistry.add(DataRefSchema, { id: "DataRef" });
   z.globalRegistry.add(NotebookDocumentSchema, { id: "NotebookDocument" });
   // Hoist notebook document metadata and the image file reference into named
   // components so they resolve from @kontext-labs/schema rather than being
   // regenerated as API-only schemas.
   z.globalRegistry.add(NotebookDocumentMetadataSchema, {
      id: "NotebookDocumentMetadata"
   });
   z.globalRegistry.add(ImageBlockDataFileSchema, {
      id: "ImageBlockDataFile"
   });
   z.globalRegistry.add(NotebookBlockTypeSchema, { id: "NotebookBlockType" });
   z.globalRegistry.add(NotebookBlockSchema, { id: "NotebookBlock" });
   z.globalRegistry.add(QuoteAlignmentSchema, { id: "QuoteAlignment" });

   // Code block outputs and types
   z.globalRegistry.add(CodeRuntimePreferenceSchema, {
      id: "CodeRuntimePreference"
   });
   z.globalRegistry.add(CodeExecutionOutputTypeSchema, {
      id: "CodeExecutionOutputType"
   });
   z.globalRegistry.add(CodeTextOutputSchema, { id: "CodeTextOutput" });
   z.globalRegistry.add(CodeImageOutputSchema, { id: "CodeImageOutput" });
   z.globalRegistry.add(CodeImageRefOutputSchema, { id: "CodeImageRefOutput" });
   z.globalRegistry.add(CodeJsonOutputSchema, { id: "CodeJsonOutput" });
   z.globalRegistry.add(CodeResourceOutputSchema, { id: "CodeResourceOutput" });
   z.globalRegistry.add(CodeExecutionOutputSchema, {
      id: "CodeExecutionOutput"
   });

   // Register individual block schemas
   Object.entries(BLOCK_DATA_SCHEMAS).forEach(([blockType, schema]) => {
      const capitalizedType =
         blockType.charAt(0).toUpperCase() + blockType.slice(1);
      z.globalRegistry.add(schema, { id: `${capitalizedType}BlockData` });
   });
   z.globalRegistry.add(BlockDataSchema, { id: "BlockData" });
   Object.entries(BLOCK_SCHEMAS).forEach(([blockType, schema]) => {
      const capitalizedType =
         blockType.charAt(0).toUpperCase() + blockType.slice(1);
      z.globalRegistry.add(schema, { id: `${capitalizedType}Block` });
   });

   // Register WASM OPFS state schemas

   console.log("✅ All schemas registered in global registry");
}

function main() {
   console.log("🚀 Starting comprehensive Kontext schema export...");

   // Ensure output directory exists
   mkdirSync(outDir, { recursive: true });

   // Register schemas
   registerDefinitions();

   let schema = z.toJSONSchema(z.globalRegistry, {
      target: "openapi-3.0"
   });

   // Flatten __shared definitions into main definitions
   if (schema.schemas.__shared && schema.schemas.__shared.definitions) {
      Object.assign(schema.schemas, schema.schemas.__shared.definitions);
      delete schema.schemas.__shared;
   }

   // Fix $ref values to use proper JSON Pointer format and ensure top-level
   // component schemas don't carry id/$id. Both live in the shared normalizer so
   // the export and the SDK spec fetch apply identical policy.
   fixRefsToComponents(schema.schemas);
   stripTopLevelSchemaIds(schema.schemas);

   console.log("📦 Extracted all schemas from global registry");

   // Every component comes from an explicit registration (see
   // `registerDefinitions`); the exporter does not synthesise wrapper types,
   // so the registry is the spec.
   const filteredSchemas = schema.schemas;

   // Handle inline enum properties - convert them to $ref pointers
   const inlineEnumReplacements = [];
   for (const [schemaKey, schema] of Object.entries(filteredSchemas)) {
      if (!schema.properties) continue;

      for (const [propKey, propValue] of Object.entries(schema.properties)) {
         // Skip if already a reference
         if (propValue.$ref) continue;

         // Detect inline enum in direct property: has type: string, enum array, but no $ref
         if (
            propValue.type === "string" &&
            Array.isArray(propValue.enum) &&
            propValue.enum.length > 0
         ) {
            // Look for a matching enum schema with the same values
            const inlineEnumValues = new Set(propValue.enum);
            let selectedEnumKey = null;

            const propertyOverrides = INLINE_ENUM_REFERENCE_OVERRIDES[propKey];
            if (propertyOverrides && inlineEnumValues.size === 1) {
               const singleValue = Array.from(inlineEnumValues)[0];

               for (const override of propertyOverrides) {
                  if (
                     !override.condition ||
                     override.condition({
                        schemaKey,
                        propKey,
                        values: Array.from(inlineEnumValues)
                     })
                  ) {
                     const targetEnumSchema = filteredSchemas[override.target];
                     if (
                        targetEnumSchema &&
                        Array.isArray(targetEnumSchema.enum) &&
                        targetEnumSchema.enum.includes(singleValue)
                     ) {
                        selectedEnumKey = override.target;
                        break;
                     }
                  }
               }
            }

            for (const [enumKey, enumSchema] of Object.entries(
               filteredSchemas
            )) {
               // Skip if same schema or if not an enum type
               if (enumKey === schemaKey || !enumSchema.enum) continue;

               if (selectedEnumKey) {
                  break;
               }

               // Check if enum values match exactly
               const schemaEnumValues = new Set(enumSchema.enum);
               const isExactMatch =
                  inlineEnumValues.size === schemaEnumValues.size &&
                  Array.from(inlineEnumValues).every((val) =>
                     schemaEnumValues.has(val)
                  );

               // Check if it's a single value subset (discriminator pattern)
               const isPerfectMatch =
                  enumKey.toLowerCase() === propKey.toLowerCase() ||
                  enumKey.toLowerCase() === propKey.toLowerCase() + "type" ||
                  enumKey.toLowerCase() ===
                     "artifact" + propKey.toLowerCase() ||
                  enumKey.toLowerCase() ===
                     "artifact" + propKey.toLowerCase() + "type";

               const singleValue =
                  inlineEnumValues.size === 1
                     ? Array.from(inlineEnumValues)[0]
                     : null;

               const isValueContextMatch =
                  singleValue &&
                  (schemaKey
                     .toLowerCase()
                     .includes(singleValue.toLowerCase().replace(/_/g, "")) ||
                     singleValue
                        .toLowerCase()
                        .replace(/_/g, "")
                        .includes(
                           schemaKey.toLowerCase().replace(/result/g, "")
                        ) ||
                     // Also handle cases where the enum contains the schema name
                     enumKey.toLowerCase().includes(schemaKey.toLowerCase()));

               const isDiscriminatorSubset =
                  singleValue &&
                  Array.from(inlineEnumValues).every((val) =>
                     schemaEnumValues.has(val)
                  ) &&
                  (isPerfectMatch ||
                     (enumKey.toLowerCase().includes(propKey.toLowerCase()) &&
                        isValueContextMatch));

               if (isExactMatch || isDiscriminatorSubset) {
                  // Perfect match found, use it immediately
                  if (
                     (isPerfectMatch || isExactMatch) &&
                     (enumKey === "NotebookBlockType" ||
                        !schemaKey.toLowerCase().includes("block"))
                  ) {
                     selectedEnumKey = enumKey;
                     break;
                  }
                  // Otherwise, remember this as a possible match
                  if (
                     !selectedEnumKey ||
                     (enumKey === "NotebookBlockType" &&
                        schemaKey.toLowerCase().includes("block"))
                  ) {
                     selectedEnumKey = enumKey;
                  }
               }
            }

            if (selectedEnumKey) {
               inlineEnumReplacements.push({
                  schemaKey,
                  propKey,
                  enumKey: selectedEnumKey,
                  propValue,
                  isArrayItem: false
               });
               console.log(
                  `🎯 Match: ${schemaKey}.${propKey} -> ${selectedEnumKey}`
               );
            }
         }

         // Detect inline enum in array items: type: array with items containing enum
         if (
            propValue.type === "array" &&
            propValue.items &&
            propValue.items.type === "string" &&
            Array.isArray(propValue.items.enum) &&
            propValue.items.enum.length > 0 &&
            !propValue.items.$ref
         ) {
            // Look for a matching enum schema with the same values
            const inlineEnumValues = new Set(propValue.items.enum);

            for (const [enumKey, enumSchema] of Object.entries(
               filteredSchemas
            )) {
               // Skip if same schema or if not an enum type
               if (enumKey === schemaKey || !enumSchema.enum) continue;

               // Check if enum values match exactly
               const schemaEnumValues = new Set(enumSchema.enum);
               const isExactMatch =
                  inlineEnumValues.size === schemaEnumValues.size &&
                  Array.from(inlineEnumValues).every((val) =>
                     schemaEnumValues.has(val)
                  );

               // Check if it's a single value subset (discriminator pattern)
               const isDiscriminatorSubset =
                  inlineEnumValues.size === 1 &&
                  Array.from(inlineEnumValues).every((val) =>
                     schemaEnumValues.has(val)
                  ) &&
                  enumKey.toLowerCase().includes(propKey.toLowerCase());

               if (isExactMatch || isDiscriminatorSubset) {
                  // Found a matching enum schema
                  inlineEnumReplacements.push({
                     schemaKey,
                     propKey,
                     enumKey,
                     propValue,
                     isArrayItem: true
                  });
                  break;
               }
            }
         }
      }
   }

   // Reuse numeric value mappings from the single source of truth
   // Source: backend/Kontext.Data/Primitives.cs
   // Imported from: ts/schema/src/enumMappings.ts
   const allEnumNumericMappings = EnumNumericMappings;

   // Add numeric value mappings and identifier mappings to all enums via x-enumValues extension
   for (const [enumName, schema] of Object.entries(filteredSchemas)) {
      if (schema.enum) {
         const mapping = EnumNumericMappings[enumName] || {};

         // Note: We keep type: string to ensure Python/JS compatibility as string enums
         // but we provide x-enumValues and x-enum-varnames for C# and Python identifiers.
         schema["x-enumValues"] = schema.enum.map((enumValue, index) => {
            // Find numeric value - try exact match or case-insensitive match
            let numericValue = mapping[enumValue];
            if (numericValue === undefined) {
               // Try case-insensitive lookup
               const match = Object.entries(mapping).find(
                  ([k]) => k.toLowerCase() === enumValue.toLowerCase()
               );
               if (match) {
                  numericValue = match[1];
               }
            }

            // PascalCase the name for C# identifiers
            // Handle snake_case like tool_call -> ToolCall, hyphen-case like lower-roman -> LowerRoman
            // and special characters like slashes or dots in mime-types.
            const pascalName = enumValue
               .split(/[^a-zA-Z0-9]+/)
               .filter((part) => part.length > 0)
               .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
               .join("");

            // Python identifiers should be UPPERCASE with NO UNDERSCORES based on existing codebase usage
            // E.g. tool_call -> TOOLCALL, DeadLettered -> DEADLETTERED, lower-roman -> LOWERROMAN
            const pythonName = enumValue
               .toUpperCase()
               .replace(/[^A-Z0-9]/g, "");

            return {
               name: pascalName,
               pythonName: pythonName,
               value: numericValue !== undefined ? numericValue : index,
               wireValue: enumValue
            };
         });

         // Add x-enum-varnames for better identifier generation in Python
         schema["x-enum-varnames"] = schema["x-enumValues"].map(
            (v) => v.pythonName
         );

         console.log(
            `📊 Added enum mappings to ${enumName} (${schema["x-enumValues"].length} values)`
         );
      }
   }

   // Apply inline enum replacements
   for (const {
      schemaKey,
      propKey,
      enumKey,
      isArrayItem,
      propValue
   } of inlineEnumReplacements) {
      const schema = filteredSchemas[schemaKey];

      if (isArrayItem) {
         // ... (keep this as is for now)
      } else {
         const isNullable = propValue.nullable === true;
         const description = propValue.description;

         // Ensure default value is set for discriminator subsets (single value enums)
         let finalDefault = propValue.default;
         if (
            finalDefault === undefined &&
            Array.isArray(propValue.enum) &&
            propValue.enum.length === 1
         ) {
            finalDefault = propValue.enum[0];
         }

         const resultObj = {};

         if (isNullable) {
            resultObj.nullable = true;
         }

         if (description) {
            resultObj.description = description;
         }

         // Preserve default value if present
         if (finalDefault !== undefined) {
            resultObj.default = finalDefault;

            // If it's an enum, we might want to provide a specific C# default
            const enumInfo = filteredSchemas[enumKey];
            if (enumInfo) {
               if (enumInfo["x-enumValues"]) {
                  const match = enumInfo["x-enumValues"].find(
                     (v) => v.wireValue === finalDefault
                  );
                  if (match) {
                     resultObj["x-csharp-default"] = `${enumKey}.${match.name}`;

                     // Automatically treat single-value enum matches as discriminators
                     // If the original property was a single-choice enum (literal), mark it as such
                     if (
                        Array.isArray(propValue.enum) &&
                        propValue.enum.length === 1
                     ) {
                        // We use internal set for C# to allow internal mapping/serialization logic
                        // while preventing external changes.
                        resultObj["x-csharp-internal-set"] = true;

                        // Keep the discriminator value in the schema itself so
                        // generators emit a literal type without vendor extensions.
                        resultObj.enum = [propValue.enum[0]];
                     }
                  }
               } else if (Array.isArray(enumInfo.enum)) {
                  // Fallback: use PascalCase of the wire value
                  const match = enumInfo.enum.find((v) => v === finalDefault);
                  if (match) {
                     const pascalName =
                        match.charAt(0).toUpperCase() + match.slice(1);
                     resultObj["x-csharp-default"] = `${enumKey}.${pascalName}`;

                     if (
                        Array.isArray(propValue.enum) &&
                        propValue.enum.length === 1
                     ) {
                        resultObj["x-csharp-internal-set"] = true;
                        resultObj.enum = [propValue.enum[0]];
                     }
                  }
               }
            }
         }

         const needsAllOfWrapper =
            resultObj.nullable === true ||
            resultObj.description !== undefined ||
            resultObj.default !== undefined ||
            resultObj["x-csharp-default"] !== undefined ||
            resultObj["x-csharp-internal-set"] !== undefined;

         if (needsAllOfWrapper) {
            resultObj.allOf = [
               {
                  $ref: `#/components/schemas/${enumKey}`
               }
            ];
         } else {
            resultObj.$ref = `#/components/schemas/${enumKey}`;
         }

         schema.properties[propKey] = resultObj;
         console.log(
            `🔗 Creating enum reference: ${schemaKey}.${propKey} -> ${enumKey}`
         );
      }
   }

   // Cleanup patterns: strip leading/trailing slashes if they exist (Zod literals)
   // Also add x-csharp-pattern to control which fields get RegularExpression attributes in .NET
   for (const schema of Object.values(filteredSchemas)) {
      if (schema.properties) {
         const propKeys = Object.keys(schema.properties);
         for (const propKey of propKeys) {
            const prop = schema.properties[propKey];

            if (prop.pattern) {
               if (prop.pattern.startsWith("/") && prop.pattern.endsWith("/")) {
                  prop.pattern = prop.pattern.slice(1, -1);
               }

               // For C#, we only want patterns that aren't handling native types like Guid/DateTime
               if (
                  prop.format !== "uuid" &&
                  prop.format !== "date-time" &&
                  prop.format !== "email"
               ) {
                  prop["x-csharp-pattern"] = prop.pattern;
               }
            }

            // Extract format from description if present (Zod doesn't always set format)
            if (
               !prop.format &&
               prop.description &&
               prop.description.startsWith("format: ")
            ) {
               // Extract format from "format: double|description" or "format: double. description"
               const match = prop.description.match(
                  /^format:\s*(\w+)(?:\s*[.|]?\s*(.*))?$/
               );
               if (match) {
                  prop.format = match[1];
                  prop.description = match[2] ? match[2].trim() : undefined;
               }

               if (!prop.description) delete prop.description;
            }

            // Flag specific formats for C# validation attributes
            if (prop.format === "email") {
               prop["x-csharp-email"] = true;
            } else if (prop.format === "tel") {
               prop["x-csharp-phone"] = true;
            } else if (prop.format === "password") {
               prop["x-csharp-password"] = true;
            }

            // Handle DateTime defaults for C# (cannot use string literals)
            if (prop.format === "date-time" && prop.default) {
               prop["x-csharp-default"] = "DateTimeOffset.UtcNow";
            }

            // Handle collection defaults for C# and Python
            if (prop.default !== undefined) {
               if (
                  prop.type === "array" &&
                  Array.isArray(prop.default) &&
                  prop.default.length === 0
               ) {
                  prop["x-csharp-default"] = "new()";
               } else if (
                  prop.type === "object" &&
                  typeof prop.default === "object" &&
                  prop.default !== null &&
                  Object.keys(prop.default).length === 0
               ) {
                  prop["x-csharp-default"] = "new()";
               }
            }

            // Remove numeric range constraints as they're not required for generated models
            if (prop.minimum !== undefined) delete prop.minimum;
            if (prop.maximum !== undefined) delete prop.maximum;

            // Zod emits the ISO-8601 pattern alongside `format: date-time` (or
            // `date`). Models type these fields as `datetime`/`date`, where a
            // string `pattern` is an invalid Pydantic constraint; parsing
            // already enforces the format, so the redundant regex is dropped
            // here.
            if (prop.format === "date-time" || prop.format === "date") {
               delete prop.pattern;
            }
         }
      }
   }

   // Request models should not mark defaulted properties as required. Zod
   // defaults survive export, but required lists otherwise cause generated
   // clients/models to reject omitted fields that the API should populate
   // implicitly. This is domain policy, so it stays here; the mechanical
   // generator-compat transforms (closed objects, record schemas, numeric range
   // stripping, ref fixing, id stripping, trivial allOf collapsing) are applied
   // by the shared normalizer below.
   for (const [schemaName, schema] of Object.entries(filteredSchemas)) {
      if (
         schemaName.endsWith("Request") &&
         Array.isArray(schema.required) &&
         schema.properties
      ) {
         schema.required = schema.required.filter((propName) => {
            const prop = schema.properties[propName];
            if (!prop || typeof prop !== "object") {
               return true;
            }

            return (
               prop.default === undefined &&
               prop["x-csharp-default"] === undefined
            );
         });

         if (schema.required.length === 0) {
            delete schema.required;
         }
      }
   }

   // Post-processing for OAS 3.0 consistency and generator compatibility. All
   // transforms live in the shared normalizer so the export and the SDK spec
   // fetch cannot drift apart.
   normalizeSchemaComponents(filteredSchemas, {
      componentRefs: true,
      stripTopLevelIds: true,
      stripNumericRanges: true,
      normalizeAdditionalProperties: true,
      // Open objects stay `additionalProperties: true` in the models spec so
      // Python types their values as `Any` instead of nested objects. The API
      // spec keeps the OAS-3.0 object form for external generators.
      openAdditionalPropertiesSchema: true,
      collapseTrivialAllOfRefs: true
   });

   // Attach the stashed component descriptions after all structural
   // normalization is done, so the transforms run on the same shape they
   // produced before descriptions existed. Only components whose structure
   // already carries properties/unions are described; pure `$ref` aliases
   // (and single-ref `allOf` wrappers) keep their exact shape because adding
   // a description there changes the generated models from aliases to
   // structural wrappers.
   for (const [id, description] of preConversionDescriptions) {
      const component = filteredSchemas[id];
      if (
         !component ||
         typeof component !== "object" ||
         Array.isArray(component)
      ) {
         continue;
      }
      const componentKeys = Object.keys(component);
      const isRefAlias =
         componentKeys.includes("$ref") ||
         (componentKeys.includes("allOf") &&
            component.allOf.length === 1 &&
            componentKeys.every(
               (componentKey) =>
                  componentKey === "allOf" || componentKey === "description"
            ));
      if (isRefAlias || "description" in component) {
         continue;
      }
      component.description = description;
   }

   writeFileSync(
      outFile,
      JSON.stringify(
         {
            openapi: "3.0.3",
            info: {
               title: "Kontext Models",
               version: "1.0.0",
               description:
                  "A comprehensive collection of shared Kontext models."
            },
            paths: {},
            components: {
               schemas: filteredSchemas
            }
         },
         null,
         1
      ),
      "utf-8"
   );

   console.log(`✅ Wrote schema to ${outFile}`);
}

// Execute if run directly
if (import.meta.url === `file://${process.argv[1]}`) {
   main();
}

export { main };
