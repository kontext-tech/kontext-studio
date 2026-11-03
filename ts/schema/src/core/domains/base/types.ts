import { z } from "zod";

/**
 * Problem Types enum for standardized error responses
 */
export const ProblemTypesSchema = z
   .enum([
      "RequiresTwoFactor",
      "InvalidCredentials",
      "ResourceNotFound",
      "Unauthorized",
      "AccountNotActivated",
      "ValidationFailed",
      "Timeout",
      "UnexpectedError",
      "InvalidCaptcha",
      "MissingCaptcha",
      "InvalidCaptchaContext",
      "UnsupportedTokenVersion"
   ])
   .describe("Problem Types enum");

export type ProblemTypes = z.infer<typeof ProblemTypesSchema>;
export const ProblemTypes = ProblemTypesSchema.enum;

/**
 * File Format Type enum
 */
export const FileFormatTypeSchema = z
   .enum([
      "Default",
      "Markdown",
      "Image",
      "DrawIO",
      "CSV",
      "PDF",
      "Parquet",
      "Text",
      "JSON",
      "JSONL",
      "TSV",
      "Notebook",
      "Chart",
      "DataTable",
      "Excel"
   ])
   .describe("File Format Type enum");

export type FileFormatType = z.infer<typeof FileFormatTypeSchema>;
export const FileFormatType = FileFormatTypeSchema.enum;

/**
 * IFormFile schema - represents a file from a form upload
 */
export const IFormFileSchema = z
   .string()
   .describe("I Form File model from Kontext API");

export type IFormFile = z.infer<typeof IFormFileSchema>;

/**
 * Problem Details schema - RFC 7807 standard
 */
export const ProblemDetailsSchema = z
   .object({
      type: z.string().nullable().optional(),
      title: z.string().nullable().optional(),
      status: z.number().int().nullable().optional(),
      detail: z.string().nullable().optional(),
      instance: z.string().nullable().optional()
   })
   .describe("Problem Details model from Kontext API");

export type ProblemDetails = z.infer<typeof ProblemDetailsSchema>;

/**
 * HTTP Validation Problem Details - RFC 7807 with validation errors
 */
export const HttpValidationProblemDetailsSchema = z
   .object({
      type: z.string().nullable().optional(),
      title: z.string().nullable().optional(),
      status: z.number().int().nullable().optional(),
      detail: z.string().nullable().optional(),
      instance: z.string().nullable().optional(),
      errors: z.record(z.string(), z.array(z.string())).optional()
   })
   .describe("Http Validation Problem Details model from Kontext API");

export type HttpValidationProblemDetails = z.infer<
   typeof HttpValidationProblemDetailsSchema
>;
