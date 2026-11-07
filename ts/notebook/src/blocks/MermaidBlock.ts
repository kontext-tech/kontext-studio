import type { BlockAPI } from "@editorjs/editorjs";
import { BlockIcons } from "@kontext-tech/common";
import type { MermaidBlockData } from "@kontext-tech/schema";
import { MermaidBlockComponent } from "@notebook/components/mermaid";
import { sharedReactRoot } from "@notebook/utils/sharedReactRoot";
import React from "react";
import { BaseReactBlock, type BaseBlockConfig } from "./BaseReactBlock";

export const KONTEXT_MERMAID_BLOCK_LANGUAGE = "kontext-mermaid-block";

/**
 * Mermaid block for rendering Mermaid diagrams.
 */
export class MermaidBlock extends BaseReactBlock {
   private data: MermaidBlockData;
   private config: BaseBlockConfig;
   private container: HTMLElement | null = null;
   private lastRenderedData: string | null = null;

   static get toolbox() {
      return {
         title: "Mermaid Diagram",
         icon: BlockIcons.code
      };
   }

   static renderPreview({
      data,
      className
   }: {
      data: MermaidBlockData;
      className?: string;
   }) {
      return React.createElement(
         "div",
         {
            className: `kontext-notebook-editor mermaid-block ${
               className || ""
            }`
         },
         React.createElement(MermaidBlockComponent, {
            id: "preview",
            data,
            onChange: () => {},
            readonly: true
         })
      );
   }

   constructor({
      data,
      config,
      block
   }: {
      data?: MermaidBlockData;
      config: BaseBlockConfig;
      block?: BlockAPI;
   }) {
      super("mermaid", block);

      this.data = {
         title: data?.title || "Mermaid Diagram",
         code: data?.code || ""
      };

      this.config = this.parseConfig(config);
   }

   render(): HTMLElement {
      this.wrapper = this.createContainer(
         "kontext-notebook-editor mermaid-block"
      );

      this.container = this.createContainer(
         "mermaid-block__main",
         this.wrapper
      );
      this.renderMain();

      return this.wrapper;
   }

   private renderMain(): void {
      if (!this.container) return;

      const currentDataString = JSON.stringify(this.data);
      if (this.lastRenderedData === currentDataString) return;

      sharedReactRoot.removePortal(`${this.blockId}-main`);

      const MainComponent = React.createElement(MermaidBlockComponent, {
         id: this.blockId,
         data: this.data,
         onChange: this.handleDataChange,
         readonly: false
      });

      sharedReactRoot.createPortal(
         `${this.blockId}-main`,
         this.container,
         MainComponent
      );
      this.lastRenderedData = currentDataString;
   }

   private handleDataChange = (newData: MermaidBlockData): void => {
      const dataChanged = JSON.stringify(this.data) !== JSON.stringify(newData);
      if (!dataChanged) return;

      this.data = { ...newData };
      this.lastRenderedData = null;
      this.renderMain();

      this.notifyChange();
   };

   save(): MermaidBlockData {
      return this.data;
   }

   destroy(): void {
      sharedReactRoot.removePortal(`${this.blockId}-main`);
      super.destroy();
      this.container = null;
   }
}
