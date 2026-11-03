---
name: verify-workspace
description: Per-package verification commands (tests, lint, typecheck, builds) for the pnpm/uv workspace - use before finishing any change or when unsure what to run
---

# Verify Workspace

Verify the smallest applicable scope, and state what you ran and did not run.

## Workspace level

```bash
pnpm run build:shared          # build shared TS packages in repo-defined order
pnpm run build                 # shared packages + app
pnpm lint                      # root ESLint
pnpm test:ts                   # all TS workspace tests
pnpm test:python               # Python workspace tests
pnpm typecheck:python          # pyright across py/*
pnpm run validate:workspace-graph
pnpm run validate:workspace-versions
```

Ruff covers Python style: `uv run ruff check --fix py && uv run ruff format py`.

## Frontend app

App-only changes verify with lint/type-check/build (no test script):

```bash
pnpm --filter @kontext-labs/app lint && pnpm --filter @kontext-labs/app type-check
pnpm --filter @kontext-labs/app build
```

Run `pnpm run build:shared` first when shared `ts/*` packages changed — the app
resolves many workspace packages from source, but some paths (notably notebook
typings/assets) depend on built outputs.

## TS packages with Jest tests

```bash
pnpm --filter @kontext-labs/schema test
pnpm --filter @kontext-labs/chart test
pnpm --filter @kontext-labs/notebook test
pnpm --filter @kontext-labs/chat test
pnpm --filter @kontext-labs/common test
```

Single file:

```bash
pnpm --filter @kontext-labs/schema test -- --runTestsByPath ts/schema/src/__tests__/core.test.ts
```

Schema-only contract checks: `pnpm --filter @kontext-labs/schema run check:contracts`
(needs `uv` for the API snapshot) or `check:contracts:ts` for the Node-only
subset.

## Python packages

```bash
uv run --package kontext-agentic pytest py/kontext-agentic/tests
uv run --package kontext-api pytest py/kontext-api/tests
uv run --package kontext-kernel pytest py/kontext-kernel/tests
uv run --package kontext-runtime pytest py/kontext-runtime/tests
uv run --package kontext-common pytest py/kontext-common/tests
```

Single test / file:

```bash
uv run --package kontext-agentic pytest py/kontext-agentic/tests/test_chat_handler.py::test_name
```

Pytest is configured at the workspace root. Slow tests run by default; filter
them with `-m "not slow"` when iterating, and use `-m "unit"` for the fast
subset.

## What to run for which change

| Change | Minimum verification |
| --- | --- |
| `py/kontext-common` protocols/DTOs | common + every dependent package suite (query, runtime, ai, api, ...) |
| engine resolution / query seams | query, engine, execution, job suites |
| runtime providers / profile | runtime suite + boundary tests |
| FastAPI routers | `kontext-api` suite; regenerate schema if the OpenAPI spec changes |
| `ts/schema` | schema contract checks + regen pipeline (see `.github/skills/contract-pipeline`) |
| app feature code | app lint + type-check + build |
| shared ts package | that package's jest tests + app type-check |
