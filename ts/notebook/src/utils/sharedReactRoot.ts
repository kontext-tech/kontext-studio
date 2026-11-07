import { logger } from "@kontext-tech/common";
import { ThemeContext, type ThemeContextProps } from "@kontext-tech/theme";
import { ConfigProvider } from "antd";
import React from "react";
import { createPortal } from "react-dom";
import { createRoot, type Root } from "react-dom/client";
import BlockErrorBoundary from "../components/ErrorBoundary";
import {
   NotebookServiceContext,
   type NotebookServiceContextValue
} from "../context/NotebookServiceContext";

interface ProviderConfig {
   configProvider?: React.ComponentProps<typeof ConfigProvider>;
   themeProvider?: React.ComponentType<{ children: React.ReactNode }>;
   themeContextValue?: ThemeContextProps;
   queryClientProvider?: React.ComponentType<{ children: React.ReactNode }>;
   /**
    * Notebook service bindings provided to every block portal.
    *
    * This is a context VALUE rather than a provider component on purpose: the
    * provider element type stays stable across renders, so changing bindings
    * re-renders mounted blocks without unmounting/remounting them. Passing a
    * provider component whose identity changes (e.g. a `useCallback` wrapper)
    * makes React treat each render as a different component type and remount
    * every chart/SQL block in the notebook.
    */
   notebookServiceValue?: NotebookServiceContextValue;
}

/**
 * Shared React root manager for EditorJS blocks
 * This allows blocks to render React components efficiently.
 * Since we're using Zustand stores, blocks can access state directly
 * without needing context to be passed through the portal system.
 *
 * The root is a single-active-owner resource: exactly one NotebookEditor
 * owns it at a time (the artifacts UI mounts one notebook at a time via
 * `destroyOnHidden`). Lifecycle calls carry the owner id so a stale owner
 * cannot update providers for, or tear down, a root that a newer editor
 * already owns.
 */
class SharedReactRootManager {
   private root: Root | null = null;
   private container: HTMLElement | null = null;
   private portals: Map<string, React.ReactElement> = new Map();
   private renderScheduled = false;
   private isDestroying = false;
   private isInitialized = false;
   private providers: ProviderConfig = {};
   private activeOwner: string | null = null;

   private log(message: string, ...args: unknown[]): void {
      if (process.env.NODE_ENV === "development") {
         logger.debug(`[SharedReactRoot] ${message}`, ...args);
      }
   }

   private warn(message: string, ...args: unknown[]): void {
      if (process.env.NODE_ENV === "development") {
         console.warn(`[SharedReactRoot] ${message}`, ...args);
      }
   }

   private error(message: string, ...args: unknown[]): void {
      console.error(`[SharedReactRoot] ${message}`, ...args);
   }

   /**
    * Update providers without reinitializing the root.
    *
    * Ignored when called by a non-owner so a stale editor cannot repoint the
    * active root's services or theme.
    *
    * @param ownerId - Identifier of the NotebookEditor instance.
    * @param providers - Provider configuration for theming and configuration
    */
   updateProviders(ownerId: string, providers: ProviderConfig): void {
      if (this.activeOwner !== null && this.activeOwner !== ownerId) {
         this.warn(
            `Ignoring provider update from ${ownerId}; owner is ${this.activeOwner}`
         );
         return;
      }

      this.log("Updating providers");
      this.providers = providers;
      this.log("Providers updated:", Object.keys(providers));

      // Re-render with new providers if initialized
      if (this.isInitialized && !this.isDestroying) {
         this.scheduleRender();
      }
   }

   /**
    * Initialize the shared root for an owning NotebookEditor instance.
    *
    * @param ownerId - Identifier of the NotebookEditor instance.
    * @param providers - Optional provider configuration for theming and configuration
    */
   initialize(ownerId: string, providers?: ProviderConfig): void {
      this.log("Initializing shared React root for", ownerId);

      // If already initialized by this owner, only refresh providers. (Doing
      // this before the cleanup path matters: the cleanup path resets
      // providers, so assigning providers earlier would be wiped.)
      if (
         this.isInitialized &&
         this.root &&
         !this.isDestroying &&
         this.activeOwner === ownerId
      ) {
         if (providers) {
            this.providers = providers;
            this.log("Already initialized; providers refreshed");
            this.scheduleRender();
         } else {
            this.log("Already initialized");
         }
         return;
      }

      // A different owner is active; take the root over cleanly.
      if (this.activeOwner !== null && this.activeOwner !== ownerId) {
         this.warn(
            `Taking over shared React root from ${this.activeOwner} for ${ownerId}`
         );
      }

      // If destroying or has existing resources, clean up first. `forceCleanup`
      // resets `this.providers`, so providers are assigned AFTER it below.
      if (this.isDestroying || this.root || this.container) {
         this.log("Forcing cleanup before initialization");
         this.forceCleanup();
      }

      // Set up new state (after cleanup so providers are not wiped)
      this.isDestroying = false;
      this.isInitialized = true;
      this.activeOwner = ownerId;
      if (providers) {
         this.providers = providers;
         this.log("Providers configured:", Object.keys(providers));
      }

      // Create a new container and root
      try {
         // Create a hidden container for the shared root
         this.container = document.createElement("div");
         this.container.id = "notebook-shared-react-root";
         this.container.style.cssText = `
            position: absolute;
            top: -9999px;
            left: -9999px;
            visibility: hidden;
            pointer-events: none;
         `;
         document.body.appendChild(this.container);

         this.root = createRoot(this.container);
         this.log("Shared React root created successfully");

         // Initial render with empty portals
         this.scheduleRender();
      } catch (error) {
         this.error("Error creating shared React root:", error);
         this.isInitialized = false;
      }
   }

   /**
    * Create a portal for a block component
    */
   createPortal(
      blockId: string,
      targetContainer: HTMLElement,
      component: React.ReactElement
   ): boolean {
      if (!this.isInitialized) {
         console.warn(`Cannot create portal for ${blockId} - not initialized`);
         return false;
      }

      if (this.isDestroying) {
         console.warn(`Cannot create portal for ${blockId} - destroying`);
         return false;
      }

      try {
         // Remove existing portal if it exists
         if (this.portals.has(blockId)) {
            this.log(`Replacing existing portal for ${blockId}`);
            this.portals.delete(blockId);
         }

         // Wrap the component with error boundary for individual block error handling
         const wrappedComponent = React.createElement(BlockErrorBoundary, {
            blockId,
            blockType: "block" as const,
            showDetails: process.env.NODE_ENV === "development",
            onRetry: () => {
               this.log(`Error boundary retry triggered for block ${blockId}`);
               // Optionally, you could trigger a re-render of just this block
               // For now, just log the retry
            },
            children: component
         });

         // Create portal that renders the wrapped component into the target container
         const portal = createPortal(wrappedComponent, targetContainer);
         this.portals.set(blockId, portal);
         this.log(`Portal with error boundary created for ${blockId}`);
         this.scheduleRender();
         return true;
      } catch (error) {
         console.error(`Error creating portal for ${blockId}:`, error);
         return false;
      }
   }

   /**
    * Remove a portal when block is destroyed
    */
   removePortal(blockId: string): boolean {
      if (!this.isInitialized) {
         return false;
      }

      if (this.isDestroying) {
         logger.debug(
            `Ignoring removePortal for ${blockId} during destruction`
         );
         return false;
      }

      if (this.portals.has(blockId)) {
         logger.debug(`Removing portal ${blockId}`);
         this.portals.delete(blockId);
         this.scheduleRender();
         return true;
      }

      return false;
   }

   /**
    * Check if a portal exists
    */
   hasPortal(blockId: string): boolean {
      return this.portals.has(blockId);
   }

   /**
    * Get portal count (for debugging)
    */
   getPortalCount(): number {
      return this.portals.size;
   }

   /**
    * Get status information
    */
   getStatus() {
      return {
         isInitialized: this.isInitialized,
         isDestroying: this.isDestroying,
         hasContainer: !!this.container,
         portalCount: this.portals.size,
         containerInDOM: this.container
            ? document.body.contains(this.container)
            : false
      };
   }

   /**
    * Schedule a render (debounced to avoid excessive renders)
    */
   private scheduleRender(): void {
      if (this.renderScheduled || !this.isInitialized || this.isDestroying) {
         return;
      }

      this.renderScheduled = true;
      requestAnimationFrame(() => {
         this.renderScheduled = false;

         if (!this.isInitialized || this.isDestroying) {
            return;
         }

         try {
            this.render();
         } catch (error) {
            console.error("Error during scheduled render:", error);
         }
      });
   }

   /**
    * Render all portals
    * Wraps portals with configured providers for theming and configuration
    */
   private render(): void {
      if (!this.root || !this.isInitialized || this.isDestroying) {
         this.warn("Cannot render - root not ready or destroying");
         return;
      }

      try {
         const portalValues = Array.from(this.portals.values());

         this.log(`Rendering ${portalValues.length} portals`);

         // Just ensure portals are not null/undefined
         const validPortals = portalValues.filter((portal) => portal != null);

         if (validPortals.length !== portalValues.length) {
            this.warn(
               `Filtered out ${
                  portalValues.length - validPortals.length
               } null/undefined portals`
            );
         }

         // Create wrapper with configured providers
         // Start with the portals
         const portalsDiv = React.createElement("div", {}, ...validPortals);

         // Apply ThemeProvider if provided
         let wrappedContent: React.ReactElement = portalsDiv;

         // Prefer passing the context value directly to ensure state sync with main app
         if (this.providers.themeContextValue) {
            wrappedContent = React.createElement(ThemeContext.Provider, {
               value: this.providers.themeContextValue,
               children: wrappedContent
            });
         } else if (this.providers.themeProvider) {
            const ThemeProvider = this.providers.themeProvider;
            wrappedContent = React.createElement(ThemeProvider, {
               children: wrappedContent
            });
         }

         // Apply QueryClientProvider if provided (needed for React Query hooks)
         if (this.providers.queryClientProvider) {
            const QueryClientProvider = this.providers.queryClientProvider;
            wrappedContent = React.createElement(QueryClientProvider, {
               children: wrappedContent
            });
         }

         // Apply the notebook service context if provided (needed for
         // resource/session bindings). The context provider element type is
         // stable, so binding updates re-render blocks without remounting.
         if (this.providers.notebookServiceValue) {
            wrappedContent = React.createElement(
               NotebookServiceContext.Provider,
               {
                  value: this.providers.notebookServiceValue,
                  children: wrappedContent
               }
            );
         }

         // Apply ConfigProvider (either custom or default)
         const configProviderProps = this.providers.configProvider || {
            getPopupContainer: () => document.body
         };

         const PortalsWrapper = React.createElement(
            ConfigProvider,
            configProviderProps,
            wrappedContent
         );

         this.root.render(PortalsWrapper);
      } catch (error) {
         console.error("Error rendering shared React root:", error);

         // Simple recovery: clear problematic portals and try again
         if (this.portals.size > 0) {
            logger.debug("Attempting recovery by clearing problematic portals");
            this.portals.clear();

            // Try a minimal render to keep the root stable
            try {
               const configProviderProps = this.providers.configProvider || {
                  getPopupContainer: () => document.body
               };

               const EmptyWrapper = React.createElement(
                  ConfigProvider,
                  configProviderProps,
                  React.createElement("div", {})
               );
               this.root.render(EmptyWrapper);
            } catch (recoveryError) {
               console.error("Recovery render also failed:", recoveryError);
            }
         }
      }
   }

   /**
    * Force immediate cleanup (used during reinitialization)
    */
   private forceCleanup(): void {
      logger.debug("Forcing shared React root cleanup");

      // Set flags first
      const wasInitialized = this.isInitialized;
      this.isInitialized = false;
      this.isDestroying = true;
      this.activeOwner = null;

      // Clear all data structures
      this.portals.clear();
      this.renderScheduled = false;
      this.providers = {};

      // Clean up React root
      if (this.root) {
         try {
            this.root.unmount();
         } catch (error) {
            console.error("Error unmounting root:", error);
         }
         this.root = null;
      }

      // Clean up DOM container
      if (this.container) {
         try {
            if (document.body.contains(this.container)) {
               document.body.removeChild(this.container);
            }
         } catch (error) {
            console.error("Error removing container:", error);
         }
         this.container = null;
      }

      // Reset flags
      this.isDestroying = false;

      if (wasInitialized) {
         logger.debug("Forced cleanup completed");
      }
   }

   /**
    * Clean up the shared root.
    *
    * Ignored when called by a non-owner so a stale editor's teardown cannot
    * clear portals that the current owner is still rendering.
    *
    * @param ownerId - Identifier of the NotebookEditor instance.
    */
   destroy(ownerId: string): void {
      if (this.activeOwner !== null && this.activeOwner !== ownerId) {
         this.warn(
            `Ignoring destroy from ${ownerId}; owner is ${this.activeOwner}`
         );
         return;
      }

      if (!this.isInitialized) {
         logger.debug("Nothing to destroy - not initialized");
         return;
      }

      if (this.isDestroying) {
         console.warn("Already destroying, ignoring duplicate destroy call");
         return;
      }

      logger.debug("Starting shared React root destruction");
      this.isDestroying = true;
      this.isInitialized = false;
      this.activeOwner = null;

      // Clear references immediately
      this.portals.clear();
      this.renderScheduled = false;

      if (this.root && this.container) {
         const rootToUnmount = this.root;
         const containerToRemove = this.container;

         // Clear references immediately
         this.root = null;
         this.container = null;

         // Schedule unmount asynchronously to avoid race conditions
         setTimeout(() => {
            try {
               rootToUnmount.unmount();
               logger.debug("React root unmounted successfully");
            } catch (error) {
               console.warn("Error unmounting React root:", error);
            }

            try {
               if (
                  containerToRemove &&
                  document.body.contains(containerToRemove)
               ) {
                  document.body.removeChild(containerToRemove);
                  logger.debug("Container removed from DOM");
               }
            } catch (error) {
               console.warn("Error removing container from DOM:", error);
            }

            // Reset the destroying flag after cleanup is complete
            this.isDestroying = false;
            logger.debug("Shared React root destruction completed");
         }, 0);
      } else {
         // If no root/container, just reset the flag
         this.isDestroying = false;
         logger.debug("No root/container to destroy");
      }
   }
}

// Export singleton instance
export const sharedReactRoot = new SharedReactRootManager();
