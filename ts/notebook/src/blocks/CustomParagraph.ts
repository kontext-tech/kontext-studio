import Paragraph from "@editorjs/paragraph";
import { BlockIcons } from "@kontext-tech/common";
import type {
   BlockPreviewProps,
   ParagraphBlock
} from "@notebook/types/notebook";
import React from "react";

export class CustomParagraph extends Paragraph {
   static get toolbox() {
      return { title: "Text" as const, icon: BlockIcons.paragraph };
   }

   static renderPreview({ data, className }: BlockPreviewProps) {
      const blockData = data as ParagraphBlock["data"];
      if (!blockData.text?.trim()) return null;

      return React.createElement("div", {
         className: `cdx-block ${className}`, // Use EditorJS block class
         dangerouslySetInnerHTML: { __html: blockData.text }
      });
   }

   /**
    */
}
