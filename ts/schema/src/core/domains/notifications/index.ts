import { z } from "zod";

import { BaseModelSchema } from "../base/index.js";
import { NotificationTypeSchema } from "./types.js";
export * from "./types.js";

/**
 * Core Domain: Notifications
 *
 * Source: backend/Kontext.Data/ViewModels/NotificationViewModels.cs
 */

export const NotificationModelSchema = BaseModelSchema.extend({
   title: z.string().nullable().optional(),
   content: z.string().nullable().optional(),
   messageTemplateResourceKey: z.string().nullable().optional(),
   messageParams: z.string().nullable().optional(),
   notificationType: z.lazy(() => NotificationTypeSchema),
   isRead: z.boolean(),
   dateCreated: z.iso.datetime({ offset: true }),
   dateRead: z.iso.datetime({ offset: true }).nullable().optional(),
   userId: z.guid().nullable().optional()
}).describe("Notification Model");

export type NotificationModel = z.infer<typeof NotificationModelSchema>;

export const CreateNotificationRequestSchema = z
   .object({
      title: z.string().max(128).nullable().optional(),
      content: z.string().max(2048).nullable().optional(),
      messageTemplateResourceKey: z.string().max(64).nullable().optional(),
      messageParams: z.string().max(1024).nullable().optional(),
      notificationType: z.lazy(() => NotificationTypeSchema),
      userId: z.guid().nullable().optional()
   })
   .describe("Create Notification Request");

export type CreateNotificationRequest = z.infer<
   typeof CreateNotificationRequestSchema
>;
