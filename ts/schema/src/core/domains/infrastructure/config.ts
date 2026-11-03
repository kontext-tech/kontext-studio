import { z } from "zod";

/**
 * Culture Info Model - locale and language information
 */
export const CultureInfoModelSchema = z
   .object({
      code: z.string(),
      displayName: z.string(),
      nativeName: z.string(),
      isRightToLeft: z.boolean()
   })
   .describe("Culture Info Model model from Kontext API");

export type CultureInfoModel = z.infer<typeof CultureInfoModelSchema>;

/**
 * File Type Configuration - defines allowed file types and content types
 */
import { FileFormatTypeSchema } from "../base/types.js";

export const FileTypeConfigurationSchema = z
   .object({
      fileExtension: z.string(),
      fileFormatType: z.lazy(() => FileFormatTypeSchema),
      allowedContentTypes: z.array(z.string())
   })
   .describe("File Type Configuration model from Kontext API");

export type FileTypeConfiguration = z.infer<typeof FileTypeConfigurationSchema>;
