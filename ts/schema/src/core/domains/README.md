# Core domains (Zod-first)

This folder is the **authoring** location for core contracts that are shared across:

- TypeScript (via `@kontext-tech/schema` and generated SDKs)
- Python (via generated Pydantic models and SDKs)
- External API consumers reading the committed OpenAPI specs

Each domain lives in its own folder and exports schemas through a domain
`index.ts`.

Current domains:

- `base/`
- `events/`
- `identity/`
- `infrastructure/`
- `jobs/`
- `knowledge/`
- `notifications/`
- `projects/`
- `tokens/`
