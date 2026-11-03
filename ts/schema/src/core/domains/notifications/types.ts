import { z } from "zod";

/**
 * Notification Type enum
 */
export const NotificationTypeSchema = z
   .enum(["Default", "NewComment", "Like"])
   .describe("Notification Type enum");

export type NotificationType = z.infer<typeof NotificationTypeSchema>;
export const NotificationType = NotificationTypeSchema.enum;
