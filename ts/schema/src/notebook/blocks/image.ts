import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const ImageBlockDataFileSchema = z
   .object({
      url: z.string().describe("Image file URL"),
      name: z.string().optional().describe("Original filename"),
      size: z.number().int().optional().describe("File size in bytes")
   })
   .describe("Image file reference");

export type ImageBlockDataFile = z.infer<typeof ImageBlockDataFileSchema>;

export const ImageBlockDataSchema = z
   .object({
      file: ImageBlockDataFileSchema,
      caption: z
         .string()
         .max(500)
         .default("")
         .describe("Image caption text; empty when not yet set"),
      withBorder: z
         .boolean()
         .default(false)
         .describe("Whether to show image border"),
      withBackground: z
         .boolean()
         .default(false)
         .describe("Whether to show background"),
      stretched: z
         .boolean()
         .default(false)
         .describe("Whether image is stretched to full width")
   })
   .describe("Data schema for image block with file and display options");

export const ImageBlockSchema = BaseBlockSchema.extend({
   type: z.literal("image"),
   data: ImageBlockDataSchema
}).describe("Image block for displaying uploaded or linked images");

export type ImageBlock = z.infer<typeof ImageBlockSchema>;
export type ImageBlockData = z.infer<typeof ImageBlockDataSchema>;
