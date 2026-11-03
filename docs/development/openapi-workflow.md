# OpenAPI specifications

Kontext tracks three OpenAPI documents under `ts/schema/src/schemas/`:

| Spec | Source | Refresh |
| --- | --- | --- |
| `kontext.models.openapi.json` | Zod-first schemas under `ts/schema/src` | `pnpm --filter @kontext-tech/schema refresh-schemas` |
| `kontext.api.openapi.json` | The FastAPI Data & AI app, imported offline | `pnpm run refresh:api-schema` |
| `kontext.api.core.openapi.json` | Frozen snapshot of the retired hosted platform contract | Not regenerated |

All three are committed. `kontext.models` and `kontext.api` feed model and
client generation; `kontext.api.core` is retained only for consumers of the old
core contract.

## Refresh the API spec

The supported path imports the FastAPI app, calls `app.openapi()`, normalizes
the document, and writes the result. No running server is required.

```bash
pnpm run refresh:api-schema
```

Equivalent entry points are the VS Code task `refresh: api schema` and
`pnpm --filter @kontext-tech/schema refresh-api-schema`.

Normalization is centralized in
[`ts/schema/scripts/openapi-normalize.cjs`](../../ts/schema/scripts/openapi-normalize.cjs).
The exporter passes the cloud runtime profile explicitly, so the tracked spec
keeps the non-local route shape even though this repository ships local mode
only; no environment override is involved.

## Validate

```bash
pnpm --filter @kontext-tech/schema run check:openapi
pnpm --filter @kontext-tech/schema run check:contracts      # full; needs uv
pnpm --filter @kontext-tech/schema run check:contracts:ts   # Node-only subset
```

`check:contracts` verifies the models snapshot, the API snapshot, OpenAPI
validity, and TypeScript/Python contract parity. CI runs the Node-only subset
in the TypeScript lint job and the full suite in the generated-code job.

## Inspect at runtime

With the local server running:

- Swagger UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>

## Rules

- Edit the Zod schema or the FastAPI route, then regenerate. Do not hand-edit a
  generated spec.
- Keep the core spec on `openapi: 3.0.x` and use normalized `nullable: true`
  fields where downstream generators need them.
- If an export starts containing local-only routes, check the offline exporter
  under `py/kontext-api`.

## Related documentation

- [Generated code](generated-code.md) — TypeScript types and Python models
  produced from these specs.
- [Python package boundaries](python-package-boundaries.md) — where transport
  and schema code belongs.
