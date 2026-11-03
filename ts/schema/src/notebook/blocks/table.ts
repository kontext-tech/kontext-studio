import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const TableBlockDataSchema = z
   .object({
      withHeadings: z
         .boolean()
         .default(false)
         .describe("Whether the table has header row"),
      content: z
         .array(z.array(z.string()))
         .describe(
            "2D array representing table content. May be empty for a freshly inserted block."
         ),
      stretched: z
         .boolean()
         .optional()
         .describe("Whether the table is stretched to full-width")
   })
   .describe("Data schema for table block with optional headings");

export const TableBlockSchema = BaseBlockSchema.extend({
   type: z.literal("table"),
   data: TableBlockDataSchema
}).describe("Table block for structured tabular data display");

export type TableBlock = z.infer<typeof TableBlockSchema>;
export type TableBlockData = z.infer<typeof TableBlockDataSchema>;
