import { z } from "zod";

export const ExecutePythonScriptRequestSchema = z
   .object({
      code: z
         .string()
         .min(1)
         .max(10000)
         .describe(
            "Python source code to execute in the managed runtime using current chat-session data tables"
         )
   })
   .describe("Request model for managed chat-scoped Python execution");

export type ExecutePythonScriptRequest = z.infer<
   typeof ExecutePythonScriptRequestSchema
>;

export const PendingPythonExecutionRequestSchema = z
   .object({
      toolCallId: z
         .string()
         .optional()
         .describe("Tool call ID awaiting approval"),
      toolName: z.string().describe("Tool name awaiting approval"),
      targetType: z
         .enum(["notebook", "session"])
         .describe("Execution target scope"),
      code: z.string().describe("Python source code under review"),
      notebookId: z
         .string()
         .optional()
         .describe("Notebook ID for notebook-backed execution"),
      blockId: z
         .string()
         .optional()
         .describe("Notebook block ID for notebook-backed execution")
   })
   .describe("Client review payload for a paused Python execution request");

export type PendingPythonExecutionRequest = z.infer<
   typeof PendingPythonExecutionRequestSchema
>;
