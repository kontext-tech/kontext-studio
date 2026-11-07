# Kontext API

Unified FastAPI application that exposes the Kontext Data & AI API surface.
It is a regular workspace member of the `py/` uv workspace and is normally
started through the `kontext-studio` console package rather than directly.

## Architecture

`create_app()` mounts the standard routers and applies shared middleware:

- **Data APIs**: query execution, query sessions, files, projects, jobs, runs
- **AI APIs**: project-scoped chat streaming, workflows
- **Catalog / OKF**: catalog indexing and Open Knowledge Format bundles
- **Health**: health and ping endpoints

`kontext-studio` reuses these same routers for local mode, serves the built React
app, and runs an embedded worker. Keep local routes compatible with the API
contract defined in this package rather than inventing separate local shapes.

## Local development

Start the whole local stack (API + app) from the repository root:

```bash
pnpm run dev:local
```

Or run just the API from source:

```bash
uv run --package kontext-api uvicorn kontext.api.main:app --reload --host 0.0.0.0 --port 8000
```

Local mode uses SQLite plus the local filesystem; no external database or
object store is required. See `.env.example` for the supported configuration.

## Environment

Configuration is read from the environment (typically `.env.local`, see
`.env.example`). Common values:

- `KONTEXT_LOCAL_MODE` — internal deployment-profile switch owned by the
  composition root. The local launcher sets it to `true`; the OpenAPI exporter
  passes the cloud profile explicitly. Do not set it to `false` for a local
  server.
- `ENVIRONMENT` — deployment environment name; `development` enables the
  interactive docs routes.
- `CORS_ALLOWED_ORIGINS` — comma-separated CORS allowlist.
- Model provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …) — see
  `.env.example`.

See [the environment reference](../../docs/development/environment.md) for the
full variable list, ownership rules, and security-sensitive settings.

## API documentation

When running in development mode:

- **OpenAPI spec**: <http://localhost:8000/openapi.json>
- **Swagger UI**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>

The committed generator-facing spec lives at
`ts/schema/src/schemas/kontext.api.openapi.json`; refresh it with
`pnpm run refresh:api-schema` (see
[docs/development/openapi-workflow.md](../../docs/development/openapi-workflow.md)).

## Authentication

Every data endpoint requires JWT authentication via the
`Authorization: Bearer <token>` header. Local mode mints tokens only for
callers that present the per-run launch token in `X-Kontext-Launch-Token`;
`kontext serve` prints that token in the URL it opens
(`http://127.0.0.1:<port>/#token=...`) and writes it to
`~/.kontext/runtime/launch.token` plus a per-port `launch-<port>.token`
(owner-only) so a lost URL can be recovered even with several local servers
running. Local mode additionally validates the Host header and rejects foreign
Origins so a DNS-rebinding page cannot reach the API. When bound to a
non-loopback address, the CLI adds this machine's interface addresses to
`KONTEXT_ALLOWED_HOSTS`; set it explicitly for hostnames or reverse proxies.

## Testing

```bash
# Whole workspace (from the repository root)
pnpm run test:python

# This package only
uv run --package kontext-api pytest py/kontext-api/tests
```
