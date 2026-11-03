import { z } from "zod";
import { QueryEngineTypeSchema } from "../../../data-lake/query/sessions.js";
import { FileTypeConfigurationSchema } from "../infrastructure/config.js";
import { ProjectFeatureSchema } from "./types.js";

const nullishArray = <T extends z.ZodTypeAny>(itemSchema: T) =>
   z.preprocess((value) => value ?? [], z.array(itemSchema));

/**
 * Project Configuration - project-level settings
 */
export const ProjectConfigurationSchema = z
   .object({
      allowedFileTypes: nullishArray(z.lazy(() => FileTypeConfigurationSchema)),
      maxFileBytesSize: z.number().int(),
      totalStorageAllocationBytes: z.number().int(),
      features: nullishArray(z.lazy(() => ProjectFeatureSchema)),
      defaultQueryEngine: z
         .lazy(() => QueryEngineTypeSchema)
         .default("DuckDB")
         .nullable()
         .optional()
         .describe("Default query engine for the project")
   })
   .strict()
   .describe("Project Configuration model from Kontext API");

export type ProjectConfiguration = z.infer<typeof ProjectConfigurationSchema>;

/**
 * Project File Type Config - links file types to project features
 */
export const ProjectFileTypeConfigSchema = z
   .object({
      fileType: z.lazy(() => FileTypeConfigurationSchema),
      requiredFeatures: z.array(z.lazy(() => ProjectFeatureSchema)).default([]),
      isAvailableForAllProjects: z.boolean().nullable().optional()
   })
   .describe("Project File Type Config model from Kontext API");

export type ProjectFileTypeConfig = z.infer<typeof ProjectFileTypeConfigSchema>;
