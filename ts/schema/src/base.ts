import { z } from "zod";

// =============================================================================
// Column Data Types
// =============================================================================

/**
 * Supported column data types for schema profiling and column statistics.
 * This enum covers common data types from various database systems.
 */
export const ColumnDataTypeSchema = z.enum([
   "TinyInt",
   "SmallInt",
   "Integer",
   "BigInt",
   "HugeInt",
   "UTinyInt",
   "USmallInt",
   "UInteger",
   "UBigInt",
   "UHugeInt",
   "Real",
   "Float",
   "Double",
   "Decimal",
   "Numeric",
   "VarChar",
   "Char",
   "Text",
   "String",
   "Blob",
   "Bytea",
   "VarBinary",
   "Binary",
   "Date",
   "Time",
   "TimeTz",
   "Timestamp",
   "TimestampTz",
   "TimestampS",
   "TimestampMs",
   "TimestampNs",
   "Interval",
   "Boolean",
   "Bool",
   "Uuid",
   "Json",
   "Array",
   "List",
   "Struct",
   "Row",
   "Map",
   "Union",
   "Enum",
   "Bit",
   "BitString",
   "Nested",
   "AggregateState",
   "Null",
   "Any",
   "Unknown"
]);
export const ColumnDataType = ColumnDataTypeSchema.enum;
export type ColumnDataType = z.infer<typeof ColumnDataTypeSchema>;

// =============================================================================
// Column Statistics Model
// =============================================================================

/**
 * ColumnStatsModel - Statistics for a single column in a resource/data table
 * This is used by ResourceStatisticsDataModel and FileStatsModel
 */
export const ColumnStatsModelSchema = z.object({
   // Name of the column
   columnName: z.string().optional().nullable(),
   // Number of distinct values
   distinctCount: z
      .number()
      .int()
      .describe("format: int64")
      .optional()
      .nullable(),
   // Number of null values
   nullCount: z.number().int().describe("format: int64").optional().nullable(),
   // Completeness score (0.0 to 1.0)
   completenessScore: z.number().min(0).max(1).optional().nullable(),
   // Minimum value (numeric)
   minValue: z.number().optional().nullable(),
   // Maximum value (numeric)
   maxValue: z.number().optional().nullable(),
   // Standard deviation
   stdDev: z.number().optional().nullable(),
   // Median value
   medianValue: z.number().optional().nullable(),
   // Average value
   avgValue: z.number().optional().nullable(),
   // Maximum length of values (for string columns)
   maxLength: z.number().int().describe("format: int64").optional().nullable(),
   // Top values for categorical data (frequency analysis)
   topValues: z
      .record(z.string(), z.number().int().describe("format: int64"))
      .optional()
      .nullable(),
   // Number of true values (for boolean columns)
   trueCount: z.number().int().describe("format: int64").optional().nullable(),
   // Number of false values (for boolean columns)
   falseCount: z.number().int().describe("format: int64").optional().nullable(),
   // Ratio of true values (for boolean columns)
   trueRatio: z.number().optional().nullable(),
   // Source of statistics (e.g., "parquet_metadata", "sampling")
   statsSource: z.string().optional().nullable(),
   // Sample values for the column
   samples: z.array(z.any()).optional().nullable()
});
export type ColumnStatsModel = z.infer<typeof ColumnStatsModelSchema>;

// =============================================================================
// Base models and error responses
// =============================================================================

export const ValidationErrorResponseSchema = z
   .object({
      error: z.string().describe("Error message for validation failures")
   })
   .describe("Simple error response for validation errors (400 status codes)");

export type ValidationErrorResponse = z.infer<
   typeof ValidationErrorResponseSchema
>;

/**
 * Inner type for ValidationError location path (can be string field name or integer index)
 */
export const ValidationErrorLocInnerSchema = z.union([
   z.string(),
   z.number().int()
]);
export type ValidationErrorLocInner = z.infer<
   typeof ValidationErrorLocInnerSchema
>;

export const ValidationErrorSchema = z
   .object({
      loc: z
         .array(ValidationErrorLocInnerSchema)
         .describe("Error location path"),
      msg: z.string().describe("Error message"),
      type: z.string().describe("Error type")
   })
   .describe("Individual validation error detail");

export const HTTPValidationErrorSchema = z
   .object({
      detail: z
         .array(ValidationErrorSchema)
         .optional()
         .describe("List of validation errors")
   })
   .describe("HTTP validation error response from FastAPI");

export type ValidationError = z.infer<typeof ValidationErrorSchema>;
export type HTTPValidationError = z.infer<typeof HTTPValidationErrorSchema>;

// =============================================================================
// Tabular Data Primitives (Row-oriented)
// =============================================================================

/**
 * Standard schema for a single row of tabular data.
 * Used for charts, data tables, and other row-oriented visualizations.
 */
export const TabularRowSchema = z
   .record(z.string(), z.unknown())
   .describe("Single row of tabular data");

/**
 * Standard schema for a collection of tabular data rows.
 * This is the common format consumed by UI components after converting
 * from the columnar transport format (DataTable).
 */
export const TabularDataSchema = z
   .array(TabularRowSchema)
   .describe("Array of tabular data rows");

export type TabularRow = z.infer<typeof TabularRowSchema>;
export type TabularData = z.infer<typeof TabularDataSchema>;
