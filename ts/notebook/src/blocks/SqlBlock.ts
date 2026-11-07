import type { BlockAPI } from "@editorjs/editorjs";
import { BlockIcons, logger } from "@kontext-tech/common";
import type { SqlBlockData } from "@kontext-tech/schema";
import {
   SqlBlockComponent,
   SqlBlockPreview,
   type SqlBlockComponentRef
} from "@notebook/components/sql";
import type { BlockPreviewProps } from "@notebook/types/notebook";
import { sharedReactRoot } from "@notebook/utils/sharedReactRoot";
import React from "react";
import { type BaseBlockConfig, BaseReactBlock } from "./BaseReactBlock";

// Constants
export const KONTEXT_SQL_BLOCK_LANGUAGE = "kontext-sql-block";

/**
 * SQL Block for executing SQL queries with document-level session management
 */
export class SqlBlock extends BaseReactBlock {
   private data: SqlBlockData;
   private config: BaseBlockConfig;
   private container: HTMLElement | null = null;
   private lastRenderedData: string | null = null;
   private componentRef: React.RefObject<SqlBlockComponentRef>;

   static get toolbox() {
      return {
         title: "SQL Query",
         icon: BlockIcons.sql
      };
   }

   static renderPreview({ data, instanceId }: BlockPreviewProps) {
      return React.createElement(SqlBlockPreview, {
         data: data as SqlBlockData,
         instanceId
      });
   }

   constructor({
      data,
      config,
      block
   }: {
      data?: SqlBlockData;
      config: BaseBlockConfig;
      block?: BlockAPI;
   }) {
      super("sql", block);

      this.data = {
         ...data,
         title: data?.title || "SQL Query",
         code: data?.code || "",
         dataRef: data?.dataRef
      };

      // Handle Editor.js config format which may be nested
      this.config = this.parseConfig(config);

      // Initialize the component ref
      this.componentRef =
         React.createRef<SqlBlockComponentRef>() as React.RefObject<SqlBlockComponentRef>;

      logger.debug(`[SqlBlock ${this.blockId}] Constructor:`, {
         title: this.data.title,
         hasCode: !!this.data.code,
         code: this.data.code?.substring(0, 50),
         hasDataRef: !!this.data.dataRef?.dataId,
         blockId: this.blockId
      });
   }

   render(): HTMLElement {
      logger.debug(`[SqlBlock ${this.blockId}] Rendering with data:`, {
         title: this.data.title,
         code: this.data.code?.substring(0, 50),
         hasDataRef: !!this.data.dataRef?.dataId
      });

      this.wrapper = this.createContainer("kontext-notebook-editor sql-block");

      this.createMainSection();

      return this.wrapper;
   }

   private createMainSection(): void {
      this.container = this.createContainer("sql-block__main", this.wrapper!);
      this.renderMain();
   }

   private renderMain(): void {
      if (!this.container) {
         logger.debug(
            `[SqlBlock ${this.blockId}] Cannot render: missing container`
         );
         return;
      }

      // Check if we need to re-render based on data changes
      const currentDataString = JSON.stringify(this.data);
      if (this.lastRenderedData === currentDataString) {
         logger.debug(
            `[SqlBlock ${this.blockId}] Data unchanged, skipping render`
         );
         return;
      }

      logger.debug(`[SqlBlock ${this.blockId}] Rendering main component`);

      // Clear any existing portal first
      sharedReactRoot.removePortal(`${this.blockId}-main`);

      const MainComponent = React.createElement(SqlBlockComponent, {
         id: this.blockId,
         data: this.data,
         config: this.config,
         onChange: this.handleDataChange,
         readonly: false, // SqlBlock is always editable in normal mode
         ref: this.componentRef
      });

      sharedReactRoot.createPortal(
         `${this.blockId}-main`,
         this.container,
         MainComponent
      );

      // Remember what we rendered
      this.lastRenderedData = currentDataString;

      logger.debug(
         `[SqlBlock ${this.blockId}] Portal created for main component`
      );
   }

   private handleDataChange = (newData: SqlBlockData): void => {
      logger.debug(`[SqlBlock ${this.blockId}] Data changed:`, {
         from: {
            title: this.data.title,
            code: this.data.code?.substring(0, 50),
            hasDataRef: !!this.data.dataRef?.dataId
         },
         to: {
            title: newData.title,
            code: newData.code?.substring(0, 50),
            hasDataRef: !!newData.dataRef?.dataId
         }
      });

      // Check if data actually changed to prevent infinite loops
      const dataChanged = JSON.stringify(this.data) !== JSON.stringify(newData);
      if (!dataChanged) {
         logger.debug(
            `[SqlBlock ${this.blockId}] Data unchanged, skipping update`
         );
         return;
      }

      logger.debug(
         `[SqlBlock ${this.blockId}] Data actually changed, updating`
      );

      // Update internal data
      this.data = { ...newData };

      // Force re-render by clearing the lastRenderedData
      this.lastRenderedData = null;

      // Re-render the main component to reflect changes
      this.renderMain();

      this.notifyChange();
   };

   /**
    * Sync any pending changes from the component to the store/block
    * This should be called when the notebook is saved
    */
   public syncPendingChanges(): void {
      this.componentRef.current?.syncPendingChanges();
   }

   /**
    * Force a re-render of the component (useful for external updates)
    */
   public forceUpdate(): void {
      this.lastRenderedData = null;
      this.renderMain();
   }

   /**
    * Get the block ID for serialization purposes
    */
   public getBlockId(): string {
      return this.blockId;
   }
   save(): SqlBlockData {
      // Sync any pending changes before saving
      this.syncPendingChanges();

      return this.data;
   }

   destroy(): void {
      // Clean up the shared React root portal
      sharedReactRoot.removePortal(`${this.blockId}-main`);

      super.destroy();
      this.container = null;
   }

   /**
    * `false` puts this tool in EditorJS's paste exception list: the catcher
    * re-inserts pasted text into any focused non-native editable, which
    * duplicated pastes inside the block's CodeMirror editor. Pasting SQL-like
    * text into *paragraph* blocks no longer converts into a SQL block — the
    * conversion required this registration and the duplication outweighed it.
    */
   static get pasteConfig() {
      return false;
   }
}
