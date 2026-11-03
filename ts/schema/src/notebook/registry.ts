import { z } from "zod";
import { NotebookBlockType, NotebookBlockTypeSchema } from "./base";
import { ChartBlockSchema } from "./blocks/chart";
import { CodeBlockSchema } from "./blocks/code";
import { DelimiterBlockSchema } from "./blocks/delimiter";
import { HeaderBlockSchema } from "./blocks/header";
import { ImageBlockSchema } from "./blocks/image";
import { ImagePickerBlockSchema } from "./blocks/imagePicker";
import { ListBlockSchema } from "./blocks/list";
import { MermaidBlockSchema } from "./blocks/mermaid";
import { ParagraphBlockSchema } from "./blocks/paragraph";
import { QuoteBlockSchema } from "./blocks/quote";
import { SqlBlockSchema } from "./blocks/sql";
import { TableBlockSchema } from "./blocks/table";

// Import data schemas
import { ChartBlockDataSchema } from "./blocks/chart";
import { CodeBlockDataSchema } from "./blocks/code";
import { DelimiterBlockDataSchema } from "./blocks/delimiter";
import { HeaderBlockDataSchema } from "./blocks/header";
import { ImageBlockDataSchema } from "./blocks/image";
import { ImagePickerBlockDataSchema } from "./blocks/imagePicker";
import { ListBlockDataSchema } from "./blocks/list";
import { MermaidBlockDataSchema } from "./blocks/mermaid";
import { ParagraphBlockDataSchema } from "./blocks/paragraph";
import { QuoteBlockDataSchema } from "./blocks/quote";
import { SqlBlockDataSchema } from "./blocks/sql";
import { TableBlockDataSchema } from "./blocks/table";

export type BlockType = z.infer<typeof NotebookBlockTypeSchema>;

export const BLOCK_SCHEMAS = {
   [NotebookBlockType.paragraph]: ParagraphBlockSchema,
   [NotebookBlockType.header]: HeaderBlockSchema,
   [NotebookBlockType.list]: ListBlockSchema,
   [NotebookBlockType.code]: CodeBlockSchema,
   [NotebookBlockType.quote]: QuoteBlockSchema,
   [NotebookBlockType.table]: TableBlockSchema,
   [NotebookBlockType.delimiter]: DelimiterBlockSchema,
   [NotebookBlockType.image]: ImageBlockSchema,
   [NotebookBlockType.imagePicker]: ImagePickerBlockSchema,
   [NotebookBlockType.sql]: SqlBlockSchema,
   [NotebookBlockType.mermaid]: MermaidBlockSchema,
   [NotebookBlockType.chart]: ChartBlockSchema
} as const;

export const BLOCK_SCHEMAS_ARRAY = [
   ParagraphBlockSchema,
   HeaderBlockSchema,
   ListBlockSchema,
   CodeBlockSchema,
   QuoteBlockSchema,
   TableBlockSchema,
   DelimiterBlockSchema,
   ImageBlockSchema,
   ImagePickerBlockSchema,
   SqlBlockSchema,
   MermaidBlockSchema,
   ChartBlockSchema
] as const;

export const BLOCK_DATA_SCHEMAS = {
   [NotebookBlockType.paragraph]: ParagraphBlockDataSchema,
   [NotebookBlockType.header]: HeaderBlockDataSchema,
   [NotebookBlockType.list]: ListBlockDataSchema,
   [NotebookBlockType.code]: CodeBlockDataSchema,
   [NotebookBlockType.quote]: QuoteBlockDataSchema,
   [NotebookBlockType.table]: TableBlockDataSchema,
   [NotebookBlockType.delimiter]: DelimiterBlockDataSchema,
   [NotebookBlockType.image]: ImageBlockDataSchema,
   [NotebookBlockType.imagePicker]: ImagePickerBlockDataSchema,
   [NotebookBlockType.sql]: SqlBlockDataSchema,
   [NotebookBlockType.mermaid]: MermaidBlockDataSchema,
   [NotebookBlockType.chart]: ChartBlockDataSchema
} as const;

export const BlockDataSchema = z.union(Object.values(BLOCK_DATA_SCHEMAS));

export const NotebookBlockSchema = z.discriminatedUnion(
   "type",
   BLOCK_SCHEMAS_ARRAY
);

export type NotebookBlock = z.infer<typeof NotebookBlockSchema>;

export function getBlockSchema(blockType: BlockType): z.ZodSchema {
   return BLOCK_SCHEMAS[blockType];
}

export function getAllBlockTypes(): BlockType[] {
   return Object.keys(BLOCK_SCHEMAS) as BlockType[];
}

export function hasBlockSchema(blockType: string): blockType is BlockType {
   return blockType in BLOCK_SCHEMAS;
}
