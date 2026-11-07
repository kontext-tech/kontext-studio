# Kontext (local runtime)

Local server and CLI composition root for Kontext. It is the end-user
entry point: `kontext-studio` starts the local API server, serves the built React
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

This package is installed as part of the unified `kontext-studio` wheel. See the
repository [README](../../README.md#install) for the end-user install path.

For local development, sync the whole uv workspace from the repository root:

```bash
uv sync
```

`pyfiglet`, `rich`, and `python-dotenv` are regular dependencies of this package.

## Usage

```bash
# Start the local server and web app (default command)
kontext

# Same, via the explicit serve entry point
kontext serve

# Manage projects, import data, run jobs, and query
kontext project list
kontext project create --name "My project"
kontext project import --project <id> ./data
kontext job list
kontext job run <job> --project <id>
kontext query "select * from my_table limit 10" --project <id>
```

Run `kontext --help` or `kontext <subcommand> --help` for flags.

At startup the server prints the URL to open, including a per-run launch token
in the fragment (`http://127.0.0.1:8000/#token=...`). Open that URL rather than
the bare host: the API only issues credentials to callers presenting the
token. The app removes the token from the address bar after reading it, and
keeps the session in an HttpOnly cookie so file previews and new tabs work.
The latest token is in `~/.kontext/runtime/launch.token`; a per-port copy lives
in `launch-<port>.token` when several servers run.

## Architecture

```text
src/kontext/labs/
├── cli.py          # argparse entry points (kontext)
├── server.py       # FastAPI app: serves the UI and the local API surface
├── local_worker.py # Embedded local job worker
├── async_cleanup.py
├── telemetry.py
└── _app_dist/      # Built React app synced in at package time
```

The `kontext` console script points at `kontext.labs.cli`. Local routers reuse
the standard routers from
`kontext-api`; keep local routes compatible with that contract rather than
inventing separate local shapes.

## Development

```bash
# Run the whole local stack (API + app) from the repository root
pnpm run dev:local

# Package tests
uv run --package kontext-studio pytest py/kontext-labs/tests
```

## License

MIT. See the repository [LICENSE](../../LICENSE).
