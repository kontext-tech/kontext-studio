# Kontext app

React + TypeScript + Vite front end for the Kontext package workspace.

Run it locally with:

```bash
pnpm run dev:app
```

It consumes the shared workspace packages (`@kontext-labs/*`) built by
`pnpm run build:shared`, and talks to the local `kontext-labs` server
(`uv run --env-file .env.local kontext-labs serve --reload`).

You can also start the app together with the local server via
`pnpm run dev:local` (see the repository [CONTRIBUTING.md](../CONTRIBUTING.md)).

## Runtime environment configuration

Public runtime URLs (`PUBLIC_KONTEXT_API_URL`, `PUBLIC_KONTEXT_DATA_API_URL`,
`PUBLIC_KONTEXT_URL`, `PUBLIC_KONTEXT_APP_URL`) are intentionally **empty** in
production builds. The Vite build config only falls back to `localhost` defaults
when these variables are *unset* — not when they are empty — so release
artifacts ship without baked-in `localhost` URLs.

Local `pnpm run dev:app` and `pnpm run dev:local` set these for you. To override
them (for example to point at a non-default API), set the `PUBLIC_KONTEXT_*`
variables in `.env.local`.
