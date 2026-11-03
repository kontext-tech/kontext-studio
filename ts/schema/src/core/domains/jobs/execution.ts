import { z } from "zod";

import { ToolCallSchema } from "../../../ai/streaming.js";
import { JobRunStatusSchema, LogLevelSchema } from "./types.js";

/**
 * Job execution schemas for queue messages and responses.
 *
 * These schemas define the structure for self-contained job execution messages
 * that workers can process without needing database lookups.
 */

// ============================================================================
// Job Execution Message (Queue Message)
// ============================================================================

/**
 * Self-contained job execution message.
 *
 * Contains all information needed to execute a job without DB lookups.
 * Workers receive this message from the queue and can execute directly
 * without querying the database for job details.
 */
export const JobExecutionMessageSchema = z
   .object({
      // Identifiers
      jobRunId: z.guid().describe("Unique job run identifier"),
      executionId: z
         .string()
         .nullish()
         .describe("Human-readable execution identifier (timestamp-based)"),
      projectId: z.guid().describe("Project context for the job"),

      // Job type and execution
      jobType: z
         .string()
         .describe(
            "Job type from registry (e.g., 'python.jobs.ExecuteQueryJob')"
         ),
      jobName: z.string().describe("Human-readable job name"),
      timeoutMinutes: z
         .number()
         .int()
         .min(1)
         .max(1440)
         .default(60)
         .describe("Job timeout in minutes (1-1440)"),

      // Parameters (job-specific)
      parameters: z
         .record(z.string(), z.unknown())
         .default({})
         .describe("Job-specific parameters"),

      // Metadata
      createdAt: z.iso
         .datetime({ offset: true })
         .describe("ISO 8601 datetime string with timezone"),
      priority: z
         .number()
         .int()
         .min(0)
         .max(10)
         .default(5)
         .describe("Job priority (0-10, higher = more important)")
   })
   .describe("Self-contained job execution message for queue processing");

export type JobExecutionMessage = z.infer<typeof JobExecutionMessageSchema>;

// ============================================================================
// Job Dispatch Response (API Response)
// ============================================================================

/**
 * Response for async job dispatch endpoints.
 *
 * Returned when a job is successfully queued for execution.
 * Clients can use the jobRunId to poll for results.
 */
export const JobDispatchResponseSchema = z
   .object({
      jobRunId: z.guid().describe("Job run ID for tracking and polling"),
      status: z
         .lazy(() => JobRunStatusSchema)
         .describe("Initial job status (typically 'Queued')"),
      message: z.string().optional().describe("Optional status message")
   })
   .describe("Response from async job dispatch endpoints");

export type JobDispatchResponse = z.infer<typeof JobDispatchResponseSchema>;

// ============================================================================
// Unified Execution Run Contracts
// ============================================================================

/**
 * Platform-level durable execution kinds spanning queries, jobs, agents, and
 * other long-running workflows.
 */
export const ExecutionRunKindSchema = z
   .enum([
      "query",
      "session_init",
      "job",
      "workflow",
      "agent",
      "notebook",
      "profiling",
      "indexing"
   ])
   .describe("Platform-level kind for a durable execution run");

export type ExecutionRunKind = z.infer<typeof ExecutionRunKindSchema>;
export const ExecutionRunKind = ExecutionRunKindSchema.enum;

/**
 * Normalized lifecycle states for platform execution runs.
 */
export const ExecutionRunStatusSchema = z
   .enum([
      "queued",
      "starting",
      "running",
      "waiting_input",
      "succeeded",
      "failed",
      "cancelled",
      "timed_out"
   ])
   .describe("Normalized lifecycle status for long-running platform work");

export type ExecutionRunStatus = z.infer<typeof ExecutionRunStatusSchema>;
export const ExecutionRunStatus = ExecutionRunStatusSchema.enum;

/**
 * Public run projection used across long-running execution APIs.
 */
export const ExecutionRunModelSchema = z
   .object({
      id: z.guid(),
      projectId: z.guid().nullable().optional(),
      ownerId: z.guid().nullable().optional(),
      kind: z.lazy(() => ExecutionRunKindSchema),
      status: z.lazy(() => ExecutionRunStatusSchema),
      name: z.string().nullable().optional(),
      progress: z.number().int().nullable().optional(),
      createdAt: z.iso.datetime({ offset: true }),
      startedAt: z.iso.datetime({ offset: true }).nullable().optional(),
      completedAt: z.iso.datetime({ offset: true }).nullable().optional(),
      errorMessage: z.string().nullable().optional(),
      resultData: z.unknown().nullable().optional(),
      sourceJobRunId: z.guid().nullable().optional(),
      rootRunId: z.guid().nullable().optional(),
      parentRunId: z.guid().nullable().optional(),
      workflowKey: z.string().nullable().optional(),
      stepKey: z.string().nullable().optional(),
      isWorkflowRoot: z.boolean().nullable().optional()
   })
   .describe("Public run projection used across long-running execution APIs");

export type ExecutionRunModel = z.infer<typeof ExecutionRunModelSchema>;

/**
 * Projected log entry for an execution run.
 */
export const ExecutionLogModelSchema = z
   .object({
      id: z.guid(),
      runId: z.guid(),
      timestamp: z.iso.datetime({ offset: true }),
      level: z.lazy(() => LogLevelSchema),
      message: z.string().max(2000),
      data: z.unknown().nullable().optional(),
      sourceRunId: z.guid().nullable().optional(),
      rootRunId: z.guid().nullable().optional(),
      parentRunId: z.guid().nullable().optional(),
      workflowKey: z.string().nullable().optional(),
      stepKey: z.string().nullable().optional()
   })
   .describe("Projected log entry for an execution run");

export type ExecutionLogModel = z.infer<typeof ExecutionLogModelSchema>;

/**
 * Event payload emitted by the execution run stream.
 */
export const ExecutionEventModelSchema = z
   .object({
      id: z.string(),
      runId: z.guid(),
      eventType: z.string(),
      timestamp: z.iso.datetime({ offset: true }),
      status: z
         .lazy(() => ExecutionRunStatusSchema)
         .nullable()
         .optional(),
      message: z.string().nullable().optional(),
      data: z.unknown().nullable().optional(),
      log: z
         .lazy(() => ExecutionLogModelSchema)
         .nullable()
         .optional()
   })
   .describe("Event payload emitted by the execution run stream");

export type ExecutionEventModel = z.infer<typeof ExecutionEventModelSchema>;

/**
 * Request payload for supplying external input to a paused execution run.
 */
export const ExecutionRunInputRequestSchema = z
   .object({
      chatSessionId: z
         .guid()
         .nullable()
         .optional()
         .describe(
            "Chat session that owns the paused agent run when the run context is not yet persisted"
         ),
      message: z
         .string()
         .nullable()
         .optional()
         .describe("Optional user message to accompany run input"),
      toolOutputs: z
         .array(z.lazy(() => ToolCallSchema))
         .min(1)
         .nullable()
         .optional()
         .describe("Tool outputs used to resume a paused run")
   })
   .describe("Request payload for supplying input to a paused execution run");

export type ExecutionRunInputRequest = z.infer<
   typeof ExecutionRunInputRequestSchema
>;

/**
 * Request payload for cancelling a run.
 */
export const ExecutionRunCancelRequestSchema = z
   .object({
      reason: z.string().min(1).max(500).nullable().optional()
   })
   .describe("Request payload for cancelling a run");

export type ExecutionRunCancelRequest = z.infer<
   typeof ExecutionRunCancelRequestSchema
>;

/**
 * Request payload for creating a retry run.
 */
export const ExecutionRunRetryRequestSchema = z
   .object({
      reason: z.string().min(1).max(500)
   })
   .describe("Request payload for creating a retry run");

export type ExecutionRunRetryRequest = z.infer<
   typeof ExecutionRunRetryRequestSchema
>;
