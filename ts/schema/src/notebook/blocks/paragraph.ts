import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const ParagraphBlockDataSchema = z
   .object({
      text: z
         .string()
         .max(10000)
         .describe(
            "HTML content of the paragraph block. Supports rich text formatting including bold, italic, links, and inline elements. May be empty for a freshly inserted block."
         )
   })
   .describe("Data schema for paragraph block content");

export const ParagraphBlockSchema = BaseBlockSchema.extend({
   type: z.literal("paragraph"),
   data: ParagraphBlockDataSchema
}).describe(
   "Paragraph block for rich text content with HTML formatting support"
);

export type ParagraphBlock = z.infer<typeof ParagraphBlockSchema>;
export type ParagraphBlockData = z.infer<typeof ParagraphBlockDataSchema>;
