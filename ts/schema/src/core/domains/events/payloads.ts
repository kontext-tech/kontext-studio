/**
 * Event data payload schemas for Data-AI API events.
 *
 * These models define the structure of the JSON data stored in Event.content.
 * They are used to serialize/deserialize event payloads for background job processing.
 *
 * Note: The EventType enum, EventViewModel, and PaginatedListOfEventViewModel are
 * generated from the .NET Core API and available via the core module export.
 */

import { z } from "zod";
import { FileFormatTypeSchema } from "../base/types.js";

// =============================================================================
// Event Data Models (payloads)
// =============================================================================

/**
 * Simple file data for event payloads.
 */
export const SimpleFileEventDataSchema = z.object({
   id: z.guid(),
   name: z.string(),
   uri: z.string().optional().nullable(),
   fileType: FileFormatTypeSchema.optional().nullable(),
   contentType: z.string().optional().nullable(),
   size: z.number().int().optional().nullable()
});

/**
 * File created event data.
 */
export const FileCreatedEventDataSchema = z.object({
   projectId: z.guid(),
   files: z.array(SimpleFileEventDataSchema)
});

/**
 * File deleted event data.
 */
export const FileDeletedEventDataSchema = z.object({
   projectId: z.guid(),
   fileId: z.guid(),
   fileType: FileFormatTypeSchema.optional().nullable()
});

/**
 * File schema updated event data.
 */
export const FileSchemaUpdatedEventDataSchema = z.object({
   projectId: z.guid(),
   fileId: z.guid(),
   fileType: FileFormatTypeSchema.optional().nullable()
});

/**
 * Catalog entity created event data.
 */
export const CatalogEntityCreatedEventDataSchema = z.object({
   projectId: z.guid(),
   connectionId: z.guid().optional().nullable(),
   entityId: z.guid(),
   entityName: z.string()
});

/**
 * Catalog entity updated event data.
 */
export const CatalogEntityUpdatedEventDataSchema = z.object({
   projectId: z.guid(),
   connectionId: z.guid().optional().nullable(),
   entityId: z.guid(),
   entityName: z.string()
});

/**
 * Catalog entity deleted event data.
 */
export const CatalogEntityDeletedEventDataSchema = z.object({
   projectId: z.guid(),
   connectionId: z.guid().optional().nullable(),
   entityId: z.guid(),
   entityName: z.string()
});

// =============================================================================
// Type Exports
// =============================================================================

export type SimpleFileEventData = z.infer<typeof SimpleFileEventDataSchema>;
export type FileCreatedEventData = z.infer<typeof FileCreatedEventDataSchema>;
export type FileDeletedEventData = z.infer<typeof FileDeletedEventDataSchema>;
export type FileSchemaUpdatedEventData = z.infer<
   typeof FileSchemaUpdatedEventDataSchema
>;
export type CatalogEntityCreatedEventData = z.infer<
   typeof CatalogEntityCreatedEventDataSchema
>;
export type CatalogEntityUpdatedEventData = z.infer<
   typeof CatalogEntityUpdatedEventDataSchema
>;
export type CatalogEntityDeletedEventData = z.infer<
   typeof CatalogEntityDeletedEventDataSchema
>;
