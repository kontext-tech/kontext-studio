import type { BlockAPI } from "@editorjs/editorjs";
import { DEFAULT_COLOR_PALETTE } from "@kontext-tech/chart";
import { BlockIcons, logger } from "@kontext-tech/common";
import type { ChartBlockData, NotebookDocument } from "@kontext-tech/schema";
import { ChartBlockComponent } from "@notebook/components/chart/ChartBlockComponent";
import { useNotebookStore } from "@notebook/stores/notebookStore";
import { createBlockId } from "@notebook/utils/coreUtils";
import { sharedReactRoot } from "@notebook/utils/sharedReactRoot";
import { Alert } from "antd";
import type { MessageInstance } from "antd/es/message/interface";
import React from "react";
import { BaseReactBlock, type BaseBlockConfig } from "./BaseReactBlock";

// Constants
export const KONTEXT_CHART_BLOCK_LANGUAGE = "kontext-chart-block";

// Shared defaults for all Chart blocks to ensure consistency between constructor and renderPreview
const DEFAULT_CHART_CONFIG = {
   chartType: "line" as const,
   title: "",
   height: 400,
   colorPalette: DEFAULT_COLOR_PALETTE
};

interface ChartBlockConfig extends BaseBlockConfig {
   message?: MessageInstance;
}

/**
 * Chart Block for creating interactive charts from SQL query results
 */
export class ChartBlock extends BaseReactBlock {
   private data: ChartBlockData;
   private config: ChartBlockConfig;
   private container: HTMLElement | null = null;
   private lastRenderedData: string | null = null;

   static get toolbox() {
      return {
         title: "Chart",
         icon: BlockIcons.chart
      };
   }

   static renderPreview({
      data,
      className,
      instanceId
   }: {
      data: ChartBlockData;
      className?: string;
      instanceId?: string;
   }) {
      // Use shared defaults to ensure consistency between editor and preview modes.
      const baseConfig = DEFAULT_CHART_CONFIG;

      // Ensure data has the required config structure with defaults applied
      const previewData: ChartBlockData = {
         ...data,
         config: data.config ? { ...baseConfig, ...data.config } : baseConfig
      } as ChartBlockData;

      // Use ChartBlockComponent in readonly/preview mode for consistency
      return React.createElement(
         "div",
         {
            className: `kontext-notebook-editor chart-block ${className || ""}`
         },
         React.createElement(ChartBlockComponent, {
            data: previewData,
            blockId: `preview-${createBlockId()}`,
            onChange: () => {}, // No-op for preview mode
            readonly: true, // Hide edit buttons in preview mode
            className: "chart-wizard--preview",
            instanceId
         })
      );
   }

   constructor({
      data,
      config,
      block
   }: {
      data?: ChartBlockData;
      config: ChartBlockConfig;
      block?: BlockAPI;
   }) {
      super("chart", block);

      // Handle data merging properly - data should have a config field
      if (data && data.config) {
         // Merge the config with defaults
         const mergedConfig = { ...DEFAULT_CHART_CONFIG, ...data.config };
         this.data = { ...data, config: mergedConfig } as ChartBlockData;
      } else {
         // No data provided, create default structure
         this.data = {
            config: DEFAULT_CHART_CONFIG
         } as ChartBlockData;
      }

      this.config = this.parseConfig(config);

      logger.debug(`[ChartBlock ${this.blockId}] Constructor:`, {
         title: this.data.config?.title || "undefined",
         chartType: this.data.config?.chartType || "undefined",
         hasDataRef: !!this.data.dataRef,
         configKeys: Object.keys(this.config),
         rawConfigKeys: Object.keys(config)
      });
   }

   /**
    * Get the current document from the notebook store
    */
   private getDocument(): NotebookDocument | undefined {
      try {
         const state = useNotebookStore.getState();
         const instanceId = this.config?.instanceId || "default";
         return state.getInstanceState(instanceId)?.document || undefined;
      } catch (error) {
         console.warn(
            `[ChartBlock ${this.blockId}] Store access failed:`,
            error
         );
         return undefined;
      }
   }

   render(): HTMLElement {
      logger.debug(`[ChartBlock ${this.blockId}] Rendering with data:`, {
         chartType: this.data.config?.chartType || "undefined",
         hasDataRef: !!this.data.dataRef,
         title: this.data.config?.title || "undefined"
      });

      this.wrapper = this.createContainer(
         "kontext-notebook-editor chart-block"
      );

      this.createMainSection();

      return this.wrapper;
   }

   private createMainSection(): void {
      this.container = this.createContainer("chart-block__main", this.wrapper!);
      logger.debug(
         `[ChartBlock ${this.blockId}] Main container created:`,
         this.container
      );
      this.renderMain();
   }

   private renderMain(): void {
      if (!this.container) {
         logger.debug(
            `[ChartBlock ${this.blockId}] Cannot render: missing container`
         );
         return;
      }

      const document = this.getDocument();
      logger.debug(`[ChartBlock ${this.blockId}] Document check:`, {
         resolvedDocument: !!document,
         documentBlocks: document
            ? Object.keys(document.blocks || {}).length
            : 0
      });

      if (!document) {
         logger.debug(
            `[ChartBlock ${this.blockId}] No document available, showing placeholder`
         );

         // Clear any existing portal first
         sharedReactRoot.removePortal(`${this.blockId}-main`);

         // Show a placeholder when no document is available
         const PlaceholderComponent = React.createElement(
            "div",
            { style: { padding: 16 } },
            React.createElement(Alert, {
               message: "Document context required to configure charts",
               type: "warning",
               showIcon: true
            })
         );

         sharedReactRoot.createPortal(
            `${this.blockId}-main`,
            this.container,
            PlaceholderComponent
         );
         return;
      }

      // Check if we need to re-render based on data changes
      const currentDataString = JSON.stringify(this.data);
      if (this.lastRenderedData === currentDataString) {
         logger.debug(
            `[ChartBlock ${this.blockId}] Data unchanged, skipping render`
         );
         return;
      }

      logger.debug(
         `[ChartBlock ${this.blockId}] Rendering main component with document`
      );

      // Clear any existing portal first
      sharedReactRoot.removePortal(`${this.blockId}-main`);

      const MainComponent = React.createElement(ChartBlockComponent, {
         data: this.data,
         blockId: this.blockId,
         onChange: this.handleDataChange,
         instanceId: this.config?.instanceId
      });

      sharedReactRoot.createPortal(
         `${this.blockId}-main`,
         this.container,
         MainComponent
      );

      // Remember what we rendered
      this.lastRenderedData = currentDataString;

      logger.debug(
         `[ChartBlock ${this.blockId}] Portal created for main component`
      );
   }

   private handleDataChange = (newData: ChartBlockData): void => {
      logger.debug(
         `[ChartBlock ${this.blockId}] Data changed:`,
         JSON.stringify({
            from: {
               title: this.data.config?.title || "undefined",
               chartType: this.data.config?.chartType || "undefined",
               hasDataRef: !!this.data.dataRef
            },
            to: {
               title: newData.config?.title || "undefined",
               chartType: newData.config?.chartType || "undefined",
               hasDataRef: !!newData.dataRef
            }
         })
      );

      // Check if data actually changed to prevent infinite loops
      const dataChanged = JSON.stringify(this.data) !== JSON.stringify(newData);
      if (!dataChanged) {
         logger.debug(
            `[ChartBlock ${this.blockId}] Data unchanged, skipping update`
         );
         return;
      }

      logger.debug(
         `[ChartBlock ${this.blockId}] Data actually changed, updating`
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
    * Force a re-render of the component (useful for external updates)
    */
   public forceUpdate(): void {
      this.lastRenderedData = null;
      this.renderMain();
   }

   /**
    * Update data and trigger re-render (safer than handleDataChange for internal use)
    */
   public updateData(newData: ChartBlockData): void {
      const dataChanged = JSON.stringify(this.data) !== JSON.stringify(newData);
      if (dataChanged) {
         this.data = { ...newData };
         this.forceUpdate();
      }
   }

   /**
    * Get the block ID for serialization purposes
    */
   public getBlockId(): string {
      return this.blockId;
   }

   save(): ChartBlockData {
      // Return data WITHOUT logging every time unless it's a real save or debugging
      return this.data;
   }

   destroy(): void {
      // Clean up the shared React root portal
      sharedReactRoot.removePortal(`${this.blockId}-main`);

      super.destroy();
      this.container = null;
   }

   static get pasteConfig() {
      return {
         tags: [],
         patterns: {}
      };
   }

   /**
    * Supports new kontext-chart-block JSON format
    */
}
