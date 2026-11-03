import { z } from "zod";
import {
   BaseChartConfigSchema,
   ColorFieldSchema,
   XFieldSchema,
   YFieldSchema
} from "./base";

export const BoxChartTypeSchema = z
   .enum(["box", "boxplot"])
   .describe("Box chart rendering mode");

export type BoxChartType = z.infer<typeof BoxChartTypeSchema>;
export const BoxChartType = BoxChartTypeSchema.enum;

export const BoxChartConfigLegendSchema = z
   .union([z.boolean(), z.record(z.string(), z.any())])
   .optional()
   .describe("Legend configuration");

export type BoxChartConfigLegend = z.infer<typeof BoxChartConfigLegendSchema>;

const BoxStyleSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional box chart style configuration");

const BoxScaleSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional box chart scale configuration");

export const boxChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("box"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   colorField: ColorFieldSchema,
   boxType: BoxChartTypeSchema.optional(),
   legend: BoxChartConfigLegendSchema,
   style: BoxStyleSchema,
   scale: BoxScaleSchema
}).describe(
   "Box chart config (flat object, chartType: 'box'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type BoxChartConfig = z.infer<typeof boxChartSchema>;
