# Local operations and troubleshooting

How to run the local stack, find its credentials, and diagnose the failures
people hit most often. Variables are defined in the
[environment reference](environment.md); the security rationale is in the
[security model](security-model.md).

## What runs

| Process | Default | Started by | Notes |
| --- | --- | --- | --- |
| API (uvicorn) | `127.0.0.1:8000` | `kontext serve` | Serves the API and, when a build exists, the React app. |
| Vite dev app | `127.0.0.1:8002` | `pnpm run dev:local` | Separate from the API; API URL is injected. |
| Job worker | Child process | `kontext serve` | Polls queued runs from SQLite; `--no-worker` disables it. |
| Python kernels | Child processes | Worker | One-shot run kernels and persistent session kernels. |
| Project database | `~/.kontext/kontext.db` | API/worker | SQLite in local mode. |
| Lake/storage | `~/.kontext` | API/worker | `KONTEXT_LAKE_PATH` or `--lake-path` overrides the lake root. |

## Start and stop

Repository checkout:

```bash
pnpm run dev:local     # API on :8000, Vite on :8002
pnpm run dev:app       # app only; expects an API
```

Installed package:

```bash
kontext serve
kontext serve --open                 # open the tokenized URL
kontext serve --host 127.0.0.1 --port 8000
kontext serve --lake-path ./workspace
kontext serve --no-worker            # API only
kontext serve --reload               # uvicorn reload
```

`Ctrl-C` stops the server and its worker. The worker supervisor restarts a
crashed worker up to five times; `KONTEXT_LOCAL_WORKER_ENABLED=false` or
`--no-worker` turns it off.

## Launch URL and token

`kontext serve` prints the URL to open, the latest token file, and a
tokenized URL of the form `http://127.0.0.1:8000/#token=...`. The dev launcher
prints the same banner again once both services answer and writes the app URL
to `~/.kontext/runtime/launch.url` (plus `launch-8002.url`).

Recovery files:

| File | Contents |
| --- | --- |
| `~/.kontext/runtime/launch.url` | Latest tokenized app URL. |
| `~/.kontext/runtime/launch.token` | Latest launch token (owner-only). |
| `~/.kontext/runtime/launch-<port>.token` | Token for a specific API port. |

Open the printed URL rather than the bare host. Use the same origin as the app
(`localhost` vs `127.0.0.1` are different origins for `sessionStorage`). The app
reads the fragment, strips it from the address bar, and keeps the token in
`sessionStorage` for the tab. A new tab can re-bootstrap with the HttpOnly
session cookie.

Restarting the server rotates the launch token, so open the new printed URL.
Previously issued JWTs remain valid until they expire or the signing key is
rotated. To revoke all local sessions, stop the server, delete
`~/.kontext/local.key`, and restart (or rotate the `KONTEXT_JWT_SECRET_KEY` /
`JWT_SECRET_KEY` value if one is set).

Several instances share the same `~/.kontext` by default. Use the per-port
`launch-<port>.token` for recovery, and override `HOME`, `PROJECT_DB_URL`, or
`--lake-path` if the instances must not share a database/storage root.

## Common failures

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `401 Missing or invalid local launch token` | Bare URL, an old tab, or a token from a previous run | Open the printed tokenized URL; `cat ~/.kontext/runtime/launch.url`; restart and use the new URL. |
| `403 Request rejected: local server host validation failed` | Non-loopback hostname, reverse proxy, or DNS rebinding attempt | Use `localhost`/`127.0.0.1`, or add the hostname to `KONTEXT_ALLOWED_HOSTS`. |
| Login and setup pages bounce | A stale stored token or a mismatched profile/setup state | Open the newly printed URL; hard-reload; clear site data for the origin if needed. |
| Address already in use | API or Vite port conflict | Change `--port`/`KONTEXT_PORT` or `VITE_PORT`; keep the Vite origin in `CORS_ALLOWED_ORIGINS` (8002/8003/8006 by default). |
| SPA returns 503 | No built app | `pnpm --filter @kontext-tech/app build`, or pass `--dist-dir`. |
| Jobs stay `Queued` | Worker disabled, crashed, or not inherited the database | Check `KONTEXT_LOCAL_WORKER_ENABLED`, start without `--no-worker`, and inspect the worker log. |
| SQLite lock or startup timeout | Two processes initializing, or an unsupported SQLite build | Stop both, check `~/.kontext/local-init.lock`, restart one server; SQLite 3.51.0/3.51.1 is rejected. |
| Kernel failures | Managed Python environment or repeated infrastructure errors | Check the worker log and `KONTEXT_PYTHON_MAX_CONSECUTIVE_KERNEL_FAILURES`; a dead session kernel restarts with a fresh namespace. |
| File access denied | The path is outside managed storage and `KONTEXT_ALLOWED_PATHS` | Add the directory to `KONTEXT_ALLOWED_PATHS` or copy the file into managed storage. |
| Model provider errors | Missing/invalid key or endpoint | Set the provider variables in `.env.local`; see [model provider configuration](../ai/model-provider-configuration.md). |
| CORS error in the dev app | API and app origins disagree | Use the documented ports, or extend `CORS_ALLOWED_ORIGINS`; keep credentials out of a `*` wildcard. |

## Diagnostics

```bash
# Is the API up?
curl -s http://127.0.0.1:8000/health

# Does the launch token work?
curl -s -H "X-Kontext-Launch-Token: $(cat ~/.kontext/runtime/launch.token)" \
  http://127.0.0.1:8000/host/auth/bootstrap

# Who holds the port?
lsof -nP -iTCP:8000 -sTCP:LISTEN

# What is on disk?
ls -la ~/.kontext ~/.kontext/runtime
sqlite3 ~/.kontext/kontext.db '.tables'
```

Logs go to the terminal that started the server. Use `KONTEXT_LOG_LEVEL` and
`KONTEXT_LOG_FORMAT` for more (or more structured) output; `OTEL_*` exports
traces to a collector when configured. Avoid `DEBUG` with real provider keys in
shared logs.

## Reset and backup

1. Stop the server (and the worker).
2. Copy or move `~/.kontext` to back up the profile, database, storage, and
   runtime tokens.
3. Delete only what you intend to lose:
   - `~/.kontext/kontext.db` — projects, runs, chats, connections.
   - `~/.kontext/storage` — managed files and artifacts.
   - `~/.kontext/local.key` — invalidates every issued local token when no env
     JWT secret is configured; rotate the env secret instead when one is set.
   - `~/.kontext/runtime` — launch URLs/tokens; regenerated on start.
4. Restart. A fresh workspace seeds the placeholder profile and project and
   offers setup again.

Do not delete `local-init.lock` while a server is starting; investigate the
process holding it first.

## Related documentation

- [Security model](security-model.md) — why these controls exist.
- [Environment reference](environment.md) — every variable and default.
- [Install and start](../user-guide/01-install-and-start.md) — user-facing setup.
- [Python package boundaries](python-package-boundaries.md) — worker/kernel
  topology and confinement.
