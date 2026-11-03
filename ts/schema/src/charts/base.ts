/**
 * Base Zod schemas for chart configurations
 * Aligned with Ant Design Charts API structure from @ant-design/plots
 */

import { z } from "zod";
import { TabularDataSchema } from "../base";

// ============================================================================
// Color Palette Constants
// ============================================================================

const COLOR_PALETTES = [
   "kontext",
   "category10",
   "accent",
   "dark2",
   "paired",
   "pastel1",
   "pastel2",
   "set1",
   "set2",
   "set3",
   "tableau10",
   "blues",
   "brBG",
   "buGn",
   "buPu",
   "cividis",
   "cool",
   "cubehelixDefault",
   "gnBu",
   "greens",
   "greys",
   "inferno",
   "magma",
   "oranges",
   "orRd",
   "piYG",
   "plasma",
   "pRGn",
   "puBu",
   "puBuGn",
   "puOr",
   "puRd",
   "purples",
   "rainbow",
   "rdBu",
   "rdGy",
   "rdPu",
   "rdYlBu",
   "rdYlGn",
   "reds",
   "sinebow",
   "spectral",
   "turbo",
   "viridis",
   "warm",
   "ylGn",
   "ylGnBu",
   "ylOrBr",
   "ylOrRd"
] as const;

// ============================================================================
// Kontext Extensions
// ============================================================================

const ChartTitleSchema = z.string().describe("Chart title");

const ChartHeightSchema = z
   .number()
   .min(200)
   .max(1000)
   .describe("Chart height in pixels");

export const ColorPaletteSchema = z
   .enum(COLOR_PALETTES)
   .describe("Color palette for chart styling");

// Export TypeScript type for API type generation
export const ColorPalette = ColorPaletteSchema.enum;
export type ColorPalette = z.infer<typeof ColorPaletteSchema>;

const ChartDataSchema = TabularDataSchema.optional().describe(
   "Chart data array - populated at runtime"
);

// ============================================================================
// Chart Type Schema
// ============================================================================

export const ChartTypeSchema = z
   .enum([
      "line",
      "bar",
      "column",
      "area",
      "pie",
      "scatter",
      "dualAxes",
      "funnel",
      "heatmap",
      "histogram",
      "box",
      "radar",
      "stock"
   ])
   .describe("Supported chart types from Ant Design Charts");

export type ChartType = z.infer<typeof ChartTypeSchema>;
export const ChartType = ChartTypeSchema.enum;

// ============================================================================
// Ant Design Charts Field Schemas
// ============================================================================

export const AggregateMethodSchema = z
   .enum(["sum", "avg", "count", "max", "min", "none"])
   .describe("Data aggregation method");

export type AggregateMethod = z.infer<typeof AggregateMethodSchema>;
export const AggregateMethod = AggregateMethodSchema.enum;

export const AggregateSchema = AggregateMethodSchema.optional().describe(
   "Data aggregation method"
);

export const XFieldSchema = z.string().describe("X-axis field name");
export const YFieldSchema = z.string().describe("Y-axis field name");
export const ColorFieldSchema = z
   .string()
   .optional()
   .describe("Color mapping field name");
export const SizeFieldSchema = z
   .string()
   .optional()
   .describe("Size mapping field name");
export const ShapeFieldSchema = z
   .string()
   .optional()
   .describe("Shape field for heat map marks");
const LabelSchema = z
   .record(z.string(), z.any())
   .optional()
   .describe("Label configuration for chart elements");

export const MARK_TYPES = [
   "auto",
   "interval",
   "rect",
   "line",
   "point",
   "text",
   "cell",
   "area",
   "node",
   "edge",
   "link",
   "image",
   "polygon",
   "box",
   "vector",
   "lineX",
   "lineY",
   "connector",
   "range",
   "rangeX",
   "rangeY",
   "sankey",
   "chord",
   "path",
   "treemap",
   "pack",
   "boxplot",
   "shape",
   "forceGraph",
   "tree",
   "wordCloud",
   "gauge",
   "density",
   "heatmap",
   "liquid"
] as const;

export const MarkTypesSchema = z
   .enum(MARK_TYPES)
   .describe("Chart mark type for visualization");

export type MarkTypes = z.infer<typeof MarkTypesSchema>;

export const MarkTypes = MarkTypesSchema.enum;

export const CompareFieldSchema = z
   .string()
   .optional()
   .describe("Compare field for funnel comparison");
export const SeriesFieldSchema = z
   .string()
   .optional()
   .describe("Series field for data grouping");
export const IsTransposedSchema = z
   .boolean()
   .optional()
   .describe("Whether to transpose the funnel chart");

// ============================================================================
// Behavior control schemas - Standalone reusable types
// ============================================================================

/**
 * Generic chart stacking configuration.
 * Can be a boolean (true/false) or an object with advanced stacking options.
 */
export const chartStackConfigSchema = z
   .union([z.boolean(), z.record(z.string(), z.any())])
   .describe("Stacking configuration");

export type ChartStackConfig = z.infer<typeof chartStackConfigSchema>;

/**
 * Generic chart grouping configuration.
 * Can be a boolean (true/false) or an object with advanced grouping options.
 * Display series side by side instead of stacked.
 */
export const chartGroupConfigSchema = z
   .union([z.boolean(), z.record(z.string(), z.any())])
   .describe(
      "Grouping configuration - display series side by side instead of stacked"
   );

export type ChartGroupConfig = z.infer<typeof chartGroupConfigSchema>;

// Convenience references for use in chart schemas (kept for backward compatibility)
export const StackSchema = chartStackConfigSchema.optional();
export const GroupSchema = chartGroupConfigSchema.optional();

export const AngleFieldSchema = z
   .string()
   .describe("Field name for pie slice angles");

export const ConnectNullsObjectSchema = z
   .object({ connect: z.boolean() })
   .catchall(z.any())
   .describe("Explicit connect nulls configuration object");

export const ConnectNullsSchema = z
   .union([z.boolean(), ConnectNullsObjectSchema])
   .optional()
   .describe("Connect null values configuration");

export type ConnectNulls = z.infer<typeof ConnectNullsSchema>;
export type ConnectNullsObject = z.infer<typeof ConnectNullsObjectSchema>;

const NumberFormatEnumSchema = z.enum([
   "none",
   "short",
   "thousands",
   "millions",
   "billions"
]);

export const NumberFormatSchema = NumberFormatEnumSchema.default(
   "short"
).describe("Number formatting style");

export type NumberFormat = z.infer<typeof NumberFormatSchema>;
export const NumberFormat = NumberFormatEnumSchema.enum;

// ============================================================================
// Base Chart Configuration Schema
// ============================================================================

export const BaseChartConfigSchema = z.object({
   chartType: ChartTypeSchema,
   title: ChartTitleSchema,
   height: ChartHeightSchema,
   colorPalette: ColorPaletteSchema.optional(),
   numberFormat: NumberFormatSchema.optional(),
   data: ChartDataSchema,
   label: LabelSchema
});
