import { z } from "zod";
import {
   AggregateSchema,
   BaseChartConfigSchema,
   ColorFieldSchema,
   StackSchema
} from "./base";

export const DualAxesChartTypeSchema = z.enum(["interval", "line", "area"], {
   message: "Chart type must be one of: interval, line, or area"
});

const RequiredXFieldSchema = z
   .string()
   .min(1, "X field is required")
   .describe("X-axis field name");
const RequiredYFieldSchema = z
   .string()
   .min(1, "Y field is required")
   .describe("Y-axis field name");

export const dualAxesChartSchema = BaseChartConfigSchema.extend({
   chartType: z.literal("dualAxes"),
   xField: RequiredXFieldSchema,
   leftYField: RequiredYFieldSchema,
   leftAggregate: AggregateSchema,
   leftChartType: DualAxesChartTypeSchema.default("interval"),
   leftColorField: ColorFieldSchema,
   leftStack: StackSchema,
   rightYField: RequiredYFieldSchema,
   rightAggregate: AggregateSchema,
   rightChartType: DualAxesChartTypeSchema.default("line"),
   rightColorField: ColorFieldSchema,
   rightStack: StackSchema
}).describe(
   "Dual-axes chart config (flat object, chartType: 'dualAxes'). Required: title, height, xField, leftYField, leftChartType ('line'|'interval'|'area'), rightYField, rightChartType. Keys are camelCase."
);

export type DualAxesChartConfig = z.infer<typeof dualAxesChartSchema>;
export type DualAxesChartType = z.infer<typeof DualAxesChartTypeSchema>;
export const DualAxesChartType = DualAxesChartTypeSchema.enum;
