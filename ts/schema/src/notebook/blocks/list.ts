import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const ListItemMetaSchema = z
   .object({
      checked: z
         .boolean()
         .optional()
         .describe("Checked state for checklist items")
   })
   .default({})
   .describe("Metadata for individual list items");

export type ListItemMeta = z.infer<typeof ListItemMetaSchema>;

export interface ListItemType {
   content: string;
   meta: Record<string, unknown>;
   items: ListItemType[];
}

export const ListItemSchema: z.ZodType<ListItemType> = z.object({
   content: z.string().describe("The text content of the list item"),
   meta: ListItemMetaSchema.describe("Metadata for the list item"),
   items: z
      .lazy(() => z.array(ListItemSchema))
      .default([])
      .describe("Nested list items")
});

export const ListStyleSchema = z
   .enum(["ordered", "unordered", "checklist"])
   .describe(
      "List style type - ordered for numbered lists, unordered for bullet points, checklist for checkbox lists"
   );

export type ListStyle = z.infer<typeof ListStyleSchema>;
export const ListStyle = ListStyleSchema.enum;

export const CounterTypeSchema = z
   .enum([
      "numeric",
      "lower-roman",
      "upper-roman",
      "lower-alpha",
      "upper-alpha"
   ])
   .describe("Counter type for ordered lists");

export type CounterType = z.infer<typeof CounterTypeSchema>;
export const CounterType = CounterTypeSchema.enum;

export const ListBlockMetaSchema = z
   .object({
      start: z
         .number()
         .int()
         .optional()
         .describe("Starting number for ordered lists"),
      counterType: z
         .lazy(() => CounterTypeSchema)
         .optional()
         .describe("Counter type for ordered lists")
   })
   .default({})
   .describe("Metadata for the entire list block");

export type ListBlockMeta = z.infer<typeof ListBlockMetaSchema>;

export const ListBlockDataSchema = z
   .object({
      style: z.lazy(() => ListStyleSchema),
      items: z
         .array(ListItemSchema)
         .describe(
            "Array of list items with content, meta, and nested items. May be empty for a freshly inserted block."
         ),
      meta: ListBlockMetaSchema
   })
   .describe("Data schema for list block compatible with EditorJS List plugin");

export const ListBlockSchema = BaseBlockSchema.extend({
   type: z.literal("list"),
   data: ListBlockDataSchema
}).describe(
   "List block for ordered, unordered, and checklist with EditorJS compatibility"
);

export type ListItem = z.infer<typeof ListItemSchema>;
export type ListBlock = z.infer<typeof ListBlockSchema>;
export type ListBlockData = z.infer<typeof ListBlockDataSchema>;
