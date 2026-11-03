import { z } from "zod";
import {
   AggregateSchema,
   BaseChartConfigSchema,
   ColorFieldSchema,
   ConnectNullsSchema,
   XFieldSchema,
   YFieldSchema
} from "./base";

export const lineChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("line"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   aggregate: AggregateSchema,
   colorField: ColorFieldSchema,
   connectNulls: ConnectNullsSchema
}).describe(
   "Line chart config (flat object, chartType: 'line'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type LineChartConfig = z.infer<typeof lineChartSchema>;
