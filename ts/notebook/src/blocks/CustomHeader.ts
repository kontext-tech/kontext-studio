import Header from "@editorjs/header";
import { BlockIcons } from "@kontext-labs/common";
import type { BlockPreviewProps, HeaderBlock } from "@notebook/types/notebook";
import * as React from "react";
export class CustomHeader extends Header {
   static get toolbox() {
      return { title: "Header" as const, icon: BlockIcons.header };
   }

   static renderPreview({ data, className }: BlockPreviewProps) {
      const blockData = data as HeaderBlock["data"];
      const level = Math.min(Math.max(blockData.level || 2, 2), 5) as
         2 | 3 | 4 | 5;
      const HeaderTag = `h${level}` as `h${typeof level}`;

      return React.createElement(HeaderTag, {
         className: `ce-header ${className}`, // Use EditorJS header class
         dangerouslySetInnerHTML: { __html: blockData.text }
      });
   }

   /**
    */
}
