import { z } from "zod";

import { BaseModelSchema } from "../base/index.js";
import {
   JobCategorySchema,
   JobExecutionRuntimeSchema,
   JobParameterTypeSchema,
   JobRetryStrategySchema,
   JobRunStatusSchema,
   JobTriggerTypeSchema,
   LogLevelSchema,
   TriggerActorModelSchema
} from "./types.js";

export * from "./execution";
export * from "./types.js";

/**
 * Core Domain: Jobs (C#-only models not currently in Core OpenAPI)
 *
 * Sources:
 * - backend/Kontext.Data/ViewModels/Jobs/JobViewModels.cs
 * - backend/Kontext.Data/ViewModels/Jobs/JobRunViewModels.cs
 * - backend/Kontext.Data/ViewModels/Jobs/JobRegistrationViewModels.cs
 * - backend/Kontext.Data/ViewModels/Jobs/ScheduledJobConfiguration.cs
 * - backend/Kontext.Data/ViewModels/Jobs/UnifiedJobTypesViewModel.cs
 * - backend/Kontext.Data/ViewModels/Jobs/JobResetViewModels.cs
 */

export const JobResetResponseSchema = z
   .object({
      resetCount: z.number().int(),
      message: z.string()
   })
   .describe("Job Reset Response");

export type JobResetResponse = z.infer<typeof JobResetResponseSchema>;

export const UnifiedJobParameterModelSchema = z
   .object({
      name: z.string(),
      type: z.lazy(() => JobParameterTypeSchema),
      required: z.boolean(),
      description: z.string().nullable().optional(),
      defaultValue: z.any().nullable().optional(),
      possibleValues: z.array(z.string()).nullable().optional(),
      maxLength: z.number().int().nullable().optional()
   })
   .describe("Unified Job Parameter Model");

export type UnifiedJobParameterModel = z.infer<
   typeof UnifiedJobParameterModelSchema
>;

export const UnifiedJobTypeModelSchema = z
   .object({
      type: z.string(),
      name: z.string(),
      description: z.string(),
      category: z.lazy(() => JobCategorySchema),
      runtime: z.lazy(() => JobExecutionRuntimeSchema),
      parameters: z
         .array(z.lazy(() => UnifiedJobParameterModelSchema))
         .default([]),
      isSystemJob: z.boolean(),
      requiredPermissions: z.array(z.string()).default([]),
      icon: z.string().nullable().optional()
   })
   .describe("Unified Job Type Model");

export type UnifiedJobTypeModel = z.infer<typeof UnifiedJobTypeModelSchema>;

export const UnifiedJobTypesResponseSchema = z
   .object({
      jobs: z.array(z.lazy(() => UnifiedJobTypeModelSchema)).default([])
   })
   .describe("Unified Job Types Response");

export type UnifiedJobTypesResponse = z.infer<
   typeof UnifiedJobTypesResponseSchema
>;

export const JobModelSchema = BaseModelSchema.extend({
   name: z.string(),
   description: z.string().nullable().optional(),
   type: z.string(),
   schedule: z.string().nullable().optional(),
   parameters: z.string().nullable().optional(),
   timeout: z.number().int(),
   isEnabled: z.boolean(),
   retryStrategy: z.lazy(() => JobRetryStrategySchema),
   retryLimit: z.number().int(),
   projectId: z.guid().nullable().optional(),
   projectName: z.string().nullable().optional(),
   ownerId: z.guid().nullable().optional(),
   dateCreated: z.iso.datetime({ offset: true }),
   dateModified: z.iso.datetime({ offset: true }).nullable().optional(),
   lastRunStatus: z
      .lazy(() => JobRunStatusSchema)
      .nullable()
      .optional(),
   lastRunDate: z.iso.datetime({ offset: true }).nullable().optional(),
   nextRunDate: z.iso.datetime({ offset: true }).nullable().optional(),
   totalRuns: z.number().int().describe("format: int64"),
   successfulRuns: z.number().int().describe("format: int64"),
   failedRuns: z.number().int().describe("format: int64"),
   inProgressRuns: z.number().int().describe("format: int64"),
   totalRunDurationSeconds: z
      .number()
      .describe("format: double")
      .nullable()
      .optional()
}).describe("Job Model");

export type JobModel = z.infer<typeof JobModelSchema>;

export const CreateJobRequestSchema = z
   .object({
      name: z
         .string()
         .min(1, "Name is required")
         .max(255, "Name must not exceed 255 characters")
         .regex(
            /^[a-zA-Z0-9\s\-_.]+$/,
            "Job name can only contain letters, numbers, spaces, hyphens, underscores, and periods"
         ),
      description: z
         .string()
         .max(4000, "Description must not exceed 4000 characters")
         .nullable()
         .optional(),
      type: z
         .string()
         .min(1, "Type is required")
         .max(500, "Type must not exceed 500 characters")
         .regex(
            /^[a-zA-Z0-9.\-_]+$/,
            "Job type must be a valid class name format"
         ),
      schedule: z
         .string()
         .max(100, "Schedule must not exceed 100 characters")
         .nullable()
         .optional(),
      parameters: z.string().nullable().optional(),
      timeout: z
         .number()
         .int()
         .min(60, "Timeout must be at least 60 seconds")
         .max(86400, "Timeout must not exceed 86400 seconds")
         .default(3600),
      isEnabled: z.boolean().default(false),
      retryStrategy: z.lazy(() => JobRetryStrategySchema).default("None"),
      retryLimit: z
         .number()
         .int()
         .min(0, "Retry limit must be at least 0")
         .max(10, "Retry limit must not exceed 10")
         .default(0),
      projectId: z.guid().nullable().optional()
   })
   .describe("Create Job Request");

export type CreateJobRequest = z.infer<typeof CreateJobRequestSchema>;

export const UpdateJobRequestSchema = z
   .object({
      name: z
         .string()
         .min(1, "Name is required")
         .max(255, "Name must not exceed 255 characters")
         .regex(
            /^[a-zA-Z0-9\s\-_.]+$/,
            "Job name can only contain letters, numbers, spaces, hyphens, underscores, and periods"
         ),
      type: z
         .string()
         .min(1, "Type is required")
         .max(500, "Type must not exceed 500 characters")
         .regex(
            /^[a-zA-Z0-9.\-_]+$/,
            "Job type must be a valid class name format"
         ),
      description: z
         .string()
         .max(4000, "Description must not exceed 4000 characters")
         .nullable()
         .optional(),
      schedule: z
         .string()
         .max(100, "Schedule must not exceed 100 characters")
         .nullable()
         .optional(),
      parameters: z.string().nullable().optional(),
      timeout: z
         .number()
         .int()
         .min(60, "Timeout must be at least 60 seconds")
         .max(86400, "Timeout must not exceed 86400 seconds"),
      isEnabled: z.boolean(),
      retryStrategy: z.lazy(() => JobRetryStrategySchema),
      retryLimit: z
         .number()
         .int()
         .min(0, "Retry limit must be at least 0")
         .max(10, "Retry limit must not exceed 10")
   })
   .describe("Update Job Request");

export type UpdateJobRequest = z.infer<typeof UpdateJobRequestSchema>;

export const JobTriggerModelSchema = BaseModelSchema.extend({
   jobId: z.guid(),
   triggerType: z.lazy(() => JobTriggerTypeSchema),
   configuration: z.string(),
   triggeredBy: z
      .lazy(() => TriggerActorModelSchema)
      .nullable()
      .optional(),
   createdAt: z.iso.datetime({ offset: true }),
   isPaused: z.boolean(),
   pausedAt: z.iso.datetime({ offset: true }).nullable().optional(),
   isDeleted: z.boolean(),
   deletedAt: z.iso.datetime({ offset: true }).nullable().optional(),
   lastScheduledRunAt: z.iso.datetime({ offset: true }).nullable().optional(),
   job: z
      .lazy(() => JobModelSchema)
      .nullable()
      .optional()
}).describe("Job Trigger Model");

export type JobTriggerModel = z.infer<typeof JobTriggerModelSchema>;

export const CreateJobTriggerRequestSchema = z
   .object({
      jobId: z.guid(),
      triggerType: z.lazy(() => JobTriggerTypeSchema),
      configuration: z.string(),
      triggeredBy: z
         .lazy(() => TriggerActorModelSchema)
         .nullable()
         .optional()
   })
   .describe("Create Job Trigger Request");

export type CreateJobTriggerRequest = z.infer<
   typeof CreateJobTriggerRequestSchema
>;

export const UpdateJobTriggerRequestSchema = z
   .object({
      triggerType: z.lazy(() => JobTriggerTypeSchema),
      configuration: z.string(),
      isPaused: z.boolean().nullable().optional()
   })
   .describe("Update Job Trigger Request");

export type UpdateJobTriggerRequest = z.infer<
   typeof UpdateJobTriggerRequestSchema
>;

export const JobExecutionSummaryModelSchema = z
   .object({
      jobId: z.guid(),
      jobName: z.string(),
      totalRuns: z.number().int().describe("format: int64"),
      successfulRuns: z.number().int().describe("format: int64"),
      failedRuns: z.number().int().describe("format: int64"),
      canceledRuns: z.number().int().describe("format: int64"),
      timedOutRuns: z.number().int().describe("format: int64"),
      lastRunDate: z.iso.datetime({ offset: true }).nullable().optional(),
      lastRunStatus: z
         .lazy(() => JobRunStatusSchema)
         .nullable()
         .optional(),
      nextScheduledRun: z.iso.datetime({ offset: true }).nullable().optional(),
      successRate: z.number().describe("format: double")
   })
   .describe("Job Execution Summary Model");

export type JobExecutionSummaryModel = z.infer<
   typeof JobExecutionSummaryModelSchema
>;

export const JobRunModelSchema = BaseModelSchema.extend({
   jobId: z.guid(),
   jobTriggerId: z.guid().nullable().optional(),
   projectId: z.guid().nullable().optional(),
   projectName: z.string().nullable().optional(),
   ownerId: z.guid().nullable().optional(),
   status: z.lazy(() => JobRunStatusSchema),
   progress: z.number().int().nullable().optional(),
   startedAt: z.iso.datetime({ offset: true }).nullable().optional(),
   completedAt: z.iso.datetime({ offset: true }).nullable().optional(),
   parameters: z.string().nullable().optional(),
   displaySummary: z
      .string()
      .nullable()
      .optional()
      .describe(
         "Optional short, type-specific summary derived from the job parameters (e.g. the SQL for a query job)"
      ),
   executionId: z.string().nullable().optional(),
   worker: z.string().nullable().optional(),
   attemptCount: z.number().int(),
   resultType: z.string().nullable().optional(),
   resultData: z.string().nullable().optional(),
   errorMessage: z.string().nullable().optional(),
   errorStack: z.string().nullable().optional(),
   createdAt: z.iso.datetime({ offset: true }),
   job: z
      .lazy(() => JobModelSchema)
      .nullable()
      .optional(),
   jobTrigger: z
      .lazy(() => JobTriggerModelSchema)
      .nullable()
      .optional()
}).describe("Job Run Model");

export type JobRunModel = z.infer<typeof JobRunModelSchema>;

export const ExecuteJobRequestSchema = z
   .object({
      jobId: z.guid(),
      projectId: z.guid().nullable().optional(),
      triggeredBy: z
         .lazy(() => TriggerActorModelSchema)
         .describe("Actor or artifact that triggered this job"),
      jobTriggerId: z.guid().nullable().optional(),
      triggerSource: z.lazy(() => JobTriggerTypeSchema),
      parameters: z.string().nullable().optional(),
      executionId: z.string().nullable().optional(),
      initialStatus: z
         .lazy(() => JobRunStatusSchema)
         .nullable()
         .optional(),
      reason: z.string().max(255).nullable().optional()
   })
   .describe("Execute Job Request");

export type ExecuteJobRequest = z.infer<typeof ExecuteJobRequestSchema>;

export const ScheduleJobRequestSchema = z
   .object({
      jobId: z.guid(),
      scheduledAt: z.iso.datetime({ offset: true }),
      parameters: z.string().nullable().optional(),
      reason: z.string().max(255).nullable().optional()
   })
   .describe("Schedule Job Request");

export type ScheduleJobRequest = z.infer<typeof ScheduleJobRequestSchema>;

export const SuccessResultDataSchema = z
   .object({
      processedItems: z
         .number()
         .int()
         .describe("format: int64")
         .nullable()
         .optional(),
      createdItems: z
         .number()
         .int()
         .describe("format: int64")
         .nullable()
         .optional(),
      updatedItems: z
         .number()
         .int()
         .describe("format: int64")
         .nullable()
         .optional(),
      deletedItems: z
         .number()
         .int()
         .describe("format: int64")
         .nullable()
         .optional(),
      executedAt: z.iso.datetime({ offset: true }).nullable().optional(),
      durationSeconds: z
         .number()
         .describe("format: double")
         .nullable()
         .optional()
   })
   .describe("Success Result Data Model");

export type SuccessResultData = z.infer<typeof SuccessResultDataSchema>;

export const JobResultModelSchema = z
   .object({
      success: z.boolean(),
      message: z.string().nullable().optional(),
      data: z.record(z.string(), z.any()).nullable().optional(),
      resultData: z
         .lazy(() => SuccessResultDataSchema)
         .nullable()
         .optional(),
      errorMessage: z.string().nullable().optional()
   })
   .describe("Job Result Model");

export type JobResultModel = z.infer<typeof JobResultModelSchema>;

export const JobRunLogModelSchema = z
   .object({
      id: z.guid(),
      jobRunId: z.guid(),
      jobId: z.guid(),
      timestamp: z.iso.datetime({ offset: true }),
      level: z.lazy(() => LogLevelSchema),
      message: z.string().max(2000),
      data: z.string().nullable().optional()
   })
   .describe("Job Run Log Model");

export type JobRunLogModel = z.infer<typeof JobRunLogModelSchema>;

export const JobRunQueryRequestSchema = z
   .object({
      jobId: z.guid().nullable().optional(),
      projectId: z.guid().nullable().optional(),
      status: z
         .lazy(() => JobRunStatusSchema)
         .nullable()
         .optional(),
      startDate: z.iso.datetime({ offset: true }).nullable().optional(),
      endDate: z.iso.datetime({ offset: true }).nullable().optional(),
      page: z.number().int().min(1, "Page number must be at least 1"),
      pageSize: z
         .number()
         .int()
         .min(1, "Page size must be at least 1")
         .max(60, "Page size must not exceed 60"),
      sortBy: z
         .string()
         .max(50, "Sort field name is too long")
         .regex(
            /^[a-zA-Z_][a-zA-Z0-9_]*$/,
            "Sort field must be a valid property name"
         )
         .nullable()
         .optional(),
      sortDescending: z.boolean()
   })
   .describe("Job Run Query Request");

export type JobRunQueryRequest = z.infer<typeof JobRunQueryRequestSchema>;

export const ProgrammaticExecuteJobRequestSchema = z
   .object({
      parameters: z.object({}).nullable().optional(),
      triggeredBy: z
         .lazy(() => TriggerActorModelSchema)
         .nullable()
         .optional(),
      executionId: z.string().nullable().optional(),
      initialStatus: z.lazy(() => JobRunStatusSchema),
      triggerSource: z.lazy(() => JobTriggerTypeSchema)
   })
   .describe("Programmatic Execute Job Request");

export type ProgrammaticExecuteJobRequest = z.infer<
   typeof ProgrammaticExecuteJobRequestSchema
>;

export const UpdateJobRunStatusRequestSchema = z
   .object({
      runId: z.guid().nullable().optional(),
      status: z.lazy(() => JobRunStatusSchema),
      errorMessage: z.string().max(1000).nullable().optional(),
      resultData: z.object({}).nullable().optional()
   })
   .describe("Update Job Run Status Request");

export type UpdateJobRunStatusRequest = z.infer<
   typeof UpdateJobRunStatusRequestSchema
>;

export const UpdateJobRunProgressRequestSchema = z
   .object({
      runId: z.guid().nullable().optional(),
      progress: z.number().int().min(0).max(100)
   })
   .describe("Update Job Run Progress Request");

export type UpdateJobRunProgressRequest = z.infer<
   typeof UpdateJobRunProgressRequestSchema
>;

export const UpdateJobRunWorkerRequestSchema = z
   .object({
      runId: z.guid().nullable().optional(),
      worker: z.string().max(255)
   })
   .describe("Update Job Run Worker Request");

export type UpdateJobRunWorkerRequest = z.infer<
   typeof UpdateJobRunWorkerRequestSchema
>;

export const CreateJobRunLogRequestSchema = z
   .object({
      jobRunId: z.guid(),
      level: z.lazy(() => LogLevelSchema),
      message: z.string().max(2000),
      data: z.string().nullable().optional()
   })
   .describe("Create Job Run Log Request");

export type CreateJobRunLogRequest = z.infer<
   typeof CreateJobRunLogRequestSchema
>;

export const AddJobRunLogRequestSchema = z
   .object({
      jobRunId: z.guid().nullable().optional(),
      level: z.lazy(() => LogLevelSchema),
      message: z.string().max(2000),
      data: z.any().nullable().optional()
   })
   .describe("Add Job Run Log Request");

export type AddJobRunLogRequest = z.infer<typeof AddJobRunLogRequestSchema>;

export const ScheduledJobConfigurationSchema = z
   .object({
      schedule: z.string().nullable().optional()
   })
   .describe("Scheduled Job Configuration");

export type ScheduledJobConfiguration = z.infer<
   typeof ScheduledJobConfigurationSchema
>;

export const JobParameterModelSchema = z
   .object({
      name: z.string(),
      displayName: z.string(),
      description: z.string(),
      parameterType: z.string(),
      isRequired: z.boolean(),
      defaultStringValue: z.string().nullable().optional(),
      defaultIntegerValue: z.number().int().nullable().optional(),
      defaultBooleanValue: z.boolean().nullable().optional(),
      possibleValues: z.array(z.string()).nullable().optional(),
      maxLength: z.number().int().nullable().optional()
   })
   .describe("Job Parameter Model");

export type JobParameterModel = z.infer<typeof JobParameterModelSchema>;

export const JobRegistrationModelSchema = z
   .object({
      type: z.string(),
      name: z.string(),
      description: z.string(),
      category: z.string(),
      isSystemJob: z.boolean(),
      requiredPermissions: z
         .array(z.string())
         .nullable()
         .optional()
         .default([]),
      iconName: z.string(),
      allowsConcurrentExecution: z.boolean(),
      parameters: z
         .array(z.lazy(() => JobParameterModelSchema))
         .nullable()
         .optional()
         .default([])
   })
   .describe("Job Registration Model");

export type JobRegistrationModel = z.infer<typeof JobRegistrationModelSchema>;
