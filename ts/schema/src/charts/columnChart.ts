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

export const columnChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("column"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   aggregate: AggregateSchema,
   colorField: ColorFieldSchema,
   stack: StackSchema,
   group: GroupSchema
}).describe(
   "Column chart config (flat object, chartType: 'column'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type ColumnChartConfig = z.infer<typeof columnChartSchema>;
