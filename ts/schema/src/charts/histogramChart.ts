import { z } from "zod";
import { BaseChartConfigSchema, ColorFieldSchema, StackSchema } from "./base";

const HistogramChannelSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional histogram channel configuration");

const HistogramStyleSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional histogram style configuration");

export const histogramChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("histogram"),
   binField: z.string().describe("Field name used for histogram binning"),
   colorField: ColorFieldSchema,
   binWidth: z.number().positive().optional().describe("Histogram bin width"),
   binNumber: z
      .number()
      .int()
      .positive()
      .optional()
      .describe("Histogram bin count"),
   channel: HistogramChannelSchema,
   stack: StackSchema,
   style: HistogramStyleSchema
}).describe(
   "Histogram chart config (flat object, chartType: 'histogram'). Required: title, height, binField. Keys are camelCase (binField, never bin shorthand)."
);

export type HistogramChartConfig = z.infer<typeof histogramChartSchema>;
