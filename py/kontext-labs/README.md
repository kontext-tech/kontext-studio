# Kontext (local runtime)

Local server and CLI composition root for Kontext. It is the end-user
entry point: `kontext-labs` starts the local API server, serves the built React
app, and runs an embedded local job worker.

## Features

- **Local server**: hosts the React app and exposes the same API contract as
  the cloud deployment.
- **Local-first runtime**: SQLite plus the local filesystem, with in-process
  execution. No external database or object store required.
- **CLI subcommands**: manage projects, import data, run jobs, and execute SQL
  without starting the full server.
- **Rich UI**: terminal banners and tables via `rich` (ASCII art via `pyfiglet`).

## Installation

This package is installed as part of the unified `kontext-labs` wheel. See the
repository [README](../../README.md#install) for the end-user install path.

For local development, sync the whole uv workspace from the repository root:

```bash
uv sync
```

`pyfiglet`, `rich`, and `python-dotenv` are regular dependencies of this package.

## Usage

```bash
# Start the local server and web app (default command)
kontext-labs

# Same, via the explicit serve entry point
kontext-labs-serve

# Manage projects, import data, run jobs, and query
kontext-labs project list
kontext-labs project create --name "My project"
kontext-labs project import --project <id> ./data
kontext-labs job list
kontext-labs job run <job> --project <id>
kontext-labs query "select * from my_table limit 10" --project <id>
```

Run `kontext-labs --help` or `kontext-labs <subcommand> --help` for flags.

## Architecture

```text
src/kontext/labs/
├── cli.py          # argparse entry points (kontext-labs, kontext-labs-serve)
├── server.py       # FastAPI app: serves the UI and the local API surface
├── local_worker.py # Embedded local job worker
├── async_cleanup.py
├── telemetry.py
└── _app_dist/      # Built React app synced in at package time
```

The `kontext-labs` and `kontext-labs-serve` console scripts both point at
`kontext.labs.cli`. Local routers reuse the standard routers from
`kontext-api`; keep local routes compatible with that contract rather than
inventing separate local shapes.

## Development

```bash
# Run the whole local stack (API + app) from the repository root
pnpm run dev:local

# Package tests
uv run --package kontext-labs pytest py/kontext-labs/tests
```

## License

MIT. See the repository [LICENSE](../../LICENSE).
