import { z } from "zod";
import { FileFormatTypeSchema } from "../core/domains/base/types.js";

export const ChatUploadPreparationAcceptedFileSchema = z
   .object({
      fileId: z.guid(),
      filename: z.string().min(1).max(1024),
      fileType: FileFormatTypeSchema,
      size: z.number().int().min(0).optional().nullable()
   })
   .describe("Accepted file metadata for chat upload preparation");

export const ChatUploadPreparationFailureSchema = z
   .object({
      fileId: z.guid().optional().nullable(),
      filename: z.string().min(1).max(1024).optional().nullable(),
      code: z.string().min(1).max(128).optional().nullable(),
      error: z.string().min(1)
   })
   .describe("A file-level failure encountered during chat upload preparation");

export const ChatUploadPreparationStepSchema = z
   .object({
      key: z.string().min(1),
      name: z.string().min(1),
      status: z.string().min(1),
      runId: z.guid().optional().nullable(),
      progress: z.number().int().min(0).max(100).optional().nullable(),
      errorMessage: z.string().optional().nullable()
   })
   .describe("Normalized workflow step status for chat upload preparation");

export const StartChatUploadPreparationResponseSchema = z
   .object({
      runId: z.guid(),
      internalCatalogConnectionId: z.guid().optional().nullable(),
      acceptedFiles: z.array(ChatUploadPreparationAcceptedFileSchema),
      uploadErrors: z.array(ChatUploadPreparationFailureSchema),
      successCount: z.number().int().min(0),
      failureCount: z.number().int().min(0)
   })
   .describe("Response returned when chat upload preparation starts");

export const ChatUploadPreparationStatusSchema = z
   .object({
      runId: z.guid(),
      status: z.string().min(1),
      progress: z.number().int().min(0).max(100),
      internalCatalogConnectionId: z.guid().optional().nullable(),
      readyFileIds: z.array(z.guid()),
      failedFiles: z.array(ChatUploadPreparationFailureSchema),
      steps: z.array(ChatUploadPreparationStepSchema)
   })
   .describe("Normalized chat upload preparation workflow status");

export type ChatUploadPreparationAcceptedFile = z.infer<
   typeof ChatUploadPreparationAcceptedFileSchema
>;
export type ChatUploadPreparationFailure = z.infer<
   typeof ChatUploadPreparationFailureSchema
>;
export type ChatUploadPreparationStep = z.infer<
   typeof ChatUploadPreparationStepSchema
>;
export type StartChatUploadPreparationResponse = z.infer<
   typeof StartChatUploadPreparationResponseSchema
>;
export type ChatUploadPreparationStatus = z.infer<
   typeof ChatUploadPreparationStatusSchema
>;
