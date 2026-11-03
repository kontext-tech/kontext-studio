# Notebook System

The notebook system is a block-based document model for markdown, SQL, and
Python blocks with embedded query results and charts. This page is a short
orientation; the implementation lives in `ts/notebook` and the demo host in
`examples/notebook-demo`.

## Document Model

A notebook is a JSON document with an ordered array of blocks. Blocks carry a
`type` and a typed `data` payload. The block registry in
`ts/schema/src/notebook/registry.ts` is the source of truth; the supported types
are `paragraph`, `header`, `list`, `code`, `quote`, `table`, `delimiter`,
`image`, `imagePicker`, `sql`, `mermaid`, and `chart`.

Canonical types are defined in `@kontext-tech/schema` and re-exported by
`ts/notebook`; treat the schema package as the source of truth rather than
duplicating shapes here.

## Package Layout (`ts/notebook`)

- `components/` — editor and preview blocks, including `NotebookEditor`.
- `context/NotebookServiceContext.tsx` — host bindings
  (`NotebookServiceProvider`): file system and execution engine.
- `stores/notebookStore.ts` — notebook state via **zustand**
  (`useNotebookStore`).
- Code editing uses **CodeMirror** (`@uiw/react-codemirror` + `@codemirror/*`).

Notebook UI is not self-sufficient: the host app provides React Query, Ant
Design `App`, a notebook store instance, and a `NotebookServiceProvider`. See
`ts/notebook/README.md` for the integration contract.

## Execution

SQL and Python execution are host responsibilities. The notebook calls into the
injected execution engine; results are persisted back into blocks. There is no
notebook-owned backend endpoint — query execution goes through the standard
`kontext-api` routers (`POST /query/execute`, session and file routes).

## Running the Demo

```bash
pnpm run build:shared
pnpm run dev:notebook
```

See `examples/notebook-demo/README.md`.
