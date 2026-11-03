# Environment reference

Kontext reads configuration from the process environment and, for the local
server, from `.env.local` (and `.env`). The canonical spellings are
`KONTEXT_`-prefixed; legacy unprefixed names are accepted through aliases so
existing deployments keep working.

Precedence, highest first: composition-time overrides, process environment,
`.env.local`, `.env`, `config.toml`, field defaults. The local launcher loads
`.env.local` with `uv run --env-file`; the worker and Python kernel inherit the
same process environment. [.env.example](../../.env.example) is the runnable
example with copy-paste values; this page is the reference.

## Ownership

- **User-tunable** — safe to set in `.env.local` or the process environment.
- **Launcher-managed** — set by `kontext serve` or the API entrypoint.
  Do not set these by hand; the launcher overwrites or derives them.
- **Internal / test-only** — used by the test suite or automation. Leave unset.

## Security-sensitive variables

| Variable | Risk | Guidance |
| --- | --- | --- |
| `KONTEXT_LOCAL_MODE` | Chooses the local vs cloud runtime profile | Launcher-managed; the local composition forces `true`. Never start a local server with `false`. |
| `KONTEXT_LOCAL_LAUNCH_TOKEN` | Per-run credential that gates token issuance | Launcher-managed secret. Do not share or commit it. |
| `KONTEXT_ALLOWED_HOSTS` | Widens the local Host allowlist (DNS-rebinding defense) | Keep the default loopback set. Add only hostnames this machine actually serves. |
| `CORS_ALLOWED_ORIGINS` | Widens cross-origin access with credentials | Keep an explicit allowlist; avoid `*` on a credentialed deployment. |
| `JWT_SECRET_KEY`, `KONTEXT_JWT_SECRET_KEY` | Signs and validates local tokens | Local mode generates `~/.kontext/local.key`. Set only to share a key with automation; use a strong random value. |
| `KONTEXT_ACCESS_TOKEN`, `KONTEXT_REFRESH_TOKEN`, `KONTEXT_COOKIES` | CLI/interactive-auth credentials supplied through the environment | Treat as secrets; prefer interactive login. |
| `KONTEXT_INTERNAL_API_URL`, `INTERNAL_KONTEXT_API_URL` | Server-to-server target for auth flows | Point only at a trusted API; credentials are sent there. |
| `KONTEXT_LOCAL_CONSOLE_AUTO_AUTH` | Skips the first-run setup prompt for the seeded profile | Test/automation only. Leave unset in normal use. |
| `KONTEXT_ALLOWED_PATHS` | Extends filesystem access outside managed storage | List only directories that must be reachable; the managed storage path is always allowed. |
| `KONTEXT_OPEN_ROOTS`, `KONTEXT_WHITELISTED_MODULES`, `KONTEXT_BLACKLISTED_MODULES` | Kernel child open/import policy | Launcher-managed; computed by the supervisor from storage plus `KONTEXT_ALLOWED_PATHS`. |
| `KONTEXT_PYTHON_RUNTIME_PACKAGES` | Installs packages into the managed Python environment | Pin exact versions; treat these packages as trusted code. |
| `KONTEXT_JOB_DISCOVERY_PACKAGES` | Imports extra packages to discover jobs | Trusted, installed packages only. |
| `KONTEXT_AGENT_FRAMEWORK` | Selects the harness adapter plugin | Trusted entry-point distributions only. |
| `PUBLIC_KONTEXT_API_URL` | Origin the browser sends the launch token and JWTs to | The local server injects `window.location.origin`; override only for a real deployment. |
| `KONTEXT_LOCAL_DEFAULT_USER_PASSWORD` | Seeded local profile password | Change it by completing setup; do not expose the default. |
| `KONTEXT_PROJECT_PERMISSION_MAP_PATH` | Overrides the bundled permission-to-role map | Keep the default or protect the override file; it controls project authorization. |
| `ENVIRONMENT` | Enables interactive docs, detailed errors, and standalone reload | Do not use `development` for a shared deployment. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Sends traces to a collector | Point only at a trusted collector. |
| `KONTEXT_DIST_DIR` | Static app root served by the local server | Launcher-managed. |

## Server and runtime

| Variable | Default | Notes |
| --- | --- | --- |
| `ENVIRONMENT` | `development` | `development` enables `/docs`, `/openapi.json`, detailed errors, and uvicorn reload in the standalone entrypoint. |
| `HOST` | `127.0.0.1` local, `0.0.0.0` otherwise | Standalone `kontext-api` bind address. |
| `PORT` | `8000` | Standalone API port. |
| `KONTEXT_HOST` | `127.0.0.1` | `kontext serve --host`. |
| `KONTEXT_PORT` | `8000` | `kontext serve --port`. |
| `SERVICE_NAME` | `kontext-api` | Service name for logging and telemetry. |
| `CORS_ALLOWED_ORIGINS` | Profile default | Comma-separated origins. Empty or `*` falls back to the local/production default list; credentials cannot be combined with `*`. |
| `KONTEXT_DIST_DIR` | Bundled `app/dist` | Launcher-managed React build served by the local server. |
| `KONTEXT_LAKE_PATH` | `.kontext` | Local lake root; `kontext serve --lake-path` overrides it. |
| `KONTEXT_API_URL` | `http://localhost:8101` | API base URL used by interactive authentication. |
| `KONTEXT_LOCAL_MODE` | `true` in the local composition | Internal deployment-profile switch. The frontend reads the same name from `window.ENV` for early local-auth decisions. |
| `KONTEXT_LOCAL_LAUNCH_TOKEN` | Per-run random | Launcher-managed credential. Persisted to `~/.kontext/runtime/launch.token` and `launch-<port>.token`. |
| `KONTEXT_ALLOWED_HOSTS` | Loopback plus local interfaces | Comma-separated Host allowlist. `kontext serve` adds this machine's addresses for wildcard binds. |
| `KONTEXT_SITE_FEATURES` | Unset | Comma-separated features to enable on top of the profile defaults. |
| `KONTEXT_DISABLED_SITE_FEATURES` | Unset | Comma-separated features to disable; disable wins over enable. |

## Local authentication

| Variable | Default | Notes |
| --- | --- | --- |
| `JWT_SECRET_KEY` | Generated local key | Legacy alias for `KONTEXT_JWT_SECRET_KEY`. |
| `KONTEXT_JWT_SECRET_KEY` | Generated local key | Canonical signing key. Local mode creates `~/.kontext/local.key` when unset. |
| `JWT_ISSUER` | `kontext-api` | Legacy alias; the local runtime mints with `kontext-local`. |
| `KONTEXT_JWT_ISSUER` | `kontext-api` | Canonical expected issuer. |
| `JWT_AUDIENCE` | `kontext-platform` | Legacy alias. |
| `KONTEXT_JWT_AUDIENCE` | `kontext-platform` | Canonical expected audience. |
| `KONTEXT_LOCAL_ACCESS_TOKEN_TTL_SECONDS` | `2592000` (30 days) | Local access-token lifetime. |
| `KONTEXT_LOCAL_REFRESH_TOKEN_TTL_SECONDS` | `31536000` (365 days) | Local refresh-token lifetime. |
| `KONTEXT_LOCAL_DEFAULT_USER_EMAIL` | `local@kontext.local` | Seeded placeholder profile email. |
| `KONTEXT_LOCAL_DEFAULT_USER_PASSWORD` | `Loc@l12e456` | Seeded placeholder password. Change it through setup. |
| `KONTEXT_LOCAL_CONSOLE_AUTO_AUTH` | Unset | Internal/test-only override that auto-authenticates the placeholder profile. |
| `KONTEXT_INTERNAL_API_URL` | Empty | Server-to-server API base; falls back to `http://localhost:8101`. |
| `INTERNAL_KONTEXT_API_URL` | Empty | Legacy alias for `KONTEXT_INTERNAL_API_URL`. |
| `KONTEXT_PLATFORM_LOGIN_URL` | `/login` | Hosted-mode login redirect; unused locally. |
| `KONTEXT_PLATFORM_LOGOUT_URL` | `/logout` | Hosted-mode logout redirect; unused locally. |
| `KONTEXT_ACCESS_TOKEN` | Unset | Bearer token input for CLI/interactive auth. |
| `KONTEXT_REFRESH_TOKEN` | Unset | Refresh token input for CLI/interactive auth. |
| `KONTEXT_COOKIES` | Unset | Reserved cookie-auth input; currently unused. |
| `KONTEXT_AUTH_CALLBACK_PORT` | `8080` | Interactive-auth callback port. |
| `KONTEXT_AUTH_TIMEOUT_SECONDS` | `300` | Interactive-auth timeout. |
| `KONTEXT_AUTH_AUTO_OPEN_BROWSER` | `true` | Whether interactive auth opens a browser. |

## Storage and paths

| Variable | Default | Notes |
| --- | --- | --- |
| `PROJECT_DB_URL` | Local SQLite `~/.kontext/kontext.db` | Legacy alias for `KONTEXT_PROJECT_DB_URL`. |
| `KONTEXT_PROJECT_DB_URL` | Local SQLite `~/.kontext/kontext.db` | Project database URL; SQLite locally, PostgreSQL in hosted deployments. |
| `STORAGE_PROVIDER` | `local` | Storage backend selection. |
| `FILE_STORAGE_PATH` | Unset | Legacy file-storage override. |
| `KONTEXT_LOCAL_STORAGE_PATH` | `~/.kontext/storage` | Local storage-provider root. |
| `KONTEXT_ALLOWED_PATHS` | Empty | Extra directories file access may reach (OS path separator between entries). |
| `KONTEXT_OPEN_ROOTS` | Launcher-managed | Roots the kernel child may open; computed from storage plus allowed paths. |
| `KONTEXT_WHITELISTED_MODULES` | Launcher-managed | Import allowlist for the kernel child. |
| `KONTEXT_BLACKLISTED_MODULES` | Launcher-managed | Import blocklist for the kernel child. |
| `KONTEXT_DUCKDB_TEMP_DIR` | System temp | DuckDB spill directory. |
| `KONTEXT_EXTENSIONS_DIR` | DuckDB default | DuckDB extension directory; point at a trusted path. |
| `KONTEXT_FASTEMBED_CACHE_DIR` | Library default | Model cache for the default embedding provider; point at a trusted path. |
| `KONTEXT_EMBEDDING_PROVIDER` | `fastembed` | Embedding backend; unknown values fall back to a local hash embedding. |
| `KONTEXT_EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model name. |
| `KONTEXT_PROJECT_PERMISSION_MAP_PATH` | Empty | Override file for the project permission-to-role map; empty uses the bundled map. |
| `PROJECT_PERMISSION_MAP_PATH` | Empty | Legacy alias for `KONTEXT_PROJECT_PERMISSION_MAP_PATH`. |
| `KONTEXT_PROJECT_CACHE_DURATION_MINUTES` | Unset | Reserved project-cache override; currently unused. |

## Worker and execution

| Variable | Default | Notes |
| --- | --- | --- |
| `KONTEXT_LOCAL_WORKER_ENABLED` | `true` | Start the job worker alongside `kontext serve`. |
| `KONTEXT_LOCAL_WORKER_CONCURRENCY` | `2` | Concurrent jobs per worker. |
| `KONTEXT_LOCAL_WORKER_POLL_INTERVAL` | `0.5` | Idle poll interval in seconds. |
| `KONTEXT_LOCAL_WORKER_WATCHDOG` | `true` | Restart the worker if it exits unexpectedly. |
| `KONTEXT_LOCAL_SESSION_REAP_INTERVAL` | `60` | Seconds between checks for orphaned session kernels. |
| `KONTEXT_LOCAL_RUN_LEASE_REAP_INTERVAL` | `60` | Seconds between lease-reclaim checks. |
| `KONTEXT_LOCAL_SESSION_FILE_SWEEP_INTERVAL` | `3600` | Seconds between session-file sweeps. |
| `KONTEXT_LOCAL_SESSION_FILE_SWEEP_GRACE` | `600` | Grace period before a swept session file is removed. |
| `KONTEXT_LOCAL_RESULT_STORE_RETENTION` | `86400` | Seconds to retain result-store entries. |
| `KONTEXT_JOB_RUN_LEASE_SECONDS` | `300` | Job-run claim lease duration. |
| `KONTEXT_JOB_RUN_MAX_LEASE_RECLAIMS` | `5` | Dead-letter a run after this many reclaims. |
| `KONTEXT_PYTHON_MAX_CONSECUTIVE_KERNEL_FAILURES` | `3` | Stop retrying agent Python execution after this many infrastructure failures. |
| `KONTEXT_PYTHON_RUNTIME_PACKAGES` | Unset | Comma-separated packages installed into the managed Python environment. Pin versions. |
| `KONTEXT_JOB_DISCOVERY_PACKAGES` | Unset | Comma-separated packages scanned for job definitions. |

## Agent, models, and prompts

| Variable | Default | Notes |
| --- | --- | --- |
| `KONTEXT_AGENT_FRAMEWORK` | `agno` | Harness adapter selected from the `kontext.agent_harnesses` entry-point group. |
| `KONTEXT_AGENT_FRAMEWORK_LOGGERS` | Unset | Comma-separated logger names owned by the harness. |
| `KONTEXT_AGENT_STREAM_THREADS` | `8` | Concurrent agent streams in the Agno harness. |
| `MODEL_PROVIDER` | `lm_studio` | Default provider: `lm_studio`, `ollama`, `openai`, `anthropic`, `openrouter`, `openai_compatible`, `gemini`, `bedrock`, and others listed in `.env.example`. |
| `SQL_DIALECT` | `DuckDB` | SQL dialect label passed to the model service. |
| `PROJECT_AGENT_MARKDOWN` | Unset | Agent markdown behavior override. |
| `PROJECT_AGENT_ADD_HISTORY` | Unset | Include prior runs in the agent context. |
| `PROJECT_AGENT_NUM_HISTORY_RUNS` | Unset | Number of prior runs to include. |
| `PROJECT_AGENT_TELEMETRY` | Unset | Agent telemetry override. |
| `PROJECT_AGENT_TOOL_CALL_CLIENT_POLICY` | Unset | Tool-call client policy override. |
| `PROJECT_AGENT_SUMMARY` | Unset | Summary behavior override. |
| `PROJECT_AGENT_DEBUG` | Unset | Agent debug output. |
| `PROJECT_AGENT_TOOL_CALL_LIMIT` | Unset | Maximum tool calls per run. |
| `PROJECT_AGENT_REASONING_EFFORT` | Unset | Reasoning-effort override for supported models. |

Provider credentials and model ids (`*_API_KEY`, `*_API_BASE`, `*_MODEL`, and the
AWS SDK variables used by Bedrock) are documented with the provider matrix in
[Model provider configuration](../ai/model-provider-configuration.md) and in
[.env.example](../../.env.example).

## Frontend and public URLs

| Variable | Default | Notes |
| --- | --- | --- |
| `PUBLIC_KONTEXT_API_URL` | `http://localhost:8101` | Client API base. The local server injects `window.location.origin`. |
| `PUBLIC_KONTEXT_DATA_API_URL` | `http://localhost:8000` | Data API base for notebook/chart helpers. |
| `PUBLIC_KONTEXT_URL` | `https://kontext.tech` | Hosted platform URL shown in console links. |
| `PUBLIC_KONTEXT_APP_URL` | `/` | App URL; the dev server uses `http://localhost:8002`. |
| `PUBLIC_KONTEXT_DOCS_URL` | `https://docs.kontext.tech` | Help → Docs link. |
| `PUBLIC_KONTEXT_UPDATES_PROJECT_ID` | Built-in UUID | Project used for Kontext update messages. |
| `IS_DEVELOPMENT` | Unset | Frontend development-mode hint. |
| `VITE_PORT` | `8002` | Vite dev-server port. |

## Observability

| Variable | Default | Notes |
| --- | --- | --- |
| `KONTEXT_LOG_LEVEL` | `INFO` | Root log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `LOG_LEVEL` | `INFO` | Legacy alias. |
| `KONTEXT_LOG_FORMAT` | `json` | `json` or `plain`. |
| `LOG_FORMAT` | `json` | Legacy alias. |
| `UVICORN_ACCESS_LOG_FORMAT` | Unset | Override for the uvicorn access-log format. |
| `OTEL_SDK_DISABLED` | `false` | Set `true` to skip telemetry setup entirely. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Unset | OTLP HTTP collector endpoint; unset keeps traces local. |
| `OTEL_SERVICE_NAME` | `kontext-studio` | Telemetry service-name override. |

## Tooling-only variables

The following are build/capture/platform internals, not runtime configuration:
`DOCS_*` (docs capture), `UV_CACHE_DIR`, `NODE_ENV`, `VITE_MODE`, `ANALYZE`,
`WINDIR`, `KONTEXT_API_SCHEMA_OUT_FILE`, and `KONTEXT_SCHEMA_OUT_FILE`.

## Validation

```bash
pnpm run validate:env-docs
```

The check compares the names documented here with `.env.example`, the
`ALL_ENV_VARS` registry, and environment reads in the code, so a new variable
or a stale row fails CI.
