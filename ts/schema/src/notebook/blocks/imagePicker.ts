import { z } from "zod";
import { BaseBlockSchema } from "../base";

export const ImagePickerBlockDataSchema = z
   .object({
      resourceId: z
         .string()
         .describe(
            "ID of the selected resource from the platform's resource library"
         ),
      caption: z
         .string()
         .max(500)
         .optional()
         .describe("Optional caption text for the selected image")
   })
   .describe("Data schema for image picker block resource ID and caption");

export const ImagePickerBlockSchema = BaseBlockSchema.extend({
   type: z.literal("imagePicker"),
   data: ImagePickerBlockDataSchema
}).describe(
   "Image picker block for selecting images from resources or URLs with captions"
);

export type ImagePickerBlock = z.infer<typeof ImagePickerBlockSchema>;
export type ImagePickerBlockData = z.infer<typeof ImagePickerBlockDataSchema>;
