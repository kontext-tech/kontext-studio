/**
 * Chart schema validation utilities using Zod
 * Provides robust schema validation for chart configurations
 */

import type { ChartType } from "@kontext-labs/schema";
import { CHART_SCHEMAS } from "@kontext-labs/schema";
import { z } from "zod";
import type { ChartConfig } from "../types/chart";

/**
 * Chart validation error interface
 */
export interface ChartValidationError {
   instancePath: string;
   schemaPath: string;
   keyword: string;
   message?: string;
   params?: z.core.$ZodIssue;
}

/**
 * Validation result interface
 */
export interface ValidationResult {
   valid: boolean;
   errors: ChartValidationError[];
}

/**
 * Convert Zod errors to our validation error format
 */
function convertZodErrors(zodErrors: z.ZodError): ChartValidationError[] {
   return zodErrors.issues.map((error: z.core.$ZodIssue) => ({
      instancePath: error.path.join("."),
      schemaPath: error.path.join("."),
      keyword: error.code,
      message: error.message,
      params: error
   }));
}

/**
 * Validate a chart configuration against its schema
 */
export function validateChartConfig(
   config: ChartConfig,
   chartType: ChartType
): ValidationResult {
   try {
      const schema = CHART_SCHEMAS[chartType];

      if (!schema) {
         return {
            valid: false,
            errors: [
               {
                  instancePath: "",
                  schemaPath: "",
                  keyword: "schema",
                  message: `No schema found for chart type: ${chartType}`,
                  params: undefined
               }
            ]
         };
      }

      // Validate using Zod
      const result = schema.safeParse(config);

      if (result.success) {
         return {
            valid: true,
            errors: []
         };
      } else {
         return {
            valid: false,
            errors: convertZodErrors(result.error)
         };
      }
   } catch (error) {
      return {
         valid: false,
         errors: [
            {
               instancePath: "",
               schemaPath: "",
               keyword: "exception",
               message: `Validation error: ${
                  error instanceof Error ? error.message : "Unknown error"
               }`,
               params: undefined
            }
         ]
      };
   }
}
