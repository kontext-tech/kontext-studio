<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="app/public/resources/logo-dark-small.svg">
    <img src="app/public/resources/logo-small.svg" alt="Kontext Studio logo" width="72" height="72">
  </picture>
</p>

<h1 align="center">Kontext Studio</h1>

**Kontext Studio is a local-first, open-source AI data workspace.** Ask questions in
plain language and a team of agents queries your files and databases, then
returns SQL results, charts, and reproducible notebooks. Bring your own model —
local or cloud — and keep the workspace on your machine.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  <a href="https://docs.kontext.tech/user-guide/">
    <img src=".github/assets/chat-notebook-demo.gif" alt="A chat answer beside the SQL, chart, and Python notebook it produced" width="900">
  </a>
</p>

<p align="center"><sub>Ask a question. The agent returns the SQL, chart, and reproducible notebook.</sub></p>

## What you get

- **Ask, don't assemble** — a coordinator routes work to SQL, chart, notebook,
  and Python specialists, and every tool call stays visible.
- **Outputs you can keep** — answers become data tables, charts, and notebooks
  that mix prose, SQL, Python, and diagrams.
- **Your sources** — a managed local lakehouse plus DuckDB, SQLite, PostgreSQL,
  and MySQL connections over data you already have.
- **Your models** — Ollama or LM Studio locally, or cloud providers such as
  OpenAI, Anthropic, Gemini, and Bedrock.
- **Grounded context** — curated Knowledge concepts for metrics, joins, and
  golden queries, with agent proposals you review.
- **Local-first** — the app, API, job worker, and Python kernels run on one
  machine; prompts go only to the model provider you configure.

## Install

### macOS desktop app

Download the latest DMG from
[GitHub Releases](https://github.com/kontext-tech/kontext-studio/releases/latest):

- Apple Silicon: `Kontext-Studio-<version>-macOS-arm64.dmg`

The beta supports Apple Silicon Macs. Intel Macs can use the command-line
install below. The app bundles Python and the analysis packages; no toolchain is
required. The current build is an unsigned beta, so on first launch use System
Settings → Privacy & Security → Open Anyway. See the
[desktop guide](docs/user-guide/16-desktop-app.md).

### Command-line install

Kontext Studio is published to PyPI as the `kontext-studio` package. Each GitHub
Release also carries the matching wheel.

#### With `uv`

```bash
uv tool install kontext-studio
```

#### With `pip` in a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install kontext-studio
```

Then start the local server from the directory that holds your project:

```bash
kontext serve
```

This starts the local API server, serves the web app, and runs the embedded
local worker.

> Requires Python 3.12–3.14; 3.15 is not yet supported. Create the virtual
> environment with an explicit version (`python3.13 -m venv .venv`), because
> a bare `python3` may point at an unsupported release. `uv` picks a supported
> interpreter on its own. [Install `uv`](https://docs.astral.sh/uv/) if you
> prefer it.

Continue with the [user guide](https://docs.kontext.tech/user-guide/) to create
a project, connect data, and start a notebook.

## Documentation

- [User guide](https://docs.kontext.tech/user-guide/) — install, projects, data
  sources, notebooks, charts, Python, agents, and settings.
- [Developer guide](https://docs.kontext.tech/develop/) — architecture, package
  boundaries, and the generation and release workflows.
- [docs/](docs/README.md) — the Markdown sources published as
  [docs.kontext.tech](https://docs.kontext.tech).

## Development

This repository is a `pnpm` + `uv` workspace containing the app, TypeScript
packages, Python packages, and the committed generated API types and Pydantic
models.

```bash
pnpm install          # Node/TypeScript workspace dependencies
uv sync               # Python environment
pnpm run dev:local    # local API server and web app
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow and
[AGENTS.md](AGENTS.md) for the canonical architecture and conventions.

## Repository layout

- `app/`: React + Vite labs application (Ant Design v6).
- `ts/`: TypeScript packages published as `@kontext-tech/*`; `ts/schema` is the
  contract hub and `ts/schema/src/generated/` holds the committed API types.
- `py/`: Python packages built as `kontext-*`.
- `examples/`: development-only sample apps that consume the packages and are
  not distributed (e.g. the notebook demo).
- `tools/`: repo-level validators and local development helpers.
- `docs/`: user guide and developer reference sources published to
  [docs.kontext.tech](https://docs.kontext.tech).
- `docs-site/`: Astro Starlight site built from `docs/`; see
  [docs-site/README.md](docs-site/README.md).
- `scripts/`: build, test, image, and release helpers.

## License

Kontext Studio is released under the [MIT License](LICENSE). Third-party
dependencies and their licenses are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). See [TERMS.md](TERMS.md) for
the AI usage terms and [PRIVACY.md](PRIVACY.md) for the privacy notice.

<p align="center">
  <a href="https://www.producthunt.com/products/kontext?embed=true&amp;utm_source=badge-featured&amp;utm_medium=badge&amp;utm_campaign=badge-kontext-studio" target="_blank" rel="noopener noreferrer">
    <img alt="Kontext Studio - AI-Native Data Analysis Workspace | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id=1307287&amp;theme=light&amp;t=1794024018734">
  </a>
</p>
