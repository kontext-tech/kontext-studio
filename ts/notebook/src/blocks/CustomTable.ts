import Table from "@editorjs/table";
import { BlockIcons } from "@kontext-tech/common";
import type { BlockPreviewProps, TableBlock } from "@notebook/types/notebook";
import React from "react";

export class CustomTable extends Table {
   static get toolbox() {
      return { title: "Table" as const, icon: BlockIcons.table };
   }

   static renderPreview({ data, className }: BlockPreviewProps) {
      const blockData = data as TableBlock["data"];

      return React.createElement(
         "div",
         { className: `cdx-block ${className}` }, // Use EditorJS block class
         React.createElement(
            "table",
            {
               className: "tc-table", // Use EditorJS table class
               style: {
                  border: "1px solid var(--editor-border-secondary)",
                  borderCollapse: "collapse",
                  width: "100%"
               }
            },
            blockData.withHeadings &&
               blockData.content.length > 0 &&
               React.createElement(
                  "thead",
                  null,
                  React.createElement(
                     "tr",
                     null,
                     blockData.content[0].map((cell, cellIndex) =>
                        React.createElement("th", {
                           key: cellIndex,
                           style: {
                              border:
                                 "1px solid var(--editor-border-secondary)",
                              padding: "8px 12px",
                              backgroundColor: "var(--editor-bg)",
                              textAlign: "left"
                           },
                           dangerouslySetInnerHTML: { __html: cell }
                        })
                     )
                  )
               ),
            React.createElement(
               "tbody",
               null,
               blockData.content
                  .slice(blockData.withHeadings ? 1 : 0)
                  .map((row, rowIndex) =>
                     React.createElement(
                        "tr",
                        { key: rowIndex },
                        row.map((cell, cellIndex) =>
                           React.createElement("td", {
                              key: cellIndex,
                              style: {
                                 border:
                                    "1px solid var(--editor-border-secondary)",
                                 padding: "8px 12px"
                              },
                              dangerouslySetInnerHTML: { __html: cell }
                           })
                        )
                     )
                  )
            )
         )
      );
   }

   /**
    */
}
