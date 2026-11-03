import { z } from "zod";

/**
 * Access Level enum
 */
export const AccessLevelSchema = z
   .enum(["Private", "Public"])
   .describe("Access Level enum");

export type AccessLevel = z.infer<typeof AccessLevelSchema>;
export const AccessLevel = AccessLevelSchema.enum;

/**
 * Project Feature enum
 */
export const ProjectFeatureSchema = z
   .enum(["Documentation", "DataLake", "Search", "Chat"])
   .describe("Project Feature enum");

export type ProjectFeature = z.infer<typeof ProjectFeatureSchema>;
export const ProjectFeature = ProjectFeatureSchema.enum;
