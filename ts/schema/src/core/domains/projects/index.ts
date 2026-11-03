import { z } from "zod";

import { BaseModelSchema } from "../base/index.js";
import { ProjectConfigurationSchema } from "./config.js";
import { AccessLevelSchema } from "./types.js";
export * from "./config.js";
export * from "./stats.js";
export * from "./types.js";

/**
 * Core Domain: Projects
 *
 * Source: backend/Kontext.Data/ViewModels/ProjectViewModels.cs
 */

export const CreateProjectRequestSchema = z
   .object({
      projectName: z.string().max(1024),
      projectCode: z
         .string()
         .max(64)
         .regex(/^[a-zA-Z0-9-]+$/),
      projectDescription: z.string().max(2048).nullable().optional(),
      accessLevel: z.lazy(() => AccessLevelSchema)
   })
   .describe("Create Project Request");

export type CreateProjectRequest = z.infer<typeof CreateProjectRequestSchema>;

export const CreateProjectModelSchema = CreateProjectRequestSchema.extend({
   configuration: z.lazy(() => ProjectConfigurationSchema)
}).describe("Create Project Model");

export type CreateProjectModel = z.infer<typeof CreateProjectModelSchema>;

export const UpdateProjectRequestSchema = BaseModelSchema.extend({
   projectName: z.string().max(1024),
   projectDescription: z.string().max(2048).nullable().optional(),
   modifyByUserId: z.guid().nullable().optional()
}).describe("Update Project Request");

export type UpdateProjectRequest = z.infer<typeof UpdateProjectRequestSchema>;

export const ProjectNavModelSchema = BaseModelSchema.extend({
   projectName: z.string().max(1024),
   projectCode: z.string().max(64),
   accessLevel: z.lazy(() => AccessLevelSchema).default("Private")
}).describe("Project Nav Model");

export type ProjectNavModel = z.infer<typeof ProjectNavModelSchema>;

export const ProjectModelSchema = ProjectNavModelSchema.extend({
   projectDescription: z.string().max(4000).nullable().optional(),
   configuration: z.lazy(() => ProjectConfigurationSchema),
   ownerId: z.guid(),
   dateCreated: z.iso.datetime({ offset: true }).nullable().optional(),
   modifiedByUserId: z.guid().nullable().optional(),
   dateModified: z.iso.datetime({ offset: true }).nullable().optional(),
   isDeleted: z.boolean().default(false),
   dateDeleted: z.iso.datetime({ offset: true }).nullable().optional()
}).describe("Project Model");

export type ProjectModel = z.infer<typeof ProjectModelSchema>;

export const UpdateProjectConfigurationRequestSchema = z
   .object({
      projectId: z.guid(),
      configuration: z.lazy(() => ProjectConfigurationSchema)
   })
   .describe("Update Project Configuration Request");

export type UpdateProjectConfigurationRequest = z.infer<
   typeof UpdateProjectConfigurationRequestSchema
>;
