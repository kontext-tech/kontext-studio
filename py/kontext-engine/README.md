# Kontext Engine

Concrete in-process compute implementations for Kontext.

## What This Package Owns

- DuckDB-backed query engines (`DuckDBQueryEngine`)
- Native live-SQL pushdown engines (`LiveSqlQueryEngine`)
- In-process chat and job-run adapters, and the in-process task dispatcher

The provider chosen at runtime is `LocalRuntimeProvider`, which lives in
`kontext-runtime` (this package no longer ships a provider class).

## What It Does Not Own

- deployment-profile bootstrap or provider selection (see `kontext-runtime`)
- query submission and session orchestration (see `kontext-query`)
- durable run lifecycle, retries, cancellation, and run projection
  (see `kontext-execution`)
- HTTP/SSE/WebSocket transport (see `kontext-api`)

## Dependencies

`kontext-engine` depends only on compute **contracts** plus `kontext-query`'s
engine-resolution seam (`resolve_engine_for_session`). It must **not** import
query orchestration internals: query resolves engines through the
`QueryRuntimeProviderProtocol.get_query_execution_engine` port, which keeps the
engine swappable (including for a future remote/cloud engine). The
`test_architecture_boundaries.py` suite enforces this.

## Related Packages

| Concern | Package |
| --- | --- |
| Chooses how a deployment is wired | `kontext-runtime` |
| Submits and tracks query sessions | `kontext-query` |
| Performs compute inside a Python process | `kontext-engine` (this package) |
| Tracks durable runs across transports and workers | `kontext-execution` |

See [Python Package Boundaries](../../docs/development/python-package-boundaries.md)
for the full responsibility matrix and the execution-stack decision tree.
