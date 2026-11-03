# Kontext Notebook Demo

Standalone sample app for the shared notebook library. It is an unpublished
(`private`) workspace package under `examples/`, not a distributed artifact.

## Commands

```bash
pnpm --filter notebook-demo dev
pnpm --filter notebook-demo build
```

The demo runs on `http://localhost:3000` and imports the notebook library
directly from the monorepo source tree (see the aliases in `vite.config.ts`).
