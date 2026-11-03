import { z } from "zod";
import {
   BaseChartConfigSchema,
   CompareFieldSchema,
   IsTransposedSchema,
   SeriesFieldSchema,
   XFieldSchema,
   YFieldSchema
} from "./base";

export const funnelChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("funnel"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   compareField: CompareFieldSchema,
   seriesField: SeriesFieldSchema,
   isTransposed: IsTransposedSchema
}).describe(
   "Funnel chart config (flat object, chartType: 'funnel'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type FunnelChartConfig = z.infer<typeof funnelChartSchema>;
