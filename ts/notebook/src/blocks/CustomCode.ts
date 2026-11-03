import type { BlockAPI } from "@editorjs/editorjs";
import { BlockIcons } from "@kontext-labs/common";
import type { CodeBlockData } from "@kontext-labs/schema";
import {
   CodeBlockComponent,
   type CodeBlockComponentRef
} from "@notebook/components/code/CodeBlockComponent";
import type { BlockPreviewProps } from "@notebook/types/notebook";
import { normalizeCodeBlockData } from "@notebook/utils/codeBlock";
import { createBlockId } from "@notebook/utils/coreUtils";
import { sharedReactRoot } from "@notebook/utils/sharedReactRoot";
import React from "react";
import { type BaseBlockConfig, BaseReactBlock } from "./BaseReactBlock";

/**
 * Enhanced Code Block with support for Python execution
 */
export class CustomCode extends BaseReactBlock {
   private data: CodeBlockData;
   private config: BaseBlockConfig;
   private container: HTMLElement | null = null;
   private lastRenderedData: string | null = null;
   private componentRef: React.RefObject<CodeBlockComponentRef | null>;

   static get toolbox() {
      return { title: "Code", icon: BlockIcons.code };
   }

   /**
    * EditorJS's paste catcher re-inserts pasted text at the caret of any
    * focused non-native editable (its gate is `input`/`textarea` only), which
    * duplicates pastes inside the block's CodeMirror editor. Declaring
    * `pasteConfig === false` puts the tool in EditorJS's paste exception
    * list so the catcher ignores this block entirely and CodeMirror handles
    * its own paste once.
    */
   static get pasteConfig() {
      return false;
   }

   static renderPreview({ data, className: _, instanceId }: BlockPreviewProps) {
      return React.createElement(CodeBlockComponent, {
         id: `preview-${createBlockId()}`,
         data: data as CodeBlockData,
         config: { instanceId } as unknown as BaseBlockConfig,
         onChange: () => {},
         readonly: true,
         previewMode: true
      });
   }

   constructor({
      data,
      config,
      block
   }: {
      data?: CodeBlockData;
      config: BaseBlockConfig;
      block?: BlockAPI;
   }) {
      super("code", block);

      this.data = normalizeCodeBlockData({
         title: data?.title || "",
         code: data?.code || "",
         outputs: data?.outputs || [],
         isExecuting: data?.isExecuting || false,
         showCode: data?.showCode !== false
      });

      this.config = this.parseConfig(config);
      this.componentRef = React.createRef<CodeBlockComponentRef>();
   }

   render(): HTMLElement {
      this.wrapper = this.createContainer("kontext-notebook-editor code-block");
      this.createMainSection();
      return this.wrapper!;
   }

   private createMainSection(): void {
      this.container = this.createContainer("code-block__main", this.wrapper!);
      this.renderMain();
   }

   private renderMain(): void {
      if (!this.container) return;

      const currentDataString = JSON.stringify(this.data);
      if (this.lastRenderedData === currentDataString) return;

      sharedReactRoot.removePortal(`${this.blockId}-main`);

      const MainComponent = React.createElement(CodeBlockComponent, {
         id: this.blockId,
         data: this.data,
         config: this.config,
         onChange: this.handleDataChange,
         readonly: false,
         previewMode: false, // In editor mode, previewMode is false
         ref: this.componentRef
      });

      sharedReactRoot.createPortal(
         `${this.blockId}-main`,
         this.container,
         MainComponent
      );

      this.lastRenderedData = currentDataString;
   }

   private handleDataChange = (newData: CodeBlockData): void => {
      this.data = normalizeCodeBlockData(newData);
      // No re-render here to avoid focus issues while typing, but tell the
      // editor so the change is tracked and saveable.
      this.notifyChange();
   };

   public syncPendingChanges(): void {
      (
         this.componentRef.current as CodeBlockComponentRef | null
      )?.syncPendingChanges();
   }

   save(): CodeBlockData {
      this.syncPendingChanges();
      return this.data;
   }

   destroy(): void {
      sharedReactRoot.removePortal(`${this.blockId}-main`);
      super.destroy();
      this.container = null;
   }

   /**
    */
}
