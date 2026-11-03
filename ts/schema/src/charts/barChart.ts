import { z } from "zod";
import {
   AggregateSchema,
   BaseChartConfigSchema,
   ColorFieldSchema,
   GroupSchema,
   StackSchema,
   XFieldSchema,
   YFieldSchema
} from "./base";

export const barChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("bar"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   aggregate: AggregateSchema,
   colorField: ColorFieldSchema,
   stack: StackSchema,
   group: GroupSchema
}).describe(
   "Bar chart config (flat object, chartType: 'bar'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type BarChartConfig = z.infer<typeof barChartSchema>;
