import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const HeaderBlockDataSchema = z
   .object({
      text: z
         .string()
         .max(500)
         .describe(
            "Header text content. May be empty for a freshly inserted block."
         ),
      level: z
         .number()
         .int()
         .min(2)
         .max(5)
         .describe("Header level (2-5) corresponding to H2-H5 HTML tags")
   })
   .describe("Data schema for header block content and level");

export const HeaderBlockSchema = BaseBlockSchema.extend({
   type: z.literal("header"),
   data: HeaderBlockDataSchema
}).describe(
   "Header block for section titles and headings with configurable levels"
);

export type HeaderBlock = z.infer<typeof HeaderBlockSchema>;
export type HeaderBlockData = z.infer<typeof HeaderBlockDataSchema>;
