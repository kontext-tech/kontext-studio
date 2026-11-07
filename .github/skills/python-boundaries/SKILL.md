---
name: python-boundaries
description: Python package layering rules and the architecture boundary tests - use when importing across py/* packages, adding a package, or touching py/kontext-common tests/test_architecture_boundaries.py
---

# Python Package Boundaries

The `py/*` import graph is a strictly layered, acyclic dependency tree enforced
by an AST-based test:
`py/kontext-common/tests/test_architecture_boundaries.py`.

> The full package responsibility matrix and per-package guidance live in
> `docs/development/python-package-boundaries.md`; this skill is the enforced
> layer map and the operational rules.

## Layer map

| Package | Role | May depend on |
| --- | --- | --- |
| `kontext-common` | leaf contract layer (protocols + internal DTOs) | `kontext-schema` only (whitelist) |
| `kontext-kernel` | separate-process Python execution topology | `kontext-common` only |
| `kontext-engine` | query compute (DuckDB, live SQL) | never `query`/`catalog` |
| `kontext-query` | query orchestration | resolves engines only via `QueryRuntimeProviderProtocol` |
| `kontext-execution` | job definitions + run orchestration | never `query`/`engine` |
| `kontext-llm` | model resolution | never `runtime`/`account` |
| `kontext-harness-agno` | Agno adapter plugin | `agent`/`common`/`llm`/`schema` + `agno`; never `agentic`/`data` |
| `kontext-okf` | knowledge format | never `catalog` |
| `kontext-runtime`, `kontext-studio` | composition roots | may wire everything |

Additional rules:

- Harness SDKs (`agno`, `google.adk`, `google.genai`) may only be imported in
  `py/kontext-harness-agno/src/kontext/harness/agno/`.
- `@job` definitions (six registered job-definition directories) must not
  import `kontext.data`; worker-portable code reaches the platform only through
  JobContext / provider ports.
- Kernel imports outside the composition layers are shrink-only-allowlisted;
  the single sanctioned seam is the lazy, process-local
  `terminate_running_kernel` in `py/kontext-execution/src/kontext/execution/runs.py`.

## Shrink-only allowlists

Transitional exceptions are named constant lists (e.g.
`KNOWN_JOB_DATA_OFFENDERS`, `KNOWN_EXTERNAL_KERNEL_OFFENDERS`) next to each
test. They may only ever shrink: migrate the import behind a port, then delete
the entry. Both **unexpected offenders** and **stale allowlist entries** fail
the test, so cleanup is enforced in both directions.

## When adding a package

1. Add the module→package mapping in `TOP_LEVEL_MODULE_TO_PACKAGE` in the
   boundary test.
2. Ensure `py/kontext-common/tests/test_architecture_boundaries.py` stays green
   plus `pnpm run validate:workspace-graph` / `validate:workspace-versions`.
3. Justify any new cross-package import against the layer map; add a whitelist
   entry (test-asserted) rather than leaving the edge silent.

## Run

```bash
uv run --package kontext-common pytest py/kontext-common/tests/test_architecture_boundaries.py -q
```
