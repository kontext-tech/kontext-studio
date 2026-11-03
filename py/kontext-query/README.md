# kontext-query

Query and session orchestration for Kontext.

This package owns query execution submission and query-session application
logic so that `kontext-api` remains a transport layer instead of the long-term
home for query workflows.

## What This Package Owns

- Query execution submission (`execute_query_sync` / `execute_query_async`)
- Query session lifecycle, reuse, and compatibility orchestration
- SQL validation, session storage, and session-scoped locking
- The in-process `IQuerySessionServiceProtocol` adapter
  (`InProcessQuerySessionService`) used by the local runtime profile

## Boundary Rule

`kontext-query` must **not** import `kontext-engine`. It resolves engines only
through the `QueryRuntimeProviderProtocol.get_query_execution_engine` port, so a
different engine (including a remote/cloud engine) can be supplied by the
runtime provider without changing query orchestration. The rule is enforced by
`py/kontext-common/tests/test_architecture_boundaries.py`.

Shared primitives that both this package and the engine adapter need
(session storage paths, compatibility predicates, execution locks, session
scope hydration) live in `kontext.common.query` — not here — precisely so the
dependency only ever points inward.
