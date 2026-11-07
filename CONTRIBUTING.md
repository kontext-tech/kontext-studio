# Contributing to Kontext

Thanks for your interest in improving Kontext. This guide covers local
setup, the commands we expect you to run, and how to get a change merged.

## Prerequisites

> The agent-oriented canonical guide is [`AGENTS.md`](AGENTS.md); this file is
> the human contributor onboarding view. Common commands are mirrored in both —
> update both when adding one.

For the system map — processes, layers, data flow, and technology choices — see
[the architecture overview](docs/development/architecture.md).

- **Node.js** `>=22.23.4` and **pnpm** `>=10.0.0`
- **Python** `>=3.12` and [**uv**](https://docs.astral.sh/uv/)
- **Git**

We use `pnpm` for all TypeScript/Node work and `uv` for all Python work. Please
do not use `npm`, `yarn`, `pip`, or ad-hoc virtualenv workflows.

## Local setup

```bash
git clone https://github.com/kontext-tech/kontext-studio.git
cd kontext-studio

pnpm install      # Node/TypeScript workspace dependencies
uv sync           # Python environment
uv sync --group codegen   # optional: only for `pnpm run generate:models`
cp .env.example .env.local   # local runtime configuration (see below)
```

`.env.local` is gitignored and read by `pnpm run dev:local` and the VS Code
launch/tasks. The committed `.env.example` holds the local-mode defaults, so a
plain copy works out of the box; add a model-provider key if you want to use AI
chat.

There is no bootstrap or artifact-download step: the generated API types and
Pydantic models are committed to the repository.

Install the pre-commit hooks:

```bash
uv tool install pre-commit
pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
```

## Common commands

```bash
pnpm run build:shared     # build shared TypeScript packages (needed before app builds)
pnpm run build            # build shared packages and the app
pnpm lint                 # root ESLint across the workspace
pnpm format:check         # prettier across the workspace

pnpm run test:python      # Python workspace test runner
pnpm run test:ts          # all TypeScript workspace tests
pnpm typecheck:python     # Python pyright runner

pnpm run generate:api-types     # regenerate the committed TypeScript API types
pnpm run generate:models        # regenerate the Pydantic models

# Structural validators (same set CI runs):
pnpm run validate:workspace-graph      # package.json deps ↔ tsconfig refs
pnpm run validate:workspace-versions   # lockstep version + changelog consistency
pnpm run validate:agent-docs           # AGENTS.md ↔ skills topology
pnpm run validate:tool-pins            # pinned tool versions consistent

# Schema hub contract check:
pnpm --filter @kontext-tech/schema run check:contracts
```

Targeted runs while iterating:

```bash
uv run --package kontext-agentic pytest py/kontext-agentic/tests
uv run --package kontext-api pytest py/kontext-api/tests
uv run --package kontext-runtime pytest py/kontext-runtime/tests

pnpm --filter @kontext-tech/schema test
pnpm --filter @kontext-tech/chart test
pnpm --filter @kontext-tech/notebook test

pnpm --filter @kontext-tech/app lint
pnpm --filter @kontext-tech/app build
```

## Verification expectations

Before opening a pull request:

- Python changes under `py/`: run the affected package tests. If you touched
  shared agent/runtime/session-state code, run the full `kontext-agentic` suite.
- React/TypeScript changes under `app/`, `ts/`, or `tools/`: run the relevant
  package checks (lint, typecheck, or build).
- If a package has tests, run them. If not, run its lint, typecheck, or build
  command.
- Schema/OpenAPI changes under `ts/schema`: regenerate the API types with
  `pnpm run generate:api-types` (and the models with `pnpm run generate:models`
  if Python contracts changed), then commit the result.
- Python coverage: CI enforces an overall floor (`[tool.coverage.report]
  fail_under` in the root `pyproject.toml`, currently 40). The floor ratchets
  upward over time, so prefer adding tests when you touch Python code.

Say what you ran and what you did not run in your pull request description.

## Generated code

Do not hand-edit generated files:

- `ts/schema/src/generated/api.ts`
- the Pydantic models in `py/kontext-schema/src/kontext/schema/_generated/`

Change the generator inputs (the Zod models under `ts/schema/src` or the FastAPI
routers) and regenerate. See
[docs/development/generated-code.md](docs/development/generated-code.md).

CI has a generated-code freshness gate that fails if the committed output does not
match the spec.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<scope>): <description>
```

Common types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
`chore`. Subject lines are imperative, at most 72 characters, and have no
trailing period.

## Pull requests

1. Branch from `main`.
2. Keep the change focused; avoid unrelated refactors.
3. Make sure the relevant checks pass locally.
4. Describe the change, the motivation, and the verification you ran.
5. CI must pass — including lint, tests, the generated-code freshness gate, and
   the unified-wheel smoke test.

By participating you agree to abide by our
[Code of Conduct](CODE_OF_CONDUCT.md) and that your contributions are licensed
under the repository's [MIT License](LICENSE). For security issues, follow
[SECURITY.md](SECURITY.md) instead of opening a public issue.
