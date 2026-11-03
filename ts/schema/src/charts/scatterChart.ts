import { z } from "zod";
import {
   BaseChartConfigSchema,
   ColorFieldSchema,
   SizeFieldSchema,
   XFieldSchema,
   YFieldSchema
} from "./base";

export const scatterChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("scatter"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   sizeField: SizeFieldSchema,
   colorField: ColorFieldSchema
}).describe(
   "Scatter chart config (flat object, chartType: 'scatter'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type ScatterChartConfig = z.infer<typeof scatterChartSchema>;
