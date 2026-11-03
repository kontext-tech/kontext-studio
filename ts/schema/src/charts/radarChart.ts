import { z } from "zod";
import {
   BaseChartConfigSchema,
   ColorFieldSchema,
   XFieldSchema,
   YFieldSchema
} from "./base";

export const RadarCoordinateTypeSchema = z
   .enum(["radar", "polar"])
   .describe("Radar chart coordinate system");

export type RadarCoordinateType = z.infer<typeof RadarCoordinateTypeSchema>;
export const RadarCoordinateType = RadarCoordinateTypeSchema.enum;

const RadarAxisSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional radar axis configuration");

const RadarAreaSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional radar area configuration");

const RadarPointSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional radar point configuration");

const RadarScaleSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional radar scale configuration");

const RadarStyleSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional radar style configuration");

export const radarChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("radar"),
   xField: XFieldSchema,
   yField: YFieldSchema,
   colorField: ColorFieldSchema,
   coordinateType: RadarCoordinateTypeSchema.optional(),
   axis: RadarAxisSchema,
   area: RadarAreaSchema,
   point: RadarPointSchema,
   scale: RadarScaleSchema,
   style: RadarStyleSchema
}).describe(
   "Radar chart config (flat object, chartType: 'radar'). Required: title, height, xField, yField. Keys are camelCase (xField, never x/y)."
);

export type RadarChartConfig = z.infer<typeof radarChartSchema>;
