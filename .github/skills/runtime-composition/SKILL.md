---
name: runtime-composition
description: Runtime provider, protocol, and profile composition conventions in py/* - use when adding services to the runtime provider, wiring new seams, or changing deployment profile behavior
---

# Runtime Composition

## Ports and protocols

- Operation-level contracts live in
  `py/kontext-common/src/kontext/common/protocols/services.py`
  (`IFileServiceProtocol`, `IQuerySessionServiceProtocol`, ...); provider
  capability surfaces in `providers.py`, composed into
  `RuntimeProviderProtocol` (full platform surface) and narrower role protocols
  (`QueryRuntimeProviderProtocol`, `JobRuntimeProviderProtocol`,
  `AIToolkitServiceProviderProtocol`, `AgentRuntimeProviderProtocol`).
- Implementations satisfy protocols structurally; no `isinstance` checks, no
  `runtime_checkable`. Narrow to an unexposed port with
  `resolve_agent_runtime_storage_provider` (in `providers.py`) rather than
  ad-hoc `hasattr` duplication.
- Capability is expressed by returning `None` from a getter, not by boolean
  flags. Consumers treat `None` as unsupported and degrade or raise.
- Widen `RuntimeProviderProtocol` when a getter is needed everywhere; keep
  single-role surfaces (jobs, AI toolkits) narrow instead.

## Provider rules

- Providers are rebuilt per request / per job run. Construction must stay
  cheap: lazy-init lightweight project-scoped services inside the provider;
  anything expensive (HTTP clients, token refreshers, connection pools) is
  built once per process at the composition root.
- Getters are project-scoped: a provider is constructed with one `project_id`
  and services derive their scope from it. Do not add `project_id` parameters
  back onto provider getters.
- Engine resolution uses the typed `QueryEngineRequest`
  (`kontext.common.query.engine`) through
  `QueryEngineResolverProtocol.get_query_execution_engine`; `None` means
  unsupported engine type. The provider enforces
  `_project_id == request.project_id` (`ProjectIdMismatchError` otherwise).
- The Python runner seams are `create_python_runner_backend` (single-use
  backend) and `create_python_session_runner` (process-shared session kernels,
  `None` when no supervisor owns them). Job code must ask its provider, never
  import `kontext-kernel` directly. Kernel *policy* / session identity live in
  `kontext.common.python` and are shared contracts, not kernel topology.
- Route service construction through provider getters; constructing services
  directly in routers is only acceptable when the concrete class belongs to
  the same package.

## Auth composition split

- `kontext.api.services.runtime.build_authorized_runtime_provider` injects an
  `AuthorizedRuntimeQuerySessionService` bound to the request's auth context —
  required for every path that can execute user SQL (streaming, execution
  runs, session-state reads).
- `ChatHandler.create_runtime_provider` (headers-based, no owner scoping) is
  restricted to paths that never execute user SQL: service resolution, CLI jobs.
- When in doubt, use the authorized composition.

## Profiles

- `RuntimeProfile` describes identity/relational/storage/execution backends and
  advertises `SiteFeature`s. Only the `local` profile is implemented;
  `cloud` is a contract placeholder that fails fast on `initialize()`/site
  config. Cloud backends (PostgreSQL, object storage, remote workers, remote
  engines) must be added behind these same seams (`RuntimeProfile`,
  `BaseStorageProvider`, `IQueueClient`, provider getters) rather than shipped
  unverified.
- `local` = deployment profile, `inprocess` = execution topology. They usually
  appear together but are not interchangeable.
- The frontend learns enabled features from `SiteConfigResponse.features`
  (parity-checked against the `SiteFeature` mirror); it must not guess from
  env vars except for pre-config bootstrap (`isLocalMode()` in
  `ts/common` is bootstrap-only).
