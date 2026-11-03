import type { BlockAPI, BlockTool } from "@editorjs/editorjs";
import type { ApiErrorResult } from "@kontext-tech/common";
import type { BlockPreviewProps } from "@notebook/types/notebook";
import { createBlockId } from "@notebook/utils/coreUtils";
import { sharedReactRoot } from "@notebook/utils/sharedReactRoot";
import type { MessageInstance } from "antd/es/message/interface";
import type { HookAPI } from "antd/es/modal/useModal";
import React from "react";

export interface BaseBlockConfig {
   /**
    * Optional notebook store instance ID. When provided, all block operations
    * should target this instance instead of relying on the global active instance.
    */
   instanceId?: string;
   message?: MessageInstance;
   modal?: HookAPI;
   projectId?: string;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
}

interface PortalInfo {
   id: string;
   container: HTMLElement;
   component: React.ReactElement;
}

/**
 * Base class for blocks that use React components with the shared React root
 */
export abstract class BaseReactBlock implements BlockTool {
   protected blockId: string;
   protected wrapper: HTMLElement | null = null;
   protected portals: Map<string, PortalInfo> = new Map();

   /** EditorJS block handle, used to signal data changes for portal blocks. */
   protected block?: BlockAPI;

   constructor(blockType: string, block?: BlockAPI) {
      // If EditorJS provides block object with ID, use it; otherwise generate new UUID
      if (block?.id) {
         this.blockId = block.id;
      } else {
         // Generate a new UUID for new blocks
         this.blockId = createBlockId();
      }

      this.block = block;
   }

   /**
    * Tell EditorJS this block's data changed.
    *
    * Native tools mutate the DOM so the editor notices their edits. Portal
    * blocks (SQL/code/chart/mermaid) mutate data outside the editor, so they
    * call this to trigger EditorJS's own `onChange` — the single path that
    * updates the editor- and store-level dirty flags the Save button reads.
    * `onChange` is hash-deduped, so repeated calls do not loop.
    */
   protected notifyChange(): void {
      try {
         this.block?.dispatchChange();
      } catch (error) {
         // The block may already be detached during teardown.
         console.warn(
            `[${this.constructor.name} ${this.blockId}] notifyChange failed`,
            error
         );
      }
   }

   /**
    * Create a portal with automatic cleanup tracking
    */
   protected createPortal(
      portalId: string,
      container: HTMLElement,
      component: React.ReactElement
   ): void {
      const fullPortalId = `${this.blockId}-${portalId}`;

      try {
         sharedReactRoot.createPortal(fullPortalId, container, component);

         // Track portal for cleanup
         this.portals.set(portalId, {
            id: fullPortalId,
            container,
            component
         });
      } catch (error) {
         console.error(`Error creating portal ${fullPortalId}:`, error);
      }
   }

   /**
    * Remove a specific portal
    */
   protected removePortal(portalId: string): void {
      const portalInfo = this.portals.get(portalId);
      if (portalInfo) {
         try {
            sharedReactRoot.removePortal(portalInfo.id);
         } catch (error) {
            console.warn(`Error removing portal ${portalInfo.id}:`, error);
         } finally {
            this.portals.delete(portalId);
         }
      }
   }

   /**
    * Update an existing portal with new component
    */
   protected updatePortal(
      portalId: string,
      component: React.ReactElement
   ): void {
      const portalInfo = this.portals.get(portalId);
      if (portalInfo) {
         // Remove old portal and create new one
         this.removePortal(portalId);
         this.createPortal(portalId, portalInfo.container, component);
      }
   }

   /**
    * Clean up all portals - called automatically in destroy()
    */
   protected cleanupPortals(): void {
      const portalIds = Array.from(this.portals.keys());

      for (const portalId of portalIds) {
         this.removePortal(portalId);
      }

      this.portals.clear();
   }

   /**
    * Create a DOM container with common styling
    */
   protected createContainer(
      className: string,
      parent?: HTMLElement
   ): HTMLElement {
      const container = document.createElement("div");

      // Handle space-separated class names properly
      const classNames = className
         .split(/\s+/)
         .filter((name) => name.length > 0);
      container.classList.add(...classNames);

      if (parent) {
         parent.appendChild(container);
      }

      return container;
   }

   /**
    * Handle Editor.js config nesting
    */
   protected parseConfig<T extends BaseBlockConfig>(
      config: T | { config: T }
   ): T {
      const configObj = config as unknown as Record<string, unknown>;
      return (configObj?.config as T) || (config as T);
   }

   // Abstract methods that subclasses must implement
   abstract render(): HTMLElement;
   abstract save(): unknown;

   /**
    * Static method to render preview component for this block type
    * Should be implemented by subclasses
    */
   static renderPreview?(props: BlockPreviewProps): React.ReactElement | null;

   /**
    * Creates a JSON markdown code block that preserves all block data including metadata
    * @param languageCode - The markdown language code (e.g., 'kontext-sql-block', 'kontext-chart-block')
    * @param blockData - The complete block data to serialize
    * @param blockId - The unique block ID
    * @param blockType - The block type (e.g., 'sql', 'chart')
    * @returns Markdown string with JSON data
    */

   /**
    * Parses a JSON markdown code block back into block data
    * @param markdownCode - The markdown code node
    * @param expectedLanguageCode - The expected language code
    * @param expectedBlockType - The expected block type
    * @returns Parsed block data or null if invalid
    */

   /**
    * Set the block ID from loaded data (called after constructor during block restoration)
    */
   public setBlockId(id: string): void {
      this.blockId = id;
   }

   /**
    * Get the block ID for serialization purposes
    */
   public getBlockId(): string {
      return this.blockId;
   }

   /**
    * Default destroy implementation that cleans up portals
    * Subclasses can override but should call super.destroy()
    */
   destroy(): void {
      this.cleanupPortals();
      this.wrapper = null;
   }
}
