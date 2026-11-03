import type { ApiErrorResult } from "@kontext-labs/common";
import type React from "react";
import { z } from "zod";

// Import Zod-inferred types from the centralized schema system
import type {
   BlockDataSchema,
   CultureInfoModel,
   NotebookDocument
} from "@kontext-labs/schema";

// Type alias for block data union
export type BlockData = z.infer<typeof BlockDataSchema>;

// Re-export block types for backward compatibility
export type {
   ChartBlock,
   CodeBlock,
   DelimiterBlock,
   HeaderBlock,
   ImageBlock,
   InlineData,
   ListBlock,
   NotebookBlock,
   NotebookDocument,
   NotebookMetadata,
   ParagraphBlock,
   QuoteBlock,
   SqlBlock,
   TableBlock
} from "@kontext-labs/schema";

export interface SidebarTabExtension {
   key: string;
   label: string;
   icon?: React.ReactNode;
   children: React.ReactNode;
}

export interface NotebookEditorProps {
   instanceId?: string; // Optional instance ID for multi-instance stores
   defaultTitle?: string;
   onSave?: (document: NotebookDocument) => Promise<void> | void;
   onExport?: (document: NotebookDocument) => Promise<void> | void;
   onDirtyChange?: (isDirty: boolean) => void;
   readonly?: boolean;
   previewMode?: boolean;
   cultures?: CultureInfoModel[];
   saveButtonText?: string;
   saveButtonIcon?: React.ReactNode;
   enableSqlBlock?: boolean;
   enableChartBlock?: boolean;
   includeFrontmatter?: boolean;
   showArticleMetadata?: boolean;
   showSaveAsDraft?: boolean;
   maxHeight?: string;
   showHeader?: boolean;
   projectId?: string; // Required for project-scoped query sessions and resource operations
   errorHandler?: (error: ApiErrorResult) => Promise<void>; // Error handler for API calls
   sidebarExtensions?: SidebarTabExtension[];
}

// Data types are now imported directly from schemas above

export interface BlockPreviewProps<TConfig = unknown> {
   data: BlockData;
   className?: string;
   config?: TConfig;
   instanceId?: string;
}
