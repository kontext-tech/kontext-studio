import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const DelimiterBlockDataSchema = z
   .object({})
   .describe("Data schema for delimiter block (no data needed)");

export const DelimiterBlockSchema = BaseBlockSchema.extend({
   type: z.literal("delimiter"),
   data: DelimiterBlockDataSchema
}).describe("Delimiter block for visual section separation");

export type DelimiterBlock = z.infer<typeof DelimiterBlockSchema>;
export type DelimiterBlockData = z.infer<typeof DelimiterBlockDataSchema>;
