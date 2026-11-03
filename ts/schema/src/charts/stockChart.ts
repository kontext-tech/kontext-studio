import { z } from "zod";
import { BaseChartConfigSchema, XFieldSchema } from "./base";

export const StockYFieldSchema = z
   .array(z.string())
   .length(4)
   .describe(
      "Ordered stock value fields: [open field, close field, low field, high field]"
   );

const StockLineStyleSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional stock line style configuration");

const StockStyleSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional stock style configuration");

const StockTooltipSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Optional stock tooltip configuration");

export const stockChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("stock"),
   xField: XFieldSchema,
   yField: StockYFieldSchema,
   lineStyle: StockLineStyleSchema,
   style: StockStyleSchema,
   tooltip: StockTooltipSchema
}).describe(
   "Stock chart config (flat object, chartType: 'stock'). Required: title, height, xField, yField where yField is a list of 4 columns in [open field, close field, low field, high field] order."
);

export type StockYField = z.infer<typeof StockYFieldSchema>;
export type StockChartConfig = z.infer<typeof stockChartSchema>;
