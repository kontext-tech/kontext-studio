import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const MermaidBlockDataSchema = z
   .object({
      title: z
         .string()
         .max(100)
         .optional()
         .describe("Optional title for the Mermaid block"),
      code: z
         .string()
         .max(50000)
         .describe(
            "Mermaid diagram source code. May be empty for a freshly inserted block."
         )
   })
   .describe("Data schema for Mermaid diagram blocks");

export const MermaidBlockSchema = BaseBlockSchema.extend({
   type: z.literal("mermaid"),
   data: MermaidBlockDataSchema
}).describe("Mermaid diagram block");

export type MermaidBlock = z.infer<typeof MermaidBlockSchema>;
export type MermaidBlockData = z.infer<typeof MermaidBlockDataSchema>;
