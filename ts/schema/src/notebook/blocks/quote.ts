import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const QuoteAlignmentSchema = z
   .enum(["left", "center"])
   .describe("Quote text alignment");

export type QuoteAlignment = z.infer<typeof QuoteAlignmentSchema>;
export const QuoteAlignment = QuoteAlignmentSchema.enum;

export const QuoteBlockDataSchema = z
   .object({
      text: z
         .string()
         .max(2000)
         .describe(
            "Quote text content. May be empty for a freshly inserted block."
         ),
      caption: z
         .string()
         .max(500)
         .optional()
         .describe("Optional quote caption or attribution"),
      alignment: QuoteAlignmentSchema.default("left")
   })
   .describe("Data schema for quote block with optional caption");

export const QuoteBlockSchema = BaseBlockSchema.extend({
   type: z.literal("quote"),
   data: QuoteBlockDataSchema
}).describe("Quote block for highlighted text with optional attribution");

export type QuoteBlock = z.infer<typeof QuoteBlockSchema>;
export type QuoteBlockData = z.infer<typeof QuoteBlockDataSchema>;
