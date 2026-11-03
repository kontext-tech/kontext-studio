# Kontext API

Unified FastAPI application that exposes the Kontext Data & AI API surface.
It is a regular workspace member of the `py/` uv workspace and is normally
started through the `kontext-labs` console package rather than directly.

## Architecture

`create_app()` mounts the standard routers and applies shared middleware:

- **Data APIs**: query execution, query sessions, files, projects, jobs, runs
- **AI APIs**: project-scoped chat streaming, workflows
- **Catalog / OKF**: catalog indexing and Open Knowledge Format bundles
- **Health**: health and ping endpoints

`kontext-labs` reuses these same routers for local mode, serves the built React
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

- `KONTEXT_LOCAL_MODE` — `true` selects SQLite + local filesystem + in-process
  execution.
- `ENVIRONMENT` — deployment environment name; `development` enables the
  interactive docs routes.
- `ENV_CORS_ALLOWED_ORIGINS` — comma-separated CORS allowlist.
- Model provider keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, …) — see
  `.env.example`.

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

Every endpoint except health/ping requires JWT authentication via the
`Authorization: Bearer <token>` header. Local mode mints its own tokens; see
`kontext-api` dependencies and the `kontext-auth` package.

## Testing

```bash
# Whole workspace (from the repository root)
pnpm run test:python

# This package only
uv run --package kontext-api pytest py/kontext-api/tests
```
