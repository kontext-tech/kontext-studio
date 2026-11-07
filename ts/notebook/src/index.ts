// Main components
export { CustomMermaid } from "./components/mermaid";
export { default as NotebookEditor } from "./components/NotebookEditor";
export { default as NotebookPreview } from "./components/NotebookPreview";
export { CreateNotebookModal } from "./components/CreateNotebookModal";
export type { CreateNotebookModalProps } from "./components/CreateNotebookModal";
export { default as NotebookSessionsSidebarTab } from "./components/NotebookSessionsSidebarTab";
export type { NotebookSessionsSidebarTabProps } from "./components/NotebookSessionsSidebarTab";
export { default as NotebookSidebar } from "./components/NotebookSidebar";
export { default as NotebookViewer } from "./components/NotebookViewer";
export type { NotebookViewerProps } from "./components/NotebookViewer";

// Constants
export * from "./constants";

// Context providers
export {
   NotebookServiceProvider,
   useNotebookServices,
   type NotebookPersistenceResult
} from "./context/NotebookServiceContext";

// Hooks and stores for state management
export { useExecuteCell } from "./hooks/useExecuteCell";
export {
   useNotebookDataReference,
   useNotebookInlineData
} from "./hooks/useInlineData";
export {
   useNotebookFileHelpers,
   useNotebookFileWorkflow,
   type UseNotebookFileHelpersReturn
} from "./hooks/useNotebookFileHelpers";

export { useNotebookStore } from "./stores/notebookStore";

export type {
   CellExecutionContext,
   CellExecutionResult,
   CodeExecutionResult,
   CodeExecutionEngine,
   DataCatalogBinding,
   DataResolverBinding,
   FileSystemBinding
} from "./types/bindings";
export * from "./types/notebook";

// Utilities - Primary conversion API (modular system)
export {
   convertFromEditorJSFormat,
   convertToEditorJSFormat
} from "./utils/documentConverter";

// Styles
// Import the dark theme CSS in your app:
// import "@kontext-tech/notebook/styles/editorjs-dark-theme.css";
