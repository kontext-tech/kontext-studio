# Generated code

The TypeScript API types and Python models are generated from the OpenAPI specs
and committed to the repository. A fresh clone builds and tests without a
bootstrap or artifact-download step, and contract changes stay reviewable in
pull requests.

## Generated artifacts

| Path | Consumed by | Generator |
| --- | --- | --- |
| `ts/schema/src/generated/api.ts` | `@kontext-tech/common` via `openapi-fetch` | `openapi-typescript` |
| `py/kontext-schema/src/kontext/schema/_generated/` | `kontext.schema` Python imports | `datamodel-code-generator` (Pydantic v2) |

The TypeScript types are generated from
`ts/schema/src/schemas/kontext.api.openapi.json` and exported as the
`@kontext-tech/schema/api` subpath. Shared API services build a typed
`openapi-fetch` client from those types; no generated client package is
published.

The Python models live in the `_generated/` subpackage. `base.py`, `policies.py`,
and `__init__.py` beside it are hand-written and survive regeneration, so the
generated directory can always be cleared and rebuilt.

## Regenerate

```bash
pnpm run generate:api-types   # ts/schema/src/generated/api.ts
pnpm run generate:models      # Pydantic models
```

`scripts/generate-api-types.sh` runs `openapi-typescript` over the committed
spec and needs only Node and pnpm. `ts/schema/scripts/generate-models.sh`
exports the Zod contracts, then runs `datamodel-codegen` from the root
`uv.lock` `codegen` dependency group. `pnpm run check:generator-smoke` checks
that the expected Python exports and TypeScript types are present.

Two contract policies cannot be expressed by the generator; they are
hand-written bases in `policies.py` and selected per model with
`--base-class-map`:

- OKF UTC timestamp normalization.
- Update-request nullability.

`base.py` holds assignment validation, protected namespaces, and the
`additional_properties` / `to_dict` compatibility helpers. `__init__.py`
re-exports the generated models.

## Freshness gate

CI regenerates both artifacts and fails if `git status --porcelain` reports any
change:

```bash
pnpm run generate:api-types
pnpm run generate:models
git status --porcelain
```

A pre-commit hook prints a reminder when schema inputs change; CI remains the
authority. If the gate fails, run the commands locally and commit the output.

## Composition decisions

1. **Models-only schemas are kept.** The hub is generated from the shared
   OpenAPI source, not endpoint usage. Models without a current local consumer
   are contract surface for hosted endpoints, and pruning them would make the
   generator inputs drift from the published spec.
2. **Types live in `ts/schema`.** They are a single committed file compiled with
   the package, so there is no separate generated package or `prepare` build
   step. `ts/common` imports the `paths` type through
   `@kontext-tech/schema/api`.
3. **Generated output is excluded from hand-run formatters and linters.**
   `ts/schema/src/generated/` is ignored by Prettier, ESLint, and whitespace
   hooks. Ruff owns the Python models: the generator runs the repository-pinned
   Ruff over its output, and `_generated/` is the only excluded directory.

## External consumers

This repository generates TypeScript types and Python models only. Other
languages can generate clients from the committed specs, which
`@kontext-tech/schema` exports as `./specs/api` and `./specs/core`.

## Related documentation

- [OpenAPI specifications](openapi-workflow.md) — how the tracked specs are
  refreshed and validated.
- [Python package boundaries](python-package-boundaries.md) — where generated
  and hand-written schema code belongs.
