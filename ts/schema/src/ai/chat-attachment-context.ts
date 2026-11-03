import { z } from "zod";
import { FileFormatTypeSchema } from "../core/domains/base/types.js";

export const AttachedDataTableSchema = z
   .object({
      entityId: z.guid(),
      namespaceName: z.string().min(1),
      entityName: z.string().min(1),
      rowCount: z.number().int().min(0).optional().nullable(),
      columnNames: z.array(z.string())
   })
   .describe("Resolved attached table metadata available to chat agents");

export const AttachedDataSourceSchema = z
   .object({
      fileId: z.guid(),
      fileName: z.string().min(1).max(1024),
      fileType: FileFormatTypeSchema,
      tables: z.array(AttachedDataTableSchema)
   })
   .describe("Resolved attached file metadata available to chat agents");

export const ChatAttachmentContextFileSchema = z
   .object({
      fileId: z.guid(),
      fileName: z.string().min(1).max(1024),
      fileType: FileFormatTypeSchema
   })
   .describe("Persisted attached file metadata for chat bootstrap");

export const ChatAttachmentContextTableSchema = z
   .object({
      fileId: z.guid(),
      entityId: z.guid(),
      namespaceName: z.string().min(1),
      entityName: z.string().min(1),
      rowCount: z.number().int().min(0).optional().nullable(),
      columnNames: z.array(z.string())
   })
   .describe("Persisted attached table metadata for chat bootstrap");

export const ChatAttachmentContextSchema = z
   .object({
      uploadPreparationRunId: z.guid(),
      internalCatalogConnectionId: z.guid(),
      files: z.array(ChatAttachmentContextFileSchema),
      tables: z.array(ChatAttachmentContextTableSchema)
   })
   .describe("Persisted attached-data context for a chat session");

export const SeedChatAttachmentContextRequestSchema = z
   .object({
      uploadPreparationRunId: z.guid()
   })
   .describe(
      "Request body for seeding attached-data context into a chat session"
   );

export type AttachedDataTable = z.infer<typeof AttachedDataTableSchema>;
export type AttachedDataSource = z.infer<typeof AttachedDataSourceSchema>;
export type ChatAttachmentContextFile = z.infer<
   typeof ChatAttachmentContextFileSchema
>;
export type ChatAttachmentContextTable = z.infer<
   typeof ChatAttachmentContextTableSchema
>;
export type ChatAttachmentContext = z.infer<typeof ChatAttachmentContextSchema>;
export type SeedChatAttachmentContextRequest = z.infer<
   typeof SeedChatAttachmentContextRequestSchema
>;
