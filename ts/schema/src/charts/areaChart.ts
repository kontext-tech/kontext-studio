import { z } from "zod";
import {
   AggregateSchema,
   BaseChartConfigSchema,
   ColorFieldSchema,
   StackSchema,
   XFieldSchema,
   YFieldSchema
} from "./base";

export const areaChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("area"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   aggregate: AggregateSchema,
   colorField: ColorFieldSchema,
   stack: StackSchema
}).describe(
   "Area chart config (flat object, chartType: 'area'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type AreaChartConfig = z.infer<typeof areaChartSchema>;
