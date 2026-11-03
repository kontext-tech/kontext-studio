import { z } from "zod";

// Project stats models

export const ProjectStatsModelSchema = z
   .object({
      fileCount: z.number().int().optional(),
      totalSizeInBytes: z.number().int().describe("format: int64").optional(),
      projectId: z.guid(),
      totalJobRunDurationMs: z
         .number()
         .int()
         .describe("format: int64")
         .optional(),
      totalTokensInbound: z.number().int().describe("format: int64").optional(),
      totalTokensOutbound: z.number().int().describe("format: int64").optional()
   })
   .describe("Project Stats Model model from Kontext API");

export type ProjectStatsModel = z.infer<typeof ProjectStatsModelSchema>;
