# Python Package Boundaries

> The *enforced* layer map lives in
> `.github/skills/python-boundaries/SKILL.md` (operational rules, allowlists,
> and the AST boundary test); this document is the full package responsibility
> matrix and workflow guidance. Keep them in sync when a rule changes.

## Boundary Model

The Python workspace follows a domain-oriented split with four important cross-cutting layers:

- `kontext-runtime`: deployment composition and startup/bootstrap
- `kontext-kernel`: the separate-process execution topology for Python jobs
- `kontext-engine`: concrete in-process query compute implementations
- `kontext-execution`: durable orchestration for long-running work

Those layers are complementary, not competing:

- `runtime` chooses how a deployment is wired
- `kernel` runs Python jobs in an isolated child process (portable across profiles)
- `engine` performs query compute inside a Python process
- `execution` tracks and coordinates durable runs across transports and workers

## Package Responsibility Matrix

| Package | Primary responsibility | Should contain | Should not contain |
| --- | --- | --- | --- |
| `kontext-common` | Shared contracts and primitives | Protocols, enums, config helpers, shared runtime contracts (`contracts/`), Pydantic bases (`pydantic.py`) | ORM services, FastAPI routers, DuckDB code, harness integration |
| `kontext-auth` | Authentication and authorization | Auth managers, JWT validation, permissions, secret handling | Project/file/query domain logic |
| `kontext-data` | Relational persistence | SQLAlchemy models, migrations, engine/session factory, repository-style data services, SQLite adapter | FastAPI transport logic, domain orchestration, query execution engines |
| `kontext-storage` | Blob/file storage providers | Storage provider factories, filesystem/blob adapters, storage config | Relational models, API routers |
| `kontext-file` | File, chart, and notebook domain logic | File services, notebook/chart editing, file-owned jobs | Generic query orchestration, auth concerns |
| `kontext-project` | Project domain logic | Project services, project stats/events, project-owned jobs | Shared auth/config primitives |
| `kontext-query` | Query sessions and query orchestration | Query submission, session services, SQL validation, session storage, the in-process query-session adapter | FastAPI routing, generic auth, importing `kontext-engine` |
| `kontext-job` | Job framework and job registry | Job contracts, job context, scheduling, registry, job execution service | Central home for every domain-specific job definition |
| `kontext-execution` | Durable long-running run orchestration | `ExecutionRun` projection/services, events/log shaping, run lifecycle helpers, worker coordination contracts | Concrete DuckDB engines, API bootstrap |
| `kontext-engine` | In-process compute implementations | DuckDB engines, live-SQL engine, in-process chat/job adapters, in-process dispatchers | Deployment bootstrap, API transport, importing `kontext-query`/`kontext-catalog` |
| `kontext-kernel` | Separate-process Python execution topology | Execution contracts, validation policy, child harness, wire protocol, kernel manager/pool, runner backends | Deployment composition, other Kontext deps, provider selection |
| `kontext-runtime` | Deployment composition/bootstrap | Provider/backend selection, local process composition, managed Python environment, startup glue | Domain logic, heavy compute engines, API router logic |
| `kontext-api` | HTTP/SSE/WebSocket transport | Routers, dependencies, request/auth context, thin application services, transport mapping | Direct persistence internals in routers, heavy compute implementations |
| `kontext-labs` | Local shell/bootstrap application | Local CLI/server composition, developer workflows | Reusable domain logic that belongs in packages above |
| `kontext-agentic` | Agent application layer | Blueprints, blueprint registry, domain tools, chat workflow, `create_agentic_system` composition | Generic API routing, relational persistence internals, harness SPI definitions |
| `kontext-agent` | Agent contracts + harness SPI | `BaseAgenticSystem`, harness SPI, run-state port, tool/streaming/client-policy primitives | LLM wiring, domain tools, blueprints, imports of `agentic`/`chat`/`data` |
| `kontext-chat` | Chat-session application workflows | Session CRUD/listing flows, chat continuation streaming orchestration | Agent runtime internals, generic API transport |
| `kontext-llm` | LLM catalog and service wiring | Foundation model metadata, language model service wiring, the `ModelConnectionStore` resolution seam | Generic agent runtime, importing `kontext-account`/`kontext-runtime` |
| `kontext-account` | Account/profile concerns | Local account/profile models and services, the local model-connection store | Generic auth/JWT infrastructure |
| `kontext-catalog` | Catalog indexing and retrieval | Catalog indexing services, document retrieval, semantic schema search, durable OKF knowledge curation | Generic API transport, unrelated domain logic |
| `kontext-okf` | Open Knowledge Format model and bundle I/O | OKF concept model (re-exported from `kontext-schema`), markdown/YAML bundle readers/writers, projection into the neutral knowledge contract | LanceDB internals, importing `kontext-catalog` |
| `kontext-schema` | Generated Pydantic models and schema contracts | Pydantic models generated from the OpenAPI spec, shared schema enums/contracts | Hand-written business logic; regenerate via `pnpm run generate:models` |

## Import Name Divergences

Most `py/*` distributions map to an identically named import package
(`kontext-account` → `kontext.account`). One intentionally diverges:

| Distribution | Import package | Why |
| --- | --- | --- |
| `kontext-job` | `kontext.jobs` | The import path is plural to avoid shadowing the common English word `job` in call sites such as `from kontext.jobs import ...`. |

Do not "fix" this to match the distribution name; it is part of the published
import contract.

## Packaging Metadata

Every `py/*` manifest carries the same `[project]` metadata so no distribution is
published under-specified. When you add a package, copy the full block from an
existing manifest rather than only the fields you happen to need:

- `description`, `readme`, `requires-python = ">=3.12"`, `license = { text = "MIT" }`, `authors`
- `classifiers` including `License :: OSI Approved :: MIT License` and `Programming Language :: Python :: 3.12`
- `[project.urls]` with `Repository = "https://github.com/kontext-labs/kontext-labs"`

Two placement rules matter because TOML tables are positional:

- Keep `dependencies` inside `[project]`. Placing `[project.urls]` above it makes
  `dependencies` a member of the wrong table.
- Put `[project.urls]` after `dependencies`, before the next `[table]` header.

## Runtime, Engine, and Execution

Three packages answer "how does work run?", so use this decision tree when
placing new code — ask the question in order and stop at the first **yes**:

1. **Does it track a durable run** (status, retries, cancellation, logs/events,
   run projection, worker coordination) across transports/processes?
   → `kontext-execution`.
2. **Does it submit or track a query session, validate SQL, or enforce
   query-session reuse/locking?**
   → `kontext-query`.
3. **Does it actually compute** (run a query, profile a file, execute Python)
   inside this or a child process?
   → `kontext-engine`.
4. **Does it choose which provider/profile is wired** (provider selection,
   bootstrap, composition roots, kernel lifecycle)?
   → `kontext-runtime`.

If none apply, it is probably a domain or contract concern, not an
execution-stack concern.

Examples:

- `ExecutionRunService`, run status projection, run events/logs: `kontext-execution`
- query submission, session reuse, SQL validation, `InProcessQuerySessionService`: `kontext-query`
- DuckDB query engine, live-SQL engine, in-process dispatchers: `kontext-engine`
- `RuntimeProfile`, `LocalRuntimeProvider`, local bootstrap, profile setup: `kontext-runtime`

### Execution-stack dependency direction

```text
kontext-common   (ports + session primitives)   ← nothing above it
     ▲
kontext-query    (orchestration; imports ports only)
     ▲  (calls get_query_execution_engine via port)
kontext-engine   (compute adapters; imports ports + resolver seam, NOT query)
     ▲
kontext-runtime  (provider selection + composition)
```

- `kontext-query` must not import `kontext-engine`.
- `kontext-engine` must not import `kontext-query`.
- `kontext-common` imports nothing above it.
- `kontext-execution` must not import `kontext-query` or `kontext-engine`.
- `kontext-llm` must not import `kontext-account` or `kontext-runtime`
  (model resolution goes through the `kontext.llm` ports).
- `kontext-okf` must not import `kontext-catalog` (the knowledge contract lives
  in `kontext-common`).

These invariants are enforced by
`py/kontext-common/tests/test_architecture_boundaries.py`. That suite also
ratchets the **package import graph**: the workspace historically uses
lazy/inline imports so a handful of cycles still exist, but any *new* cycle
fails the build. Shrinking the frozen baseline is always welcome.

### Model resolution seam

`kontext-llm` owns model-selection resolution but not where selections live:

- `kontext.llm.model_connection_store` defines the `ModelConnectionStore` port and a
  process-wide registry.
- `kontext-runtime.model_connection_store` registers the local SQLite store
  (`kontext-account`); `configure_model_resolution()` is called during bootstrap.

This keeps `llm` free of deployment and SDK-client imports (no cycles, no
inverted dependency). Kontext is local-first, so only the local store is
wired today; a hosted profile would register a different `ModelConnectionStore`
here — no change to `kontext-llm`.

## Cloud / Non-Local Execution Extension

Deployment profile and execution backend are separate axes: `local` vs `cloud`
is the deployment profile; `in-process` vs `remote` is where compute runs.

A cloud or otherwise non-local execution backend is added by supplying different
**provider implementations** — no change to `kontext-query` or `kontext-engine`
orchestration is required:

- Implement `IQuerySessionServiceProtocol` for session lifecycle/metadata (the
  local profile uses `InProcessQuerySessionService` from `kontext-query`).
- Implement `QueryRuntimeProviderProtocol.get_query_execution_engine` to return
  an engine for each `QueryEngineType` (a remote engine implements the
  `QueryExecutionEngine` port from `kontext-common`).
- Register the provider in a new `kontext-runtime` composition (mirroring
  `LocalRuntimeProvider`).

Because `kontext-query` only ever calls the port, pointing the API at the cloud
provider is a wiring change in `kontext-runtime`, not a rewrite. Keep new
`QueryEngineType` values resolvable through the port rather than branching on
engine type inside query orchestration.

The same client/server split is preserved locally on purpose: the local worker
is a *supervisor* that claims runs through `IJobRunClaimTransport`
(`kontext-engine`'s DB-poll implementation today) and uses the in-process
`LocalJobRunService`. A hosted worker would supply its own API-backed
`JobRunService` and a remote claim transport — with no change to job execution
code, because both are ports (`IJobRunServiceProtocol`,
`IJobRunClaimTransport`) declared in `kontext-common`. No such implementation
ships in this repository; a hosted deployment provides it alongside its
composition root.

## Deployment Profiles

Kontext ships as a **local-first tool**. Only the `local` deployment profile
has an implemented composition: SQLite, local filesystem storage, and local
identity. The cloud profile is a documented extension shape, not implemented
behavior.

Deployment profile and execution backend are separate axes.

- `local` is a deployment profile.
- `kernel` is the execution topology: code runs in a separate Python process.
- The same kernel topology is used locally and in a future cloud deployment;
  only the supervisor's transport to the platform differs.

Profiles:

- Local profile (implemented):
   - identity: local
   - relational backend: SQLite
   - storage backend: local filesystem
   - execution backend: separate kernel process
- Cloud profile (contract placeholder; no implementation in this repo):
   - identity: JWT/platform
   - relational backend: external
   - storage backend: external
   - execution backend: the same separate kernel process

### Kernel execution model

Job code never runs in the API or supervisor process. A supervisor claims a
queued run and starts a **kernel** child process that talks to it over a small
loopback socket protocol (`kontext.kernel`). The kernel binds four
sockets, publishes a connection file, and accepts the supervisor's connection:

- `shell` — `execute_request` / `execute_reply`, `kernel_info_request`
- `iopub` — progressive `stream` / `display_data` / `execute_result` / `status`
- `control` — `interrupt_request`, `shutdown_request`, `host_call_request/reply`
- `heartbeat` — liveness echo

The kernel is stdlib-only and imports no `kontext` code. Platform capabilities
(SQL, files, models) are reached through `host_call`, which the supervisor
services using its `RuntimeProvider`. This keeps the kernel portable: it runs
unchanged in local and hosted modes.

Python execution has a single code path. The kernel is the only executor:
`kontext-kernel` owns the process, protocol, and the dependency-free execution
contracts, and `kontext.runtime.python_environment` owns the managed virtualenv
(numpy/pandas) the kernel runs in and that `/account/python-environment` reports
on. Backend *selection* — choosing the kernel backend and resolving the managed
interpreter — is composition and lives in `kontext-runtime`
(`create_python_runner_backend`). There is no second, file-based executor to keep
consistent.

Kernels are launched with best-effort resource caps (`kontext.kernel.limits`):
POSIX `rlimit`s (address space, CPU seconds, file size, open files, processes)
and, on Windows, a Job Object that kills the kernel if the supervisor dies.

Cancellation crosses the process boundary through the run's persisted status,
not an in-process signal: the API marks a run `Canceled`, the supervisor's
executor polls that status while the run executes, and stops the kernel
(session kernels are interrupted and survive; one-shot kernels are terminated).
The signal is process-local by design; a hosted mode would carry it over its
queue transport instead of the database.

Two lifecycles share the one protocol:

- **Run kernel** (one-shot): a fresh process per execution.
- **Session kernel** (persistent): a process bound to a session id, reused
  across cells so namespace state survives; evicted after an idle timeout.

Session state is in-memory and process-local: there is **no snapshot or
restore**. If a session kernel is evicted or its process dies, the next
execution starts a fresh namespace. This is a deliberate simplification.

Kernel lifecycle details:

- The parent sends a `hello` handshake carrying the connection key before the
  kernel serves any request; the connection file is written `0600`.
- Session kernels are keyed by chat/query/notebook id; a run with no session
  scope is ephemeral and is torn down after it finishes.
- Kernels are evicted after an idle timeout, on LRU overflow, when their
  session is deleted (supervisor reconciliation), and on worker shutdown; the
  kernel workspace directory is removed on every teardown path.
- The supervisor runs a bounded number of jobs concurrently
  (`KONTEXT_LOCAL_WORKER_CONCURRENCY`, default 2).
- Local init (migrations + seed) is serialized across the API and worker
  processes with an advisory file lock (`kontext.runtime.local.init_lock`).

Cloud support is kept as **contracts, not implementations**:

- `kontext-runtime` `RuntimeProfile` selects the composition, and
  `QueryRuntimeProviderProtocol.get_query_execution_engine` selects the query
  engine; the local profile supplies `LocalRuntimeProvider` + `DuckDBQueryEngine`,
  and a cloud profile would supply its own provider + remote `QueryExecutionEngine`.
- `IQuerySessionServiceProtocol` in `kontext-common` abstracts session
  lifecycle/metadata; the in-process implementation is
  `kontext-query`'s `InProcessQuerySessionService`.
- `kontext-storage` `BaseStorageProvider` / `StorageEngine` abstract the blob and
  lake store; only `LocalFilesystemProvider` / `LocalStorageEngine` ship today.
- `IQueueClient` in `kontext-common` abstracts the message queue; only the
  in-process/no-op local path ships today.
- `IJobRunClaimTransport` in `kontext-common` abstracts *claiming* a queued run
  (distinct from a message queue); the local DB-poll implementation lives in
  `kontext-engine.transports`.
- `kontext-execution` owns durable runs regardless of where execution happens.

The claim contract lives in `kontext-common` (not `kontext-job`) because its
consumer, the engine's DB-poll transport, must not depend on the job framework:
`kontext-engine` sits below `kontext-job` in the graph, so hosting the contract
there would invert the layering. It stays out of `kontext-engine` itself because
the supervisor (in `kontext-labs`) is the consumer, and a deployment could swap
in a different transport without touching engine compute.

Do not add concrete cloud backends (S3, Azure Blob, SQS, Azure Queue, managed
Postgres) until they are actually wired and tested; add the implementation
behind the existing seam instead. Do not add a cloud-only executor — the kernel
is deployment-agnostic by design.

## Import Policy

- Import from the owning package directly.
- Do not add new compatibility re-exports.
- Prefer generated models from `kontext-schema` for schema-defined contracts.

## Current Recommendations

- Keep `kontext-runtime` thin and composition-focused.
- Keep domain jobs in their owning domain packages, with `kontext-job` providing the framework/registry.
- Move runtime composition helpers out of `kontext-api` over time so API stays transport-focused.
