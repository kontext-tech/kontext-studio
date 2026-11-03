/**
 * Paginated List Models - Zod-first definitions
 *
 * These schemas define paginated response structures used throughout Kontext.
 * By using explicit z.lazy() references to item types, we ensure that OpenAPI conversion
 * produces proper $ref entries instead of inline object definitions, preventing the
 * generation of unnecessary ItemsInner wrapper classes in code generators.
 *
 * Note: Identity-related paginated models (User, Role, ServiceAccount) are defined in
 * ts/schema/src/core/domains/identity/ since they're part of the identity domain.
 */

import { z } from "zod";
import { EventModelSchema } from "./events/index.js";
import {
   ExecutionRunModelSchema,
   JobModelSchema,
   JobRunModelSchema
} from "./jobs/index.js";
import { NotificationModelSchema } from "./notifications/index.js";
import { ProjectModelSchema } from "./projects/index.js";
import { TokenModelSchema } from "./tokens/index.js";

/**
 * Generic paginated response wrapper
 * Provides standard pagination metadata: totalCount, pageIndex, pageSize, totalPages
 */
const createPaginatedSchema = <T extends z.ZodTypeAny>(
   itemSchema: T,
   name: string
) => {
   return z
      .object({
         items: z.array(itemSchema).default([]),
         totalCount: z.number().int(),
         pageIndex: z.number().int(),
         pageSize: z.number().int(),
         totalPages: z.number().int().optional()
      })
      .describe(`Paginated List Of ${name} model from Kontext API`);
};

// Notification paginated responses
export const PaginatedListOfEventModelSchema = createPaginatedSchema(
   z.lazy(() => EventModelSchema),
   "Event Model"
);

// Job paginated responses
export const PaginatedListOfJobModelSchema = createPaginatedSchema(
   z.lazy(() => JobModelSchema),
   "Job Model"
);

export const PaginatedListOfJobRunModelSchema = createPaginatedSchema(
   z.lazy(() => JobRunModelSchema),
   "Job Run Model"
);

export const PaginatedListOfExecutionRunModelSchema = createPaginatedSchema(
   z.lazy(() => ExecutionRunModelSchema),
   "Execution Run Model"
);

// Notification paginated responses
export const PaginatedListOfNotificationModelSchema = createPaginatedSchema(
   z.lazy(() => NotificationModelSchema),
   "Notification Model"
);

// Project paginated responses
export const PaginatedListOfProjectModelSchema = createPaginatedSchema(
   z.lazy(() => ProjectModelSchema),
   "Project Model"
);

// Token paginated responses
export const PaginatedListOfTokenModelSchema = createPaginatedSchema(
   z.lazy(() => TokenModelSchema),
   "Token Model"
);

// Type exports for TypeScript
export type PaginatedListOfEventModel = z.infer<
   typeof PaginatedListOfEventModelSchema
>;
export type PaginatedListOfJobModel = z.infer<
   typeof PaginatedListOfJobModelSchema
>;
export type PaginatedListOfJobRunModel = z.infer<
   typeof PaginatedListOfJobRunModelSchema
>;
export type PaginatedListOfExecutionRunModel = z.infer<
   typeof PaginatedListOfExecutionRunModelSchema
>;
export type PaginatedListOfNotificationModel = z.infer<
   typeof PaginatedListOfNotificationModelSchema
>;
export type PaginatedListOfProjectModel = z.infer<
   typeof PaginatedListOfProjectModelSchema
>;
export type PaginatedListOfTokenModel = z.infer<
   typeof PaginatedListOfTokenModelSchema
>;
