import { z } from "zod";
import { ChartSpecSchema } from "../../charts";
import { BaseBlockSchema } from "../base";

export const ChartBlockDataSchema = ChartSpecSchema.describe(
   "Data schema for chart block configuration with unified chart specification"
);

export const ChartBlockSchema = BaseBlockSchema.extend({
   type: z.literal("chart"),
   data: ChartBlockDataSchema
}).describe(
   "Chart block for interactive data visualizations with separate data table management"
);

export type ChartBlock = z.infer<typeof ChartBlockSchema>;
export type ChartBlockData = z.infer<typeof ChartBlockDataSchema>;
