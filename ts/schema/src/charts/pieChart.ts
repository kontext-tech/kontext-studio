import { z } from "zod";
import {
   AggregateSchema,
   AngleFieldSchema,
   BaseChartConfigSchema,
   ColorFieldSchema
} from "./base";

export const pieChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("pie"),
   angleField: AngleFieldSchema,
   aggregate: AggregateSchema,
   colorField: ColorFieldSchema.refine((val) => val !== undefined, {
      message: "Color field is required for pie charts"
   })
}).describe(
   "Pie chart config (flat object, chartType: 'pie'). Required: title, height, angleField (+ optional colorField). Keys are camelCase (angleField, never angle shorthand)."
);

export type PieChartConfig = z.infer<typeof pieChartSchema>;
