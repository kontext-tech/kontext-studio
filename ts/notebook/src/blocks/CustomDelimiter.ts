import Delimiter from "@editorjs/delimiter";
import { BlockIcons } from "@kontext-labs/common";
import type { BlockPreviewProps } from "@notebook/types/notebook";
import React from "react";

export class CustomDelimiter extends Delimiter {
   static get toolbox() {
      return { title: "Delimiter" as const, icon: BlockIcons.delimiter };
   }

   static renderPreview({ className }: BlockPreviewProps) {
      return React.createElement("hr", {
         className: `notebook-preview__delimiter ${className}` // Use preview-specific class
      });
   }

   /**
    */
}
