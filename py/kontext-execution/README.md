# kontext-execution

Execution orchestration primitives for long-running Kontext work.

This package owns durable run lifecycle: `ExecutionRun` projection, job
scheduling, retries, cancellation, run status/events/log shaping, and worker
coordination contracts.

## What It Does Not Own

- concrete compute engines (see `kontext-engine`)
- query submission/session orchestration (see `kontext-query`)
- deployment-profile bootstrap (see `kontext-runtime`)

See [Python Package Boundaries](../../docs/development/python-package-boundaries.md)
for the execution-stack decision tree that distinguishes
`execution` / `engine` / `runtime`.
