import List from "@editorjs/list";
import { BlockIcons } from "@kontext-tech/common";
import type { BlockPreviewProps, ListBlock } from "@notebook/types/notebook";
import React from "react";

/**
 * Interface for EditorJS List item structure
 */
interface ListDataItem {
   content: string;
   meta: Record<string, unknown>;
   items: ListDataItem[];
   index?: number;
}

/**
 * Custom List Block that extends EditorJS List plugin
 * Uses EditorJS-compatible schema: { style, items: {content, meta, items}[], meta }
 */
export class CustomList extends List {
   static get toolbox() {
      return { title: "List" as const, icon: BlockIcons.list };
   }

   static renderPreview({ data, className }: BlockPreviewProps) {
      const blockData = data as ListBlock["data"];

      // Safety check for data structure
      if (!blockData || !blockData.items || !Array.isArray(blockData.items)) {
         return React.createElement("div", { className }, "Invalid list data");
      }

      // Choose appropriate list tag based on style
      const isChecklist = blockData.style === "checklist";
      const ListTag = blockData.style === "ordered" ? "ol" : "ul";

      // Process items according to EditorJS format
      const processedItems = blockData.items
         .map((item: unknown, index: number) => {
            const listItem = item as ListDataItem;
            // Ensure we have the proper EditorJS item structure
            const content = listItem?.content || "";
            const meta = listItem?.meta || {};
            const nestedItems = listItem?.items || [];

            return {
               content,
               meta,
               items: nestedItems,
               index
            };
         })
         .filter(
            (item: ListDataItem) =>
               item.content && item.content.trim().length > 0
         );

      const renderListItems = (
         items: ListDataItem[],
         depth = 0,
         maxDepth = 10
      ): React.ReactElement[] => {
         // Prevent infinite recursion
         if (depth >= maxDepth) {
            return [];
         }

         return items.map((item, displayIndex) => {
            const listItemProps: Record<string, unknown> = {
               key: `list-item-${item.index}-${displayIndex}`,
               style: depth > 0 ? { marginLeft: `${depth * 20}px` } : {}
            };

            let content: React.ReactElement;

            if (isChecklist) {
               // Render checklist item with checkbox
               const isChecked = item.meta?.checked === true;
               content = React.createElement(
                  "div",
                  {
                     style: {
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "8px"
                     }
                  },
                  React.createElement("input", {
                     type: "checkbox",
                     checked: isChecked,
                     disabled: true,
                     style: { marginTop: "2px" }
                  }),
                  React.createElement("span", {
                     dangerouslySetInnerHTML: { __html: item.content }
                  })
               );
            } else {
               // Render regular list item
               content = React.createElement("span", {
                  dangerouslySetInnerHTML: { __html: item.content }
               });
            }

            // Handle nested items
            if (item.items && item.items.length > 0) {
               const nestedList = React.createElement(
                  ListTag,
                  { className: "nested-list" },
                  renderListItems(item.items, depth + 1, maxDepth)
               );

               return React.createElement(
                  "li",
                  listItemProps,
                  content,
                  nestedList
               );
            }

            return React.createElement("li", listItemProps, content);
         });
      };

      // For checklist, use ul tag but with custom styling
      const FinalListTag = isChecklist ? "ul" : ListTag;
      const listClassName = `notebook-preview__list ${className} ${
         isChecklist ? "checklist" : ""
      }`;

      return React.createElement(
         FinalListTag,
         {
            className: listClassName,
            style: isChecklist ? { listStyle: "none", paddingLeft: "0" } : {}
         },
         renderListItems(processedItems)
      );
   }

   /**
    */
}
