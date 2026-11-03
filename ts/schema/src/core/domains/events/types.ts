import { z } from "zod";

/**
 * Event Type enum
 *
 * IMPORTANT: This enum maps to specific database numeric values defined in backend/Kontext.Data/Primitives.cs
 * The numeric values are NOT sequential because deleted event types left gaps.
 *
 * Numeric mappings are defined in ../enumMappings.ts and used in OpenAPI generation.
 * Source of truth: backend/Kontext.Data/Primitives.cs
 *
 * When serializing/deserializing:
 * - TypeScript/Python: Uses string values (e.g., "CreateProject")
 * - Database storage: Uses numeric values (e.g., 9 for CreateProject)
 * - OpenAPI spec: Includes numeric value mapping via x-enumValues extension
 * - C# generated code: Will include numeric values (0, 9, 10, 18, 20, etc.)
 */
export const EventTypeSchema = z
   .enum([
      "Other",
      "CreateProject",
      "ModifyProject",
      "ViewProject",
      "ViewPage",
      "Login",
      "Register",
      "ConfirmEmail",
      "EditProfile",
      "ChangePassword",
      "Enable2FA",
      "Disable2FA",
      "EnableUser",
      "DisableUser",
      "CreateServiceAccount",
      "EnableServiceAccount",
      "DisableServiceAccount",
      "AuthenticateServiceAccount",
      "CreateServiceAccountKey",
      "EnableServiceAccountKey",
      "DisableServiceAccountKey",
      "DeleteServiceAccountKey",
      "CreateFile",
      "CreateFiles",
      "DeleteFile",
      "UpdateFileSchema",
      "ProcessFailedEvent",
      "CreateCatalogEntity",
      "UpdateCatalogEntity",
      "DeleteCatalogEntity",
      "SubscribeToGroup",
      "UnsubscribeFromGroup",
      "RequestCampaignEmailDelivery",
      "SessionRefresh"
   ])
   .describe(
      "Event Type enum - see ../enumMappings.ts for numeric database values"
   );

export type EventType = z.infer<typeof EventTypeSchema>;
export const EventType = EventTypeSchema.enum;

/**
 * Channel Type enum
 */
export const ChannelTypeSchema = z
   .enum(["Other", "Web", "Mobile", "Api"])
   .describe("Channel Type enum");

export type ChannelType = z.infer<typeof ChannelTypeSchema>;
export const ChannelType = ChannelTypeSchema.enum;

/**
 * Bot Info Model - tracks bot/crawler information in events
 */
export const BotInfoSchema = z
   .object({
      isBot: z.boolean(),
      botType: z.string().nullable().optional(),
      botName: z.string().nullable().optional()
   })
   .describe("Bot Info model from Kontext API");

export type BotInfo = z.infer<typeof BotInfoSchema>;
