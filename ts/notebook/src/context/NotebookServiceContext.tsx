import React, {
   createContext,
   useContext,
   useMemo,
   type ReactNode
} from "react";
import type {
   CodeExecutionEngine,
   DataCatalogBinding,
   DataResolverBinding,
   FileSystemBinding
} from "../types/bindings";

/**
 * Context value containing all services needed by notebook components
 */
export interface NotebookServiceContextValue {
   projectId?: string;
   projectCode?: string;
   notebookId?: string;
   onViewExecutionRun?: (runId: string) => void;
   persistCurrentNotebook?: () => Promise<NotebookPersistenceResult>;
   fileSystem?: FileSystemBinding;
   executionEngine?: CodeExecutionEngine;
   dataCatalog?: DataCatalogBinding;
   dataResolver?: DataResolverBinding;
}

export interface NotebookPersistenceResult {
   success: boolean;
   error?: string;
}

const NotebookServiceContext =
   createContext<NotebookServiceContextValue | null>(null);

/**
 * The notebook service context. Exposed so the shared React root can provide
 * the context value directly (a stable provider element type) instead of
 * wrapping portals in a provider component whose identity may change between
 * renders and force React to remount every mounted block.
 */
export { NotebookServiceContext };

/**
 * Hook to access notebook service bindings.
 *
 * @example
 * ```tsx
 * const { fileSystem } = useNotebookServices();
 * const data = await fileSystem?.getInlineData?.(fileId);
 * ```
 */
export function useNotebookServices(): NotebookServiceContextValue {
   const context = useContext(NotebookServiceContext);
   return context ?? {};
}

interface NotebookServiceProviderProps {
   children: ReactNode;
   projectId?: string;
   projectCode?: string;
   notebookId?: string;
   onViewExecutionRun?: (runId: string) => void;
   persistCurrentNotebook?: () => Promise<NotebookPersistenceResult>;
   fileSystem?: FileSystemBinding;
   executionEngine?: CodeExecutionEngine;
   dataCatalog?: DataCatalogBinding;
   dataResolver?: DataResolverBinding;
}

/**
 * Provider for notebook host bindings.
 *
 * @example Demo with mock bindings:
 * ```tsx
 * <NotebookServiceProvider
 *    fileSystem={mockFileSystem}
 *    executionEngine={mockExecutionEngine}
 * >
 *    <NotebookEditor />
 * </NotebookServiceProvider>
 * ```
 */
export const NotebookServiceProvider: React.FC<
   NotebookServiceProviderProps
> = ({
   children,
   projectId,
   projectCode,
   notebookId,
   onViewExecutionRun,
   persistCurrentNotebook,
   fileSystem,
   executionEngine,
   dataCatalog,
   dataResolver
}) => {
   const contextValue = useMemo(
      () => ({
         projectId,
         projectCode,
         notebookId,
         onViewExecutionRun,
         persistCurrentNotebook,
         fileSystem,
         executionEngine,
         dataCatalog,
         dataResolver
      }),
      [
         projectId,
         projectCode,
         notebookId,
         onViewExecutionRun,
         persistCurrentNotebook,
         fileSystem,
         executionEngine,
         dataCatalog,
         dataResolver
      ]
   );

   return (
      <NotebookServiceContext.Provider value={contextValue}>
         {children}
      </NotebookServiceContext.Provider>
   );
};
