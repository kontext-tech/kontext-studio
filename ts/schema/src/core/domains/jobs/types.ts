import { z } from "zod";

/**
 * Job Category enum
 */
export const JobCategorySchema = z
   .enum([
      "General",
      "DataManagement",
      "ContentManagement",
      "SystemMaintenance",
      "Import",
      "Export",
      "Notification",
      "Cleanup",
      "Analytics",
      "Security",
      "Maintenance",
      "Processing",
      "DataProcessing"
   ])
   .describe("Job Category enum");

export type JobCategory = z.infer<typeof JobCategorySchema>;
export const JobCategory = JobCategorySchema.enum;

/**
 * Job Execution Runtime enum
 */
export const JobExecutionRuntimeSchema = z
   .enum(["DotNet", "Python"])
   .describe("Job Execution Runtime enum");

export type JobExecutionRuntime = z.infer<typeof JobExecutionRuntimeSchema>;
export const JobExecutionRuntime = JobExecutionRuntimeSchema.enum;

/**
 * Job Parameter Type enum
 */
export const JobParameterTypeSchema = z
   .enum(["String", "Integer", "Boolean"])
   .describe("Job Parameter Type enum");

export type JobParameterType = z.infer<typeof JobParameterTypeSchema>;
export const JobParameterType = JobParameterTypeSchema.enum;

/**
 * Job Retry Strategy enum
 */
export const JobRetryStrategySchema = z
   .enum(["None", "Immediate", "Linear", "Exponential", "Fixed"])
   .describe("Job Retry Strategy enum");

export type JobRetryStrategy = z.infer<typeof JobRetryStrategySchema>;
export const JobRetryStrategy = JobRetryStrategySchema.enum;

/**
 * Job Run Status enum
 */
export const JobRunStatusSchema = z
   .enum([
      "Queued",
      "Dispatched",
      "Running",
      "Succeeded",
      "Failed",
      "Canceled",
      "TimedOut",
      "DeadLettered"
   ])
   .describe("Job Run Status enum");

export type JobRunStatus = z.infer<typeof JobRunStatusSchema>;
export const JobRunStatus = JobRunStatusSchema.enum;

/**
 * Job Trigger Type enum
 */
export const JobTriggerTypeSchema = z
   .enum(["Scheduled", "Event", "Manual", "Dependency", "Retry", "Interactive"])
   .describe("Job Trigger Type enum");

export type JobTriggerType = z.infer<typeof JobTriggerTypeSchema>;
export const JobTriggerType = JobTriggerTypeSchema.enum;

/**
 * Trigger Actor Type enum - the kind of actor/entity that triggered a job
 */
export const TriggerActorTypeSchema = z
   .enum([
      "User",
      "Agent",
      "Notebook",
      "ChatSession",
      "File",
      "Scheduler",
      "Event",
      "System"
   ])
   .describe("Trigger Actor Type enum");

export type TriggerActorType = z.infer<typeof TriggerActorTypeSchema>;
export const TriggerActorType = TriggerActorTypeSchema.enum;

/**
 * Structured reference to the actor or artifact that triggered a job.
 *
 * `type` identifies the kind of actor and `id` optionally identifies the
 * specific artifact (user id, notebook id, chat session id, ...) so callers can
 * link to it. Use `System` with a subsystem name in `id` for internal actors.
 */
export const TriggerActorModelSchema = z
   .object({
      type: TriggerActorTypeSchema,
      id: z.string().nullable().optional()
   })
   .describe(
      "Structured reference to the actor or artifact that triggered a job"
   );

export type TriggerActorModel = z.infer<typeof TriggerActorModelSchema>;

/**
 * Log Level enum
 */
export const LogLevelSchema = z
   .enum([
      "Trace",
      "Debug",
      "Information",
      "Warning",
      "Error",
      "Critical",
      "None"
   ])
   .describe("Log Level enum");

export type LogLevel = z.infer<typeof LogLevelSchema>;
export const LogLevel = LogLevelSchema.enum;

/**
 * Job Run Sort By enum - for sorting job run lists
 */
const JobRunSortByEnumSchema = z.enum([
   "DateCreated",
   "StartedAt",
   "CompletedAt",
   "Duration",
   "Status",
   "JobName"
]);
export const JobRunSortBy = JobRunSortByEnumSchema.enum;

export const JobRunSortBySchema = JobRunSortByEnumSchema.default(
   "DateCreated"
).describe("Job Run Sort By model from Kontext API");

export type JobRunSortBy = z.infer<typeof JobRunSortBySchema>;

/**
 * Job Sort By enum - for sorting job lists
 */
const JobSortByEnumSchema = z.enum([
   "DateCreated",
   "Name",
   "DateModified",
   "Type",
   "LastRunDate"
]);
export const JobSortBy = JobSortByEnumSchema.enum;

export const JobSortBySchema = JobSortByEnumSchema.default(
   "DateCreated"
).describe("Job Sort By model from Kontext API");

export type JobSortBy = z.infer<typeof JobSortBySchema>;

/**
 * Execute Job Now Request - for immediate job execution
 */
export const ExecuteJobNowRequestSchema = z
   .object({
      parameters: z.object({}).nullable().optional(),
      executionId: z.string().nullable().optional()
   })
   .describe("Execute Job Now Request model from Kontext API");

export type ExecuteJobNowRequest = z.infer<typeof ExecuteJobNowRequestSchema>;

/**
 * Reset Job Runs Request - reset specific job runs
 */
export const ResetJobRunsRequestSchema = z
   .object({
      jobRunIds: z.array(z.guid()),
      reason: z.string().min(1).max(500)
   })
   .describe("Reset Job Runs Request model from Kontext API");

export type ResetJobRunsRequest = z.infer<typeof ResetJobRunsRequestSchema>;

/**
 * Reset All Failed Jobs Request - reset all failed jobs in a project
 */
export const ResetAllFailedJobsRequestSchema = z
   .object({
      projectId: z.guid().nullable().optional(),
      reason: z.string().min(1).max(500)
   })
   .describe("Reset All Failed Jobs Request model from Kontext API");

export type ResetAllFailedJobsRequest = z.infer<
   typeof ResetAllFailedJobsRequestSchema
>;

/**
 * Update Job Run Parameters Request - update parameters for a job run
 */
export const UpdateJobRunParametersRequestSchema = z
   .object({
      parameters: z.string(),
      reason: z.string().min(3).max(500)
   })
   .describe("Update Job Run Parameters Request model from Kontext API");

export type UpdateJobRunParametersRequest = z.infer<
   typeof UpdateJobRunParametersRequestSchema
>;
