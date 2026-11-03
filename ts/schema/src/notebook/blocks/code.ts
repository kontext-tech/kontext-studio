import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const CodeRuntimePreferenceSchema = z
   .enum(["client", "server"])
   .describe("User preference for where to run the code");

export type CodeRuntimePreference = z.infer<typeof CodeRuntimePreferenceSchema>;
export const CodeRuntimePreference = CodeRuntimePreferenceSchema.enum;

// ============================================================================
// Code Execution Output Type Enum
// ============================================================================

export const CodeExecutionOutputTypeSchema = z
   .enum(["text", "image", "image_ref", "json", "resource"])
   .describe("Supported code execution output types");

export type CodeExecutionOutputType = z.infer<
   typeof CodeExecutionOutputTypeSchema
>;
export const CodeExecutionOutputType = CodeExecutionOutputTypeSchema.enum;

export const CodeTextOutputSchema = z
   .object({
      type: z.literal("text"),
      mimeType: z.string().describe("Mime type of the output"),
      content: z.string().describe("Textual output (stdout/stderr)")
   })
   .describe("Textual output (stdout/stderr)");

export const CodeImageOutputSchema = z
   .object({
      type: z.literal("image"),
      mimeType: z.string().describe("Mime type of the output"),
      content: z.string().describe("Base64 encoded image data")
   })
   .describe("Base64 encoded image data");

export const CodeImageRefOutputSchema = z
   .object({
      type: z.literal("image_ref"),
      mimeType: z.string().describe("Mime type of the output"),
      fileId: z.string().describe("File id of the stored image"),
      name: z.string().optional().describe("Optional friendly name"),
      imageUrl: z
         .string()
         .optional()
         .describe("Optional pre-resolved image URL")
   })
   .describe("Reference to an uploaded image file");

export const CodeJsonOutputSchema = z
   .object({
      type: z.literal("json"),
      mimeType: z.string().describe("Mime type of the output"),
      content: z
         .string()
         .describe("JSON serialized data (e.g. dataframe preview)")
   })
   .describe("JSON serialized data (e.g. dataframe preview)");

export const CodeResourceOutputSchema = z
   .object({
      type: z.literal("resource"),
      mimeType: z.string().describe("Mime type of the output"),
      uri: z
         .string()
         .describe("URI to the generated resource (e.g. Parquet file)"),
      name: z.string().optional().describe("Friendly name for the resource")
   })
   .describe("Reference to a generated resource");

export const CodeExecutionOutputSchema = z
   .discriminatedUnion("type", [
      CodeTextOutputSchema,
      CodeImageOutputSchema,
      CodeImageRefOutputSchema,
      CodeJsonOutputSchema,
      CodeResourceOutputSchema
   ])
   .describe("Schema for code execution outputs");

export type CodeTextOutput = z.infer<typeof CodeTextOutputSchema>;
export type CodeImageOutput = z.infer<typeof CodeImageOutputSchema>;
export type CodeImageRefOutput = z.infer<typeof CodeImageRefOutputSchema>;
export type CodeJsonOutput = z.infer<typeof CodeJsonOutputSchema>;
export type CodeResourceOutput = z.infer<typeof CodeResourceOutputSchema>;

const CodeBlockLanguageSchema = z.literal("python").default("python");

export const CodeBlockDataSchema = z
   .object({
      title: z
         .string()
         .optional()
         .describe("Optional title/label for the code block"),
      code: z
         .string()
         .max(10000)
         .describe(
            "Code content to be displayed with syntax highlighting. May be empty for a freshly inserted block."
         ),
      language: CodeBlockLanguageSchema.describe(
         "Programming language for syntax highlighting"
      ),
      outputs: z
         .array(CodeExecutionOutputSchema)
         .optional()
         .describe("Execution outputs"),
      runtimePreference: CodeRuntimePreferenceSchema.optional(),
      isExecuting: z
         .boolean()
         .optional()
         .describe("Runtime flag indicating if code is currently executing"),
      showCode: z
         .boolean()
         .optional()
         .describe("Flag to show or hide the code editor"),
      lastExecuted: z.coerce
         .number()
         .int()
         .optional()
         .describe("format: int64 | Timestamp of last code execution"),
      executionRunId: z
         .string()
         .optional()
         .describe(
            "Run id of the last managed execution that produced the outputs"
         )
   })
   .describe("Data schema for code block content");

export const CodeBlockSchema = BaseBlockSchema.extend({
   type: z.literal("code"),
   data: CodeBlockDataSchema
}).describe("Code block for displaying syntax-highlighted code snippets");

export type CodeBlock = z.infer<typeof CodeBlockSchema>;
export type CodeBlockData = z.infer<typeof CodeBlockDataSchema>;
export type CodeExecutionOutput = z.infer<typeof CodeExecutionOutputSchema>;
