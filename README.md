# Kontext Labs

**Kontext Labs is a local, open-source data and AI workspace.** It gives you a
notebook-style environment for querying data, running Python, and working with AI
agents — all running on your own machine, over your own files and databases.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What you get

- **Data workspace** — connect local files and databases, browse catalogs, and
  explore schemas without uploading your data anywhere.
- **SQL notebooks** — author markdown and SQL blocks, execute queries, and
  visualize results as charts.
- **Python execution** — run Python against your local engine and data.
- **AI chat** — chat with agents that can read your workspace context and use
  tools to answer questions about your data.
- **Local-first runtime** — the API, engine, storage, and web app all run in a
  single process on your machine. Your data stays local.

## Install

Kontext Labs is published to PyPI as the `kontext-labs` package. Each GitHub
Release also carries the matching wheel.

```bash
uv tool install kontext-labs
```

To pin a specific release:

```bash
uv tool install "kontext-labs==0.261.0"
```

Then start the local server from the directory that holds your project:

```bash
kontext-labs serve
```

This starts the local API server, serves the web app, and runs the embedded
local worker. `kontext-labs-serve` is the legacy alias for the same command.

> Requires Python 3.12 or newer. [Install `uv`](https://docs.astral.sh/uv/) if
> you do not have it yet.

## Development

This repository is a `pnpm` + `uv` workspace containing the app, TypeScript
packages, Python packages, and the generated TypeScript API types.

```bash
pnpm install          # install Node/TypeScript workspace dependencies
uv sync               # create the Python environment

pnpm run build:shared # build shared TypeScript packages
pnpm run build        # build shared packages and the app
pnpm run test:python  # run the Python workspace test suite
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution workflow.

## Repository layout

- `app/`: React + Vite labs application (Ant Design v6).
- `ts/`: TypeScript packages published as `@kontext-labs/*`.
- `py/`: Python packages built as `kontext-*`.
- `examples/`: private sample apps that consume the packages and are not
  distributed (e.g. the notebook demo).
- `tools/`: repo-level validators and local development helpers.
- `docs/`: user guide and developer reference sources published to
  [docs.kontext.tech](https://docs.kontext.tech).
- `docs-site/`: Astro Starlight site built from `docs/`; see
  [docs-site/README.md](docs-site/README.md).
- `scripts/`: build, test, image, and release helpers.
   - `scripts/uv/`: the Python (uv) helper that builds the unified
     `kontext-labs` wheel.
- `ts/schema/src/generated/`: the generated TypeScript API types, committed
  and consumed by the shared services (see
  [docs/development/generated-code.md](docs/development/generated-code.md)).

## Generated API types

The TypeScript API types are generated from the OpenAPI spec at
`ts/schema/src/schemas/kontext.api.openapi.json` with `openapi-typescript` and
**committed to this repository** so a clone is buildable without any bootstrap
step. Regenerate them after changing schema inputs:

```bash
pnpm run generate:api-types     # TypeScript API types
pnpm run generate:models        # Pydantic models
```

Continuous integration verifies that the committed output matches the spec, so
always commit the regenerated files.

The generated types back the `openapi-fetch` client used by the shared service
packages; no TypeScript client package is published from this repository
anymore. Python and other-language consumers generate their own client from the
spec published by
`@kontext-labs/schema` (`./specs/api`). See
[docs/development/generated-code.md](docs/development/generated-code.md).

## Release

TypeScript package versioning and publishing uses Commitizen
(`pnpm run version:labs`) and publishes to GitHub Packages under the
`@kontext-labs/*` scope. See
[docs/development/releasing.md](docs/development/releasing.md) for the full
flow. The unified `kontext-labs` wheel is published to PyPI and attached to the
matching GitHub Release; it is the end-user install path described above.

The docs site is published by `.github/workflows/publish-docs.yml` on each
release (and on demand). It uploads `docs-site/dist` to the S3 + CloudFront
infrastructure defined in `kontext-tech/kontext-platform` and serves it at
`https://docs.kontext.tech`.

## License

[MIT](LICENSE)
