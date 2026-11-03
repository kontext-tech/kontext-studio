import { z } from "zod";

import { BaseModelSchema } from "../base/index.js";
import { BotInfoSchema, ChannelTypeSchema, EventTypeSchema } from "./types.js";
export * from "./payloads.js";
export * from "./types.js";

/**
 * Core Domain: Events
 *
 * Source: backend/Kontext.Data/ViewModels/EventViewModels.cs
 */

export const EventModelSchema = BaseModelSchema.extend({
   title: z.string().nullable().optional(),
   content: z.string().nullable().optional(),
   userId: z.guid().nullable().optional(),
   projectId: z.guid().nullable().optional(),
   contentId: z.guid().nullable().optional(),
   type: z.lazy(() => EventTypeSchema),
   channelType: z.lazy(() => ChannelTypeSchema),
   ipAddress: z.string().nullable().optional(),
   path: z.string().nullable().optional(),
   botInfo: z
      .lazy(() => BotInfoSchema)
      .nullable()
      .optional(),
   dateCreated: z.iso.datetime({ offset: true })
}).describe("Event Model");

export type EventModel = z.infer<typeof EventModelSchema>;

export const CreateEventRequestSchema = z
   .object({
      title: z.string().max(256).nullable().optional(),
      content: z.string().max(2560).nullable().optional(),
      userId: z.guid().nullable().optional(),
      projectId: z.guid().nullable().optional(),
      contentId: z.guid().nullable().optional(),
      type: z.lazy(() => EventTypeSchema),
      channelType: z.lazy(() => ChannelTypeSchema),
      ipAddress: z.string().max(64).nullable().optional(),
      userAgent: z.string().max(250).nullable().optional(),
      path: z.string().max(512).nullable().optional()
   })
   .describe("Create Event Request");

export type CreateEventRequest = z.infer<typeof CreateEventRequestSchema>;
