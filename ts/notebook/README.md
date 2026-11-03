# Kontext Notebook

Shared React notebook library for Kontext.

## What This Package Owns

- notebook editor and preview components
- Editor.js block registrations and rendering
- notebook state via `useNotebookStore`
- notebook host bindings through `NotebookServiceProvider`
- notebook conversion helpers and styles

## What It Does Not Own

- app-specific service construction
- route-level notebook loading and saving
- the local demo app

The standalone sample app now lives in `examples/notebook-demo`.

## Host Requirements

Render notebook UI inside:

- `QueryClientProvider` from `@tanstack/react-query`
- Ant Design `App`
- `NotebookServiceProvider`

Create a notebook store instance before mounting `NotebookEditor`.

## Minimal Integration

```tsx
import { App } from "antd";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
   NotebookEditor,
   NotebookServiceProvider,
   useNotebookStore,
   type NotebookDocument
} from "@kontext-tech/notebook";

const queryClient = new QueryClient();
const instanceId = "example-notebook";

useNotebookStore.getState().createInstance(instanceId, {
   document,
   isDarkMode: false,
   readonly: false
});

export function ExampleNotebook({ document }: { document: NotebookDocument }) {
   return (
      <QueryClientProvider client={queryClient}>
         <App>
            <NotebookServiceProvider
               fileSystem={fileSystem}
               executionEngine={executionEngine}
               projectId="project-id"
            >
               <NotebookEditor instanceId={instanceId} onSave={saveNotebook} />
            </NotebookServiceProvider>
         </App>
      </QueryClientProvider>
   );
}
```

## Development Commands

```bash
pnpm --filter @kontext-tech/notebook build
pnpm --filter @kontext-tech/notebook test
pnpm --filter @kontext-tech/notebook lint
pnpm --filter notebook-demo dev
```

Use the VS Code task `start: notebook demo` to launch the standalone demo app.
