import {
   ChartBlock,
   CustomCode,
   CustomDelimiter,
   CustomHeader,
   CustomImage,
   CustomList,
   CustomParagraph,
   CustomQuote,
   CustomTable,
   MermaidBlock,
   SqlBlock
} from "@notebook/blocks";
import type { NotebookBlock, NotebookDocument } from "@notebook/types/notebook";
import { Typography } from "antd";
import React from "react";
import "../styles/editorjs-theme.css";

const { Text } = Typography;

interface NotebookPreviewProps {
   document: NotebookDocument;
   className?: string;
   style?: React.CSSProperties;
   instanceId?: string;
}

interface BlockRendererProps {
   block: NotebookBlock;
   index: number;
   instanceId?: string;
}

/**
 * Renders individual blocks in readonly preview mode
 */
const BlockRenderer: React.FC<BlockRendererProps> = ({
   block,
   index,
   instanceId
}) => {
   const renderBlock = () => {
      const className = "";

      switch (block.type) {
         case "paragraph":
            return CustomParagraph.renderPreview({
               data: block.data,
               className
            });

         case "header":
            return CustomHeader.renderPreview({ data: block.data, className });

         case "list":
            return CustomList.renderPreview({ data: block.data, className });

         case "code":
            return CustomCode.renderPreview({
               data: block.data,
               className,
               instanceId
            });

         case "quote":
            return CustomQuote.renderPreview({ data: block.data, className });

         case "table":
            return CustomTable.renderPreview({ data: block.data, className });

         case "delimiter":
            return CustomDelimiter.renderPreview({
               data: block.data,
               className
            });

         case "image":
            return CustomImage.renderPreview({ data: block.data, className });

         case "sql":
            return SqlBlock.renderPreview({
               data: block.data,
               className,
               instanceId
            });

         case "chart":
            return ChartBlock.renderPreview({
               data: block.data,
               className,
               instanceId
            });

         case "mermaid":
            return MermaidBlock.renderPreview({
               data: block.data,
               className
            });

         default:
            return (
               <div className="notebook-preview__unknown-block">
                  <Text type="secondary">
                     Unknown block type: {(block as { type: string }).type}
                  </Text>
               </div>
            );
      }
   };

   return (
      <div
         key={block.id || index}
         className={`notebook-preview__block notebook-preview__block--${block.type}`}
      >
         {renderBlock()}
      </div>
   );
};

/**
 * NotebookPreview component for displaying notebook content in readonly mode
 */
const NotebookPreview: React.FC<NotebookPreviewProps> = ({
   document,
   className = "",
   style,
   instanceId
}) => {
   if (!document?.blocks || document.blocks.length === 0) {
      return (
         <div
            className={`notebook-preview notebook-preview--empty ${className}`}
            style={style}
         >
            <div className="notebook-preview__empty-state">
               <Text type="secondary">This notebook is empty</Text>
            </div>
         </div>
      );
   }

   return (
      <div className={`notebook-preview ${className}`} style={style}>
         <div className="notebook-preview__content">
            {document.blocks.map((block, index) => (
               <BlockRenderer
                  key={block.id || index}
                  block={block}
                  index={index}
                  instanceId={instanceId}
               />
            ))}
         </div>
      </div>
   );
};

export default NotebookPreview;
