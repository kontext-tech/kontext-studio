import { z } from "zod";
import {
   BaseChartConfigSchema,
   MarkTypesSchema,
   ShapeFieldSchema,
   SizeFieldSchema,
   XFieldSchema,
   YFieldSchema
} from "./base";

export const heatMapSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("heatmap"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   colorField: z
      .string()
      .optional()
      .describe(
         "Color mapping field name - optional for backward compatibility"
      ),
   sizeField: SizeFieldSchema,
   shapeField: ShapeFieldSchema,
   mark: MarkTypesSchema.optional()
}).describe(
   "Heatmap chart config (flat object, chartType: 'heatmap'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type HeatMapConfig = z.infer<typeof heatMapSchema>;
