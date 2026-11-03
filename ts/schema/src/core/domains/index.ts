import type { z } from "zod";

export type CoreDomainSchemaRegistration = {
   /**
    * Global schema id. Must be stable; it drives OpenAPI component names and downstream codegen.
    */
   id: string;
   schema: z.ZodTypeAny;
};

/**
 * Core Domains: Central Exports
 *
 * Re-exports all domain schemas from the Zod-first authored schemas.
 * This is the single source of truth for all platform schemas.
 */

// Identity Domain (Phase 2.1) ✅
export * from "./identity/index.js";

// Additional C# ViewModels (not necessarily in Core OpenAPI) ✅
export * from "./base/index.js";
export * from "./events/index.js";
export * from "./infrastructure/index.js";
export * from "./jobs/index.js";
export * from "./knowledge/index.js";
export * from "./notifications/index.js";
export * from "./pagination.js";
export * from "./projects/index.js";
export * from "./tokens/index.js";

// Future domains will be added here:
// - Infrastructure Domain (Phase 2.2)
// - Projects Domain (Phase 2.3)
// - Subscriptions Domain (Phase 2.4)
// - Events & Notifications Domain (Phase 2.5)
// - Tokens Domain (Phase 2.6)
// - Shared/Base Domain (Phase 2.7)

/**
 * Domain Export Mapping
 *
 * This object provides a mapping of schema names to their Zod schemas
 * for use in the refresh-schemas (export-schemas.mjs) consolidation script.
 */
import * as Base from "./base/index.js";
import * as Events from "./events/index.js";
import * as Identity from "./identity/index.js";
import * as Infrastructure from "./infrastructure/index.js";
import * as Jobs from "./jobs/index.js";
import * as Knowledge from "./knowledge/index.js";
import * as Notifications from "./notifications/index.js";
import * as Pagination from "./pagination.js";
import * as Projects from "./projects/index.js";
import * as Tokens from "./tokens/index.js";

/**
 * Complete Core Domain Registry
 *
 * All hand-authored Zod-first schemas organized by domain.
 * This is the single source of truth for platform schemas.
 */
export const CORE_DOMAIN_SCHEMAS: CoreDomainSchemaRegistration[] = [
   // Identity Domain
   { id: "UserType", schema: Identity.UserTypeSchema },
   { id: "UserDetailsModel", schema: Identity.UserDetailsModelSchema },
   { id: "UserNavModel", schema: Identity.UserNavModelSchema },
   { id: "UserModel", schema: Identity.UserModelSchema },
   {
      id: "UserDetailsWithEmailModel",
      schema: Identity.UserDetailsWithEmailModelSchema
   },
   { id: "UserWithRolesModel", schema: Identity.UserWithRolesModelSchema },
   {
      id: "UserWithProjectRolesModel",
      schema: Identity.UserWithProjectRolesModelSchema
   },
   { id: "ServiceAccountModel", schema: Identity.ServiceAccountModelSchema },
   {
      id: "ServiceAccountKeyModel",
      schema: Identity.ServiceAccountKeyModelSchema
   },
   { id: "RsaKeyPairModel", schema: Identity.RsaKeyPairModelSchema },
   {
      id: "ApplicationPermissionModel",
      schema: Identity.ApplicationPermissionModelSchema
   },
   {
      id: "ApplicationRoleClaimModel",
      schema: Identity.ApplicationRoleClaimModelSchema
   },
   { id: "PermissionClaimModel", schema: Identity.PermissionClaimModelSchema },
   { id: "RoleClaimModel", schema: Identity.RoleClaimModelSchema },
   { id: "RoleModel", schema: Identity.RoleModelSchema },
   {
      id: "UserRegistrationRequest",
      schema: Identity.UserRegistrationRequestSchema
   },
   {
      id: "UpdateUserProfileRequest",
      schema: Identity.UpdateUserProfileRequestSchema
   },
   {
      id: "UpdateUserCredentialsRequest",
      schema: Identity.UpdateUserCredentialsRequestSchema
   },
   {
      id: "UpdateUserRequest",
      schema: Identity.UpdateUserRequestSchema
   },
   { id: "UserMetadata", schema: Identity.UserMetadataSchema },
   { id: "RoleMetadata", schema: Identity.RoleMetadataSchema },
   { id: "LoginRequest", schema: Identity.LoginRequestSchema },
   { id: "RefreshRequest", schema: Identity.RefreshRequestSchema },
   {
      id: "ForgotPasswordRequest",
      schema: Identity.ForgotPasswordRequestSchema
   },
   { id: "ResetPasswordRequest", schema: Identity.ResetPasswordRequestSchema },
   {
      id: "ResendConfirmationEmailRequest",
      schema: Identity.ResendConfirmationEmailRequestSchema
   },
   {
      id: "EnableTwoFactorRequest",
      schema: Identity.EnableTwoFactorRequestSchema
   },
   { id: "AccessTokenResponse", schema: Identity.AccessTokenResponseSchema },
   { id: "TwoFactorResponse", schema: Identity.TwoFactorResponseSchema },
   {
      id: "EmailConfirmationResult",
      schema: Identity.EmailConfirmationResultSchema
   },
   { id: "CreateRoleRequest", schema: Identity.CreateRoleRequestSchema },
   { id: "UpdateRoleRequest", schema: Identity.UpdateRoleRequestSchema },
   {
      id: "UserRoleAssignmentRequest",
      schema: Identity.UserRoleAssignmentRequestSchema
   },
   {
      id: "RoleClaimAssignmentRequest",
      schema: Identity.RoleClaimAssignmentRequestSchema
   },
   {
      id: "UpdateUserProjectRolesRequest",
      schema: Identity.UpdateUserProjectRolesRequestSchema
   },
   {
      id: "CreateServiceAccountRequest",
      schema: Identity.CreateServiceAccountRequestSchema
   },
   {
      id: "CreateServiceAccountKeyRequest",
      schema: Identity.CreateServiceAccountKeyRequestSchema
   },
   {
      id: "UpdateServiceAccountKeyRequest",
      schema: Identity.UpdateServiceAccountKeyRequestSchema
   },
   {
      id: "UpdateServiceAccountStatusRequest",
      schema: Identity.UpdateServiceAccountStatusRequestSchema
   },
   {
      id: "ServiceAccountAuthRequest",
      schema: Identity.ServiceAccountAuthRequestSchema
   },
   {
      id: "GenerateServiceAccountTokenRequest",
      schema: Identity.GenerateServiceAccountTokenRequestSchema
   },
   {
      id: "ServiceAccountTokenResponse",
      schema: Identity.ServiceAccountTokenResponseSchema
   },
   {
      id: "PaginatedListOfUserWithRolesModel",
      schema: Identity.PaginatedListOfUserWithRolesModelSchema
   },
   {
      id: "PaginatedListOfUserWithProjectRolesModel",
      schema: Identity.PaginatedListOfUserWithProjectRolesModelSchema
   },
   {
      id: "PaginatedListOfRoleModel",
      schema: Identity.PaginatedListOfRoleModelSchema
   },
   {
      id: "PaginatedListOfServiceAccountModel",
      schema: Identity.PaginatedListOfServiceAccountModelSchema
   },
   {
      id: "PaginatedListOfServiceAccountKeyModel",
      schema: Identity.PaginatedListOfServiceAccountKeyModelSchema
   },
   { id: "SetupRequest", schema: Identity.SetupRequestSchema },
   {
      id: "SetupStatusResponse",
      schema: Identity.SetupStatusResponseSchema
   },
   // Projects Domain
   { id: "AccessLevel", schema: Projects.AccessLevelSchema },
   { id: "ProjectFeature", schema: Projects.ProjectFeatureSchema },
   { id: "CreateProjectRequest", schema: Projects.CreateProjectRequestSchema },
   { id: "CreateProjectModel", schema: Projects.CreateProjectModelSchema },
   { id: "UpdateProjectRequest", schema: Projects.UpdateProjectRequestSchema },
   { id: "ProjectNavModel", schema: Projects.ProjectNavModelSchema },
   { id: "ProjectModel", schema: Projects.ProjectModelSchema },
   {
      id: "UpdateProjectConfigurationRequest",
      schema: Projects.UpdateProjectConfigurationRequestSchema
   },
   {
      id: "ProjectConfiguration",
      schema: Projects.ProjectConfigurationSchema
   },
   {
      id: "ProjectFileTypeConfig",
      schema: Projects.ProjectFileTypeConfigSchema
   },

   // Knowledge
   { id: "OkfConcept", schema: Knowledge.OkfConceptSchema },
   { id: "OkfAttestation", schema: Knowledge.OkfAttestationSchema },
   { id: "OkfProvenanceActor", schema: Knowledge.OkfProvenanceActorSchema },
   { id: "OkfSource", schema: Knowledge.OkfSourceSchema },

   // Infrastructure
   {
      id: "ModelAdapterType",
      schema: Infrastructure.ModelAdapterTypeSchema
   },
   {
      id: "ModelConnectionSourceType",
      schema: Infrastructure.ModelConnectionSourceTypeSchema
   },
   {
      id: "ModelConnectionKind",
      schema: Infrastructure.ModelConnectionKindSchema
   },
   {
      id: "ModelValidationState",
      schema: Infrastructure.ModelValidationStateSchema
   },
   {
      id: "ModelAvailability",
      schema: Infrastructure.ModelAvailabilitySchema
   },
   {
      id: "ModelReasoningEffort",
      schema: Infrastructure.ModelReasoningEffortSchema
   },
   {
      id: "ModelProviderConfigField",
      schema: Infrastructure.ModelProviderConfigFieldSchema
   },
   {
      id: "ModelCredentialRefField",
      schema: Infrastructure.ModelCredentialRefFieldSchema
   },
   {
      id: "ModelProviderDefinition",
      schema: Infrastructure.ModelProviderDefinitionSchema
   },
   {
      id: "ModelConnectionProviderConfig",
      schema: Infrastructure.ModelConnectionProviderConfigSchema
   },
   {
      id: "ModelConnectionCredentialRefs",
      schema: Infrastructure.ModelConnectionCredentialRefsSchema
   },
   { id: "FoundationModel", schema: Infrastructure.FoundationModelSchema },
   { id: "ModelConnection", schema: Infrastructure.ModelConnectionSchema },
   { id: "ModelCatalogEntry", schema: Infrastructure.ModelCatalogEntrySchema },
   { id: "CultureInfoModel", schema: Infrastructure.CultureInfoModelSchema },
   {
      id: "FileTypeConfiguration",
      schema: Infrastructure.FileTypeConfigurationSchema
   },
   {
      id: "CatalogConnectionKind",
      schema: Infrastructure.CatalogConnectionKindSchema
   },
   {
      id: "CatalogSourceCategory",
      schema: Infrastructure.CatalogSourceCategorySchema
   },
   {
      id: "CatalogConnectionAuthType",
      schema: Infrastructure.CatalogConnectionAuthTypeSchema
   },
   {
      id: "CatalogExecutionMode",
      schema: Infrastructure.CatalogExecutionModeSchema
   },
   {
      id: "CatalogSourceKind",
      schema: Infrastructure.CatalogSourceKindSchema
   },
   {
      id: "CatalogEntityType",
      schema: Infrastructure.CatalogEntityTypeSchema
   },
   {
      id: "CatalogConnectionCapabilities",
      schema: Infrastructure.CatalogConnectionCapabilitiesSchema
   },
   {
      id: "CatalogConnectionConfig",
      schema: Infrastructure.CatalogConnectionConfigSchema
   },
   {
      id: "CatalogConnection",
      schema: Infrastructure.CatalogConnectionSchema
   },
   {
      id: "CatalogConnectionRequest",
      schema: Infrastructure.CatalogConnectionRequestSchema
   },
   {
      id: "CatalogNamespaceSummary",
      schema: Infrastructure.CatalogNamespaceSummarySchema
   },
   {
      id: "CatalogColumn",
      schema: Infrastructure.CatalogColumnSchema
   },
   {
      id: "CatalogEntitySummary",
      schema: Infrastructure.CatalogEntitySummarySchema
   },
   {
      id: "CatalogEntityDetail",
      schema: Infrastructure.CatalogEntityDetailSchema
   },
   {
      id: "CatalogSyncStatus",
      schema: Infrastructure.CatalogSyncStatusSchema
   },
   {
      id: "CatalogConnectionValidationResult",
      schema: Infrastructure.CatalogConnectionValidationResultSchema
   },
   {
      id: "CatalogProviderDefinition",
      schema: Infrastructure.CatalogProviderDefinitionSchema
   },

   // Base / Shared
   { id: "BaseModel", schema: Base.BaseModelSchema },
   { id: "SortBy", schema: Base.SortBySchema },
   { id: "ConfigModel", schema: Base.ConfigModelSchema },
   { id: "SiteConfigResponse", schema: Base.SiteConfigResponseSchema },
   { id: "PythonPackageSource", schema: Base.PythonPackageSourceSchema },
   {
      id: "PythonEnvironmentPackage",
      schema: Base.PythonEnvironmentPackageSchema
   },
   { id: "PythonEnvironmentInfo", schema: Base.PythonEnvironmentInfoSchema },
   { id: "ProblemTypes", schema: Base.ProblemTypesSchema },
   { id: "FileFormatType", schema: Base.FileFormatTypeSchema },
   { id: "IFormFile", schema: Base.IFormFileSchema },
   { id: "ProblemDetails", schema: Base.ProblemDetailsSchema },
   {
      id: "HttpValidationProblemDetails",
      schema: Base.HttpValidationProblemDetailsSchema
   },

   // Events
   { id: "EventType", schema: Events.EventTypeSchema },
   { id: "ChannelType", schema: Events.ChannelTypeSchema },
   { id: "BotInfo", schema: Events.BotInfoSchema },
   { id: "EventModel", schema: Events.EventModelSchema },
   { id: "CreateEventRequest", schema: Events.CreateEventRequestSchema },

   // Notifications
   { id: "NotificationType", schema: Notifications.NotificationTypeSchema },
   { id: "NotificationModel", schema: Notifications.NotificationModelSchema },
   {
      id: "CreateNotificationRequest",
      schema: Notifications.CreateNotificationRequestSchema
   },

   // Jobs
   { id: "JobCategory", schema: Jobs.JobCategorySchema },
   { id: "JobExecutionRuntime", schema: Jobs.JobExecutionRuntimeSchema },
   { id: "JobParameterType", schema: Jobs.JobParameterTypeSchema },
   { id: "JobRetryStrategy", schema: Jobs.JobRetryStrategySchema },
   { id: "JobRunSortBy", schema: Jobs.JobRunSortBySchema },
   { id: "JobRunStatus", schema: Jobs.JobRunStatusSchema },
   { id: "JobTriggerType", schema: Jobs.JobTriggerTypeSchema },
   { id: "TriggerActorType", schema: Jobs.TriggerActorTypeSchema },
   { id: "TriggerActorModel", schema: Jobs.TriggerActorModelSchema },
   { id: "LogLevel", schema: Jobs.LogLevelSchema },
   { id: "ExecutionRunKind", schema: Jobs.ExecutionRunKindSchema },
   { id: "ExecutionRunStatus", schema: Jobs.ExecutionRunStatusSchema },
   { id: "JobModel", schema: Jobs.JobModelSchema },
   { id: "CreateJobRequest", schema: Jobs.CreateJobRequestSchema },
   { id: "UpdateJobRequest", schema: Jobs.UpdateJobRequestSchema },
   { id: "JobTriggerModel", schema: Jobs.JobTriggerModelSchema },
   {
      id: "CreateJobTriggerRequest",
      schema: Jobs.CreateJobTriggerRequestSchema
   },
   {
      id: "UpdateJobTriggerRequest",
      schema: Jobs.UpdateJobTriggerRequestSchema
   },
   {
      id: "JobExecutionSummaryModel",
      schema: Jobs.JobExecutionSummaryModelSchema
   },
   { id: "JobRunModel", schema: Jobs.JobRunModelSchema },
   { id: "ExecutionRunModel", schema: Jobs.ExecutionRunModelSchema },
   { id: "ExecuteJobRequest", schema: Jobs.ExecuteJobRequestSchema },
   { id: "ScheduleJobRequest", schema: Jobs.ScheduleJobRequestSchema },
   { id: "JobRunLogModel", schema: Jobs.JobRunLogModelSchema },
   { id: "ExecutionLogModel", schema: Jobs.ExecutionLogModelSchema },
   { id: "ExecutionEventModel", schema: Jobs.ExecutionEventModelSchema },
   { id: "JobRunQueryRequest", schema: Jobs.JobRunQueryRequestSchema },
   {
      id: "ProgrammaticExecuteJobRequest",
      schema: Jobs.ProgrammaticExecuteJobRequestSchema
   },
   { id: "ExecuteJobNowRequest", schema: Jobs.ExecuteJobNowRequestSchema },
   { id: "JobSortBy", schema: Jobs.JobSortBySchema },
   { id: "ResetJobRunsRequest", schema: Jobs.ResetJobRunsRequestSchema },
   {
      id: "ResetAllFailedJobsRequest",
      schema: Jobs.ResetAllFailedJobsRequestSchema
   },
   {
      id: "UpdateJobRunParametersRequest",
      schema: Jobs.UpdateJobRunParametersRequestSchema
   },
   {
      id: "ExecutionRunInputRequest",
      schema: Jobs.ExecutionRunInputRequestSchema
   },
   {
      id: "ExecutionRunCancelRequest",
      schema: Jobs.ExecutionRunCancelRequestSchema
   },
   {
      id: "ExecutionRunRetryRequest",
      schema: Jobs.ExecutionRunRetryRequestSchema
   },
   {
      id: "UpdateJobRunStatusRequest",
      schema: Jobs.UpdateJobRunStatusRequestSchema
   },
   {
      id: "UpdateJobRunProgressRequest",
      schema: Jobs.UpdateJobRunProgressRequestSchema
   },
   {
      id: "UpdateJobRunWorkerRequest",
      schema: Jobs.UpdateJobRunWorkerRequestSchema
   },
   {
      id: "AddJobRunLogRequest",
      schema: Jobs.AddJobRunLogRequestSchema
   },
   {
      id: "CreateJobRunLogRequest",
      schema: Jobs.CreateJobRunLogRequestSchema
   },
   {
      id: "SuccessResultData",
      schema: Jobs.SuccessResultDataSchema
   },
   {
      id: "JobResultModel",
      schema: Jobs.JobResultModelSchema
   },
   { id: "JobResetResponse", schema: Jobs.JobResetResponseSchema },
   {
      id: "UnifiedJobParameterModel",
      schema: Jobs.UnifiedJobParameterModelSchema
   },
   { id: "UnifiedJobTypeModel", schema: Jobs.UnifiedJobTypeModelSchema },
   {
      id: "UnifiedJobTypesResponse",
      schema: Jobs.UnifiedJobTypesResponseSchema
   },
   {
      id: "ScheduledJobConfiguration",
      schema: Jobs.ScheduledJobConfigurationSchema
   },
   { id: "JobParameterModel", schema: Jobs.JobParameterModelSchema },
   { id: "JobRegistrationModel", schema: Jobs.JobRegistrationModelSchema },

   // Tokens
   { id: "TokenPurpose", schema: Tokens.TokenPurposeSchema },
   { id: "TokenModel", schema: Tokens.TokenModelSchema },
   { id: "ValidateTokenRequest", schema: Tokens.ValidateTokenRequestSchema },
   { id: "CreateTokenRequest", schema: Tokens.CreateTokenRequestSchema },

   // Paginated Responses (Zod-first, using explicit refs to prevent ItemsInner generation)
   // Note: Identity-related paginated models (User, Role, ServiceAccount) are in the identity domain
   {
      id: "PaginatedListOfEventModel",
      schema: Pagination.PaginatedListOfEventModelSchema
   },
   {
      id: "PaginatedListOfJobModel",
      schema: Pagination.PaginatedListOfJobModelSchema
   },
   {
      id: "PaginatedListOfJobRunModel",
      schema: Pagination.PaginatedListOfJobRunModelSchema
   },
   {
      id: "PaginatedListOfExecutionRunModel",
      schema: Pagination.PaginatedListOfExecutionRunModelSchema
   },
   {
      id: "PaginatedListOfNotificationModel",
      schema: Pagination.PaginatedListOfNotificationModelSchema
   },
   {
      id: "PaginatedListOfProjectModel",
      schema: Pagination.PaginatedListOfProjectModelSchema
   },
   {
      id: "PaginatedListOfTokenModel",
      schema: Pagination.PaginatedListOfTokenModelSchema
   }
];
