import { z } from "zod";
import { NotebookMetadataSchema } from "./base";
import { NotebookBlockSchema } from "./registry";

export const NotebookBlocksSchema = z
   .array(NotebookBlockSchema)
   .describe("Array of document blocks");

export const NotebookDocumentSchema = z
   .object({
      title: z.string().min(1).max(200).describe("Document title"),
      metadata: NotebookMetadataSchema.optional().describe(
         "Optional document metadata"
      ),
      created: z.coerce
         .number()
         .int()
         .describe(
            "format: int64 | Creation timestamp (Unix epoch milliseconds)"
         ),
      modified: z.coerce
         .number()
         .int()
         .describe("format: int64 | Last modification timestamp"),
      blocks: NotebookBlocksSchema
   })
   .describe(
      "Complete notebook document schema. The file ID serves as the notebook identifier."
   );

export type NotebookDocument = z.infer<typeof NotebookDocumentSchema>;
