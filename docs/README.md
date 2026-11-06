# Kontext documentation

Documentation for the Kontext repository, grouped by what the reader is trying
to do rather than by subject area.

## Use Kontext

Task documentation for people running the released product, with screenshots
and numbered steps.

- [Kontext Labs user guide](user-guide/README.md) — install, set up a profile, and
  work with projects, data sources, notebooks, and chats.
- [Install Kontext](../README.md#install) in the repository README.

The user guide assumes the installed `kontext-labs` package and
`kontext-labs serve`; it does not require a repository checkout.

## Understand Kontext

Architecture, conventions, and design decisions for contributors.

- [AI architecture](ai/ai-architecture.md) — agents, tools, and the request
  path.
- [Harness abstraction](ai/harness-abstraction.md) — the swappable agent
  framework boundary.
- [Harness strategy](ai/harness-strategy.md) — the decision record behind
  staying on Agno and keeping the exit cheap.
- [Model provider configuration](ai/model-provider-configuration.md) — provider
  inputs, catalog defaults, and the harness-neutral model object.
- [Tool result schemas](ai/tool-results-schema.md) — the shared transport schema
  for tool results.
- [Notebook system](notebook/notebook-system.md) — the block document model and
  host contract.
- [Python package boundaries](development/python-package-boundaries.md) — the
  package responsibility matrix and dependency rules.
- [Security and trust model](development/security-model.md) — what the local
  launch token, guards, JWT, and confinement protect.
- [Authorization and permissions](development/authorization.md) — claims, project
  roles, feature gates, and the permission map.

## Change Kontext

Workflows for building, verifying, and releasing this repository.

- [Environment reference](development/environment.md) — runtime variables,
  ownership, and the security-sensitive knobs.
- [Local operations and troubleshooting](development/local-operations.md) —
  running the stack, launch-token recovery, and common failures.
- [OpenAPI specifications](development/openapi-workflow.md) — refreshing and
  validating the tracked specs.
- [Generated code](development/generated-code.md) — the committed API types and
  Python models.
- [Releasing](development/releasing.md) — the app, wheel, TypeScript package, and
  docs publishing paths.
- [Contributing](../CONTRIBUTING.md)
- [App development](../app/README.md)
- [Agent guide](../AGENTS.md)

## Publish the docs

The Starlight site under [docs-site](../docs-site/README.md) publishes the user
guide and the durable developer reference pages. Plans, decision records, and
roadmaps stay in the repository and are not published.

## Conventions

Use `Kontext` for this repository and package workspace.

Each fact has exactly one canonical home. Other documents link to it rather than
restating it: the user guide never explains internals, contributor documents
never describe click paths, and screenshots stay in the user guide.
