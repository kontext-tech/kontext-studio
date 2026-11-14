# Kontext — Agent Guide

Canonical guide for every coding agent working in this repository
(opencode, Codex, Claude Code, Copilot, Cline, ...). This file is
self-sufficient for everyday work. Longer procedural workflows live in
`.github/skills/<name>/SKILL.md` and are loaded on demand when a task matches.

Tool-specific entry points are thin adapters with no unique content:

- GitHub Copilot: `.github/copilot-instructions.md`
- Cline: `.clinerules`
- Claude Code: `CLAUDE.md` (symlink to this file)
- `tools/validate-agent-docs.mjs` enforces that skills exist and adapters point here.

## Non-negotiables

- Use `pnpm` for Node/TypeScript and `uv` for Python. Never `npm`, `yarn`, or `pip`.
- Verify before finishing: run the affected package's tests, or its
  lint/typecheck/build when it has no tests. State what you ran and did not run.
- If you add, rename, or remove an environment variable, update
  `docs/development/environment.md` and run `pnpm run validate:env-docs`.
- Never hand-edit a package version. All `ts/*` packages plus Python packages
  and the root `package.json` share one lockstep version owned by
  `[tool.commitizen]` in `pyproject.toml`; bump with `pnpm run version:studio`.
- Follow Conventional Commits (see `.github/skills/commit-message`).
- Shared TS packages must not import app-local modules. The `@/` alias is for
  `app/src` only; packages under `ts/` import each other via `@kontext-tech/*`.
- Feature placement: workspace packages own state, services, and domain
  components; `app/` owns screens, routing, and composition. Do not move
  screens into packages or business rules into `app/`; import packages through
  their public entry points, never `@kontext-tech/*/src/...`.
- Python distributions must declare exactly the workspace packages their source
  imports (`py/kontext-common/tests/test_dependency_metadata.py` enforces this;
  only `kontext-api`, `kontext-runtime`, and `kontext-studio` may pin unimported
  packages as composition roots).
- Keep `package.json` deps and `tsconfig.json` project references aligned inside
  `ts/*` (`tools/validate-workspace-graph.mjs` fails otherwise).

## Package managers and setup

- Node engines: `node >=22.23.4`, `pnpm >=10.0.0`.

```bash
pnpm install
uv sync
uv sync --group codegen   # only needed to regenerate the committed models
```

- The generated TypeScript API types (`ts/schema/src/generated/api.ts`) and the Pydantic models
  (`py/kontext-schema`) are committed source. Regeneration is a
  pipeline — see `.github/skills/contract-pipeline`.

## Build, test, and lint

```bash
pnpm run build:shared      # build shared TS packages in repo-defined order
pnpm run build             # shared packages + app
pnpm lint                  # root ESLint
pnpm test:ts               # all TS workspace tests
pnpm test:python           # Python workspace tests
pnpm typecheck:python      # pyright across py/*
pnpm run validate:workspace-graph
pnpm run validate:workspace-versions
```

App only: `pnpm --filter @kontext-tech/app {dev,build,lint,type-check}`
(no dedicated app test script).

Python suites (pytest configured at the workspace root; markers like
`-m "not slow"` / `-m "unit"` work):

```bash
uv run --package kontext-agentic pytest py/kontext-agentic/tests
uv run --package kontext-api pytest py/kontext-api/tests
uv run --package kontext-runtime pytest py/kontext-runtime/tests
```

For single test files, package-specific checks, and the full per-package
verification matrix, see `.github/skills/verify-workspace`.

## High-level architecture

A system map (processes, layers, data flow, and technology) lives in
[`docs/development/architecture.md`](docs/development/architecture.md).

- `app/` is the React + Vite frontend. `app/src/app/bootstrap.tsx` composes
  `QueryClientProvider` + `ThemeProvider` + `PermissionProvider` + `RouterProvider`.
  Routing is metadata-driven: start from `app/src/routing/routes.ts`.
- `ts/` holds shared workspace packages. `ts/schema` is the contract hub
  (Zod-first source of truth + committed OpenAPI specs); changes there cascade
  into the generated API types and Pydantic models (see `.github/skills/contract-pipeline`).
- `py/kontext-api` is the unified FastAPI backend. `py/kontext-studio` is the
  local server/CLI composition root reusing the same routers.
- Python layering: `kontext-common` is the leaf contract layer (imports only
  `kontext-schema`); `kontext-query` orchestrates engines only through the
  `QueryRuntimeProviderProtocol` port; `kontext-engine` is compute and never
  imports query/catalog; `kontext-kernel` is the separate-process Python
  topology and depends only on common; `kontext-runtime` + `kontext-studio` are
  the composition roots. The import graph is acyclic and enforced by
  `py/kontext-common/tests/test_architecture_boundaries.py`
  (see `.github/skills/python-boundaries`).
- Agent-stack layering: `kontext-agent` is the framework-agnostic contract
  layer and harness SPI (`AgentSpec`, `AgentKind`, `AgentCreationContext`,
  `AgentFrameworkAdapter`, tool metadata, session state, run-state port; deps
  are `kontext-common` + `kontext-schema`);
  `kontext-agentic` is the application layer (blueprints, blueprint registry,
  chat handling, domain tools); `kontext-harness-agno` is the pluggable adapter
  dist discovered through the `kontext.agent_harnesses` entry-point group.
  Harness dists are plugins, not layers — they import `kontext-agent`, never
  `kontext-agentic`/`kontext-data`, and the app never imports one statically.
- `py/kontext-runtime` selects the deployment profile (local-first; cloud is a
  documented extension point behind the seams, see
  `.github/skills/runtime-composition`).

## Key conventions

- When a DI contract interface would clash with its implementing class, suffix
  the interface with `Contract` in TS (`FileServiceContract` / `FileService`).
  Python uses `*Protocol` classes in `kontext-common/protocols` instead.
- In Python runtime code, `local` refers to the deployment profile while
  `inprocess` refers to execution topology. Related, not interchangeable.
- API contract conventions: both FastAPI entrypoints call
  `configure_camel_case_params(app)`, local and cloud share router prefixes,
  and `KontextError` / JWT failures surface as structured HTTP errors.
- Search for contract imports with word boundaries: `rg -w kontext.agent` (or
  the pattern `kontext\.agent\b`). A fixed-string search for `kontext.agent`
  also matches `kontext.agentic.*` lines; the longer name never collides.
- Internal cross-package DTOs (e.g. `QueryEngineRequest`, `PythonRunnerResult`)
  live in `kontext-common`; wire payloads live in the `ts/schema` pipeline.
  Crossing the HTTP boundary is the trigger to add a type to the schema hub.
- Documentation architecture and flow diagrams use fenced `mermaid` blocks, not
  ASCII art. Step-by-step procedures stay as numbered prose. The docs site
  renders Mermaid with `astro-mermaid`; keep directory trees and literal
  command output in `text` blocks.

## Skills

Load on demand when a task matches:

- `.github/skills/commit-message` — Conventional Commits + auto-commit workflow
- `.github/skills/contract-pipeline` — schema/OpenAPI source-of-truth loop and type/model regeneration
- `.github/skills/python-boundaries` — packaging layer rules and the boundary-test harness
- `.github/skills/verify-workspace` — per-package verification matrix (tests, lint, typecheck)
- `.github/skills/runtime-composition` — runtime provider/protocol/profile composition conventions
