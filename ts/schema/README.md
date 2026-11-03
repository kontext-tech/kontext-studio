# @kontext-tech/schema

Shared domain schemas for Kontext, authored Zod-first and consumed across
TypeScript and Python, including the generated TypeScript API types.

## Overview

This package is the single source of truth for shared Kontext domain contracts.
Schemas are hand-authored as Zod schemas under `src/` and exported directly;
OpenAPI/Pydantic artifacts are generated from them.

## What's Included

- **Core domains** (`src/core/domains/`): hand-authored contracts for identity,
  projects, jobs, events, knowledge, notifications, infrastructure, tokens, and
  base primitives.
- **Data lake** (`src/data-lake/`): catalog discovery, files and file models, and
  query sessions/execution.
- **Charts** (`src/charts/`): 13 chart configuration types via the
  `CHART_SCHEMAS` registry (`line`, `bar`, `column`, `area`, `pie`, `scatter`,
  `dualAxes`, `funnel`, `heatmap`, `histogram`, `box`, `radar`, `stock`) plus the
  unified `ChartSpec`.
- **Notebook** (`src/notebook/`): notebook document schema and the block
  registry (`paragraph`, `header`, `list`, `code`, `quote`, `table`, `delimiter`,
  `image`, `imagePicker`, `sql`, `mermaid`, `chart`).
- **AI** (`src/ai/`): agents, chat sessions/streaming, workflows, and
  tool results.
- **Base** (`src/base.ts`): column data types, tabular data, and validation
  error shapes.

## Importing in TypeScript

```ts
// Core domain schemas
import { ProjectModelSchema, CreateProjectRequestSchema } from "@kontext-tech/schema";

// Tabular primitives
import { DataTableSchema, DataColumnSchema } from "@kontext-tech/schema";

// Chart schemas
import { ChartConfigSchema, CHART_SCHEMAS, getAllChartTypes } from "@kontext-tech/schema";

// Notebook schemas
import { NotebookDocumentSchema, NotebookBlockSchema, SqlBlockSchema } from "@kontext-tech/schema";

// Type inference
import type { NotebookDocument, ChartConfig, DataTable, ProjectModel } from "@kontext-tech/schema";
```

The committed OpenAPI specs are also exported as subpaths:

- `@kontext-tech/schema/specs/core` → `kontext.api.core.openapi.json`
- `@kontext-tech/schema/specs/api` → `kontext.api.openapi.json`

## Scripts

All scripts run from this package (`pnpm --filter @kontext-tech/schema run <script>`).

### Refresh the OpenAPI specs

```bash
pnpm run refresh-schemas
```

Exports the Zod schemas to OpenAPI 3.0 and writes
`src/schemas/kontext.models.openapi.json`.

### Generate Pydantic models

```bash
pnpm run generate:models
```

Runs the Zod-first export and then `datamodel-codegen` (Pydantic v2) to produce
the models in `py/kontext-schema/`. Use the root alias
`pnpm run generate:models` to run this from the repository root. The generator
is pinned in the root `uv.lock` under the `codegen` dependency group.

### Contract checks

```bash
pnpm run check:contracts        # schema snapshot + OpenAPI + contract parity
pnpm run check:generator-smoke  # validates generated types/models
```

## Package Architecture

```text
@kontext-tech/schema (Zod-first source of truth)
├── src/
│   ├── core/                 # Hand-authored core domains + primitives
│   │   ├── domains/          # identity, projects, jobs, events, ...
│   │   ├── data.ts           # DataTable / DataColumn
│   │   ├── health.ts
│   │   └── primitives.ts
│   ├── data-lake/            # catalog discovery, files, query execution
│   ├── charts/               # ChartType registry + ChartSpec
│   ├── notebook/             # document + block registry
│   ├── ai/                   # agents, chat, streaming, tool results
│   └── base.ts               # column data types, validation errors
├── scripts/                  # export, model-gen, and contract-check tooling
└── src/schemas/              # committed generated OpenAPI specs
    ├── kontext.models.openapi.json
    ├── kontext.api.openapi.json
    └── kontext.api.core.openapi.json
```

## Dependencies

- `zod` — schema authoring and validation.

## Development Guidelines

### Schema changes

1. Edit the Zod schemas under `src/`.
2. Build: `pnpm run build`.
3. Refresh the specs: `pnpm run refresh-schemas`.
4. Regenerate Pydantic models and TypeScript API types via the root
   `pnpm run generate:models` and `pnpm run generate:api-types`.
5. Run `pnpm run check:contracts`.

### Best practices

- Write comprehensive descriptions for better generated docs.
- Use discriminated unions for polymorphic types.
- Prefer additive changes; version the OpenAPI `$id`/`version` for breaking
  changes.
- Keep Zod as the authoring layer; treat generated output as derived.
