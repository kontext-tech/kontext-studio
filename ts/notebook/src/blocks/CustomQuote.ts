import Quote from "@editorjs/quote";
import { BlockIcons } from "@kontext-labs/common";
import type { BlockPreviewProps, QuoteBlock } from "@notebook/types/notebook";
import React from "react";

export class CustomQuote extends Quote {
   static get toolbox() {
      return { title: "Quote" as const, icon: BlockIcons.quote };
   }

   static renderPreview({ data, className }: BlockPreviewProps) {
      const blockData = data as QuoteBlock["data"];

      return React.createElement(
         "blockquote",
         { className: `cdx-block ${className}` }, // Use EditorJS block class
         React.createElement("div", {
            className: "cdx-quote__text", // Use EditorJS quote text class
            dangerouslySetInnerHTML: { __html: blockData.text }
         }),
         blockData.caption &&
            React.createElement("cite", {
               className: "cdx-quote__caption", // Use EditorJS quote caption class
               dangerouslySetInnerHTML: { __html: blockData.caption }
            })
      );
   }

   /**
    */
}
