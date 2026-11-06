"""
Kontext Console CLI entry points.

  kontext-labs-serve  [--port PORT] [--host HOST] [--dist-dir PATH] [--open]
  kontext-labs        serve | project list | project create | project import
                         | import | job run | job list

Starts the local HTTP + WebSocket server that hosts the React UI and exposes the
same API contract as the cloud deployment.  Subcommands let you manage
projects, import data, run jobs, and execute SQL without starting the full server.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any
from urllib.parse import quote

from kontext.runtime.local.hosts import (
    browser_host,
    configure_allowed_hosts,
    is_loopback_host,
)

from .sqlite_compat import ensure_supported_sqlite

# ── Helpers ──────────────────────────────────────────────────────────────────


def _print_startup_banner() -> None:
    """Render a lightweight ASCII banner for the local server."""
    try:
        import pyfiglet
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()
        ascii_art = pyfiglet.figlet_format("Kontext", font="slant")
        console.print(
            Panel(
                Text(ascii_art, style="bold cyan"),
                title="Kontext",
                subtitle="Local Console",
                border_style="bright_blue",
                padding=(0, 1),
            )
        )
    except Exception:
        print("KONTEXT")
        print("Kontext | Local Console")


def _init_engine(lake_path: str | None = None) -> Any:
    """Initialize local storage engine and SQLite database for local mode."""
    if lake_path:
        os.environ["KONTEXT_LAKE_PATH"] = lake_path

    # Local mode should always use SQLite unless the caller already supplied a
    # SQLite override. This prevents inherited cloud/Postgres env settings from
    # leaking into local startup.
    current_db_url = os.getenv("PROJECT_DB_URL", "")
    if not current_db_url.startswith("sqlite:///"):
        from kontext.runtime.local.config import configure_local_database_url

        configure_local_database_url()
    from kontext.data.database import Base
    from kontext.data.database import get_engine as get_db_engine

    # Import model modules for their SQLAlchemy metadata registrations.
    importlib.import_module("kontext.account")
    importlib.import_module("kontext.data.models")

    Base.metadata.create_all(get_db_engine())

    from kontext.storage.engine.local import LocalStorageEngine

    return LocalStorageEngine()


def _get_project_index() -> list[dict[str, Any]]:
    """Return all non-deleted projects from the SQLite database."""
    from sqlalchemy import select

    from kontext.data.database import get_sync_db_session
    from kontext.data.models import Project

    with get_sync_db_session() as session:
        rows = session.execute(select(Project).where(Project.is_deleted.is_(False))).scalars().all()
        return [
            {
                "id": str(r.id),
                "project_code": r.project_code or "",
                "project_name": r.project_name or "",
            }
            for r in rows
        ]


def _resolve_project_id(project_arg: str | None) -> str:
    """Resolve a project ID from *project_arg* or fall back to the first project."""
    if project_arg:
        return project_arg
    index = _get_project_index()
    if not index:
        print("No projects found. Create one first with `kontext-labs project create <name>`.")
        sys.exit(1)
    return index[0]["id"]


# ── serve (original entry-point) ────────────────────────────────────────────


def _add_serve_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("serve", help="Start the local Kontext server (UI + API).")
    p.add_argument(
        "--host",
        default=os.getenv("KONTEXT_HOST", "127.0.0.1"),
        help="Bind address (default: 127.0.0.1)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("KONTEXT_PORT", "8000")),
        help="Port (default: 8000)",
    )
    p.add_argument("--dist-dir", default=None, help="Path to the built React app (app/dist).")
    p.add_argument(
        "--open",
        action="store_true",
        default=False,
        help="Open the browser after start.",
    )
    p.add_argument("--lake-path", default=None, help="Lake directory (default: .kontext/ in cwd).")
    p.add_argument(
        "--reload",
        action="store_true",
        default=False,
        help="Enable uvicorn auto-reload.",
    )
    p.add_argument(
        "--no-worker",
        action="store_true",
        default=False,
        help="Do not start the local job worker process alongside the server.",
    )
    p.set_defaults(func=_cmd_serve)


class _WorkerSupervisor:
    """Owns a child ``kontext-labs worker`` process for the life of ``serve``.

    The worker runs in its own process/session, so a hung or crashed job can
    never wedge the API process. Stopping the supervisor stops the worker. The
    supervisor also watches the worker and restarts it if it exits unexpectedly,
    so a crash does not silently stop all background job processing.
    """

    _MAX_RESTART_ATTEMPTS = 5
    _RESTART_BACKOFF_SECONDS = 1.0
    _WATCH_INTERVAL_SECONDS = 1.0

    def __init__(self) -> None:
        self._process: subprocess.Popen[Any] | None = None
        self._stopping = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self._restarts = 0

    def start(self) -> None:
        if os.getenv("KONTEXT_LOCAL_WORKER_ENABLED", "true").lower() != "true":
            print("Local job worker disabled (KONTEXT_LOCAL_WORKER_ENABLED is not true).")
            return

        self._spawn()
        if os.getenv("KONTEXT_LOCAL_WORKER_WATCHDOG", "true").lower() == "true":
            self._watch_thread = threading.Thread(
                target=self._watch, name="local-worker-watchdog", daemon=True
            )
            self._watch_thread.start()

    def _spawn(self) -> None:
        env = dict(os.environ)
        kwargs: dict[str, Any] = {}
        if os.name == "nt":  # pragma: no cover - Windows-only process flags
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True

        self._process = subprocess.Popen(
            [sys.executable, "-m", "kontext.labs.local_worker"],
            env=env,
            **kwargs,
        )
        print(f"Local job worker started (pid={self._process.pid}).")

    def _watch(self) -> None:
        """Restart the worker on unexpected exit, with a bounded retry budget."""
        while not self._stopping.wait(self._WATCH_INTERVAL_SECONDS):
            process = self._process
            if process is None or process.poll() is None:
                continue
            if self._stopping.is_set():
                return
            exit_code = process.returncode
            self._restarts += 1
            if self._restarts > self._MAX_RESTART_ATTEMPTS:
                print(
                    "Local job worker exited repeatedly "
                    f"(last exit code {exit_code}); not restarting. "
                    "Background jobs will not run until the server is restarted.",
                    file=sys.stderr,
                )
                return
            print(
                f"Local job worker exited unexpectedly (exit code {exit_code}); "
                f"restarting (attempt {self._restarts}/{self._MAX_RESTART_ATTEMPTS}).",
                file=sys.stderr,
            )
            self._stopping.wait(self._RESTART_BACKOFF_SECONDS)
            if self._stopping.is_set():
                return
            with contextlib.suppress(Exception):
                self._spawn()

    def stop(self) -> None:
        self._stopping.set()
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return
        with contextlib.suppress(Exception):
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(Exception):
                process.kill()


def _cmd_serve(args: argparse.Namespace) -> None:
    # This entrypoint is the local composition; make the profile explicit
    # before any settings are read or child processes are spawned.
    os.environ["KONTEXT_LOCAL_MODE"] = "true"

    # Fail before starting the worker or opening a database: SQLite 3.51.0/3.51.1
    # can deadlock under the local multi-process WAL workload.
    try:
        ensure_supported_sqlite()
    except RuntimeError as exc:
        raise SystemExit(f"❌ {exc}") from None

    if args.dist_dir:
        os.environ["KONTEXT_DIST_DIR"] = args.dist_dir
    if args.lake_path:
        os.environ["KONTEXT_LAKE_PATH"] = args.lake_path

    # A default signal death (SIGHUP on terminal close) skips the ``finally``
    # below, so the job worker outlives the server and pollers of every past
    # generation then race for jobs. uvicorn installs its own SIGTERM/SIGINT
    # handlers inside run() and stops cleanly; SIGHUP is left unhandled, so
    # turn it into an exception before uvicorn runs. SIGKILL cannot be
    # intercepted: worker startup reaps orphans as the safety net.

    def _sighup_to_exit(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    with contextlib.suppress(AttributeError, ValueError, OSError):
        signal.signal(signal.SIGHUP, _sighup_to_exit)

    from kontext.runtime.local.launch_token import (
        LAUNCH_TOKEN_ENV,
        generate_launch_token,
        persist_launch_token,
    )

    # A per-run token proves the browser was opened by this server rather than
    # by a page that reached loopback through DNS rebinding. The worker process
    # inherits it through the environment; the file lets a user recover a lost
    # launch URL without restarting.
    launch_token = os.getenv(LAUNCH_TOKEN_ENV, "").strip() or generate_launch_token()
    os.environ[LAUNCH_TOKEN_ENV] = launch_token
    token_file = persist_launch_token(launch_token, port=args.port)

    configure_allowed_hosts(args.host)

    _init_engine(getattr(args, "lake_path", None))

    import uvicorn

    _print_startup_banner()

    url = f"http://{browser_host(args.host)}:{args.port}"
    launch_url = f"{url}/#token={quote(launch_token, safe='')}"
    print(
        "\n"
        "============================================================\n"
        f"  Kontext local: {url}\n"
        f"  Open with token: {launch_url}\n"
        f"  Token file: {token_file}\n"
        "============================================================\n"
    )
    if not is_loopback_host(args.host):
        print(
            "Warning: the server is bound to a non-loopback address without "
            "TLS. Requests are accepted only for this machine's interface "
            "addresses; anyone who can reach them can attempt requests.",
            file=sys.stderr,
        )

    if args.open:
        import time
        import webbrowser

        def _open_browser() -> None:
            time.sleep(1.5)
            webbrowser.open(launch_url)

        threading.Thread(target=_open_browser, daemon=True).start()

    supervisor = _WorkerSupervisor()
    if not getattr(args, "no_worker", False):
        supervisor.start()

    try:
        if args.reload:
            uvicorn.run(
                "kontext.labs.server:create_app",
                factory=True,
                host=args.host,
                port=args.port,
                reload=True,
                log_level="info",
            )
            return

        from kontext.labs.server import create_app

        app = create_app(dist_dir=args.dist_dir)
        uvicorn.run(app, host=args.host, port=args.port, reload=False, log_level="info")
    finally:
        supervisor.stop()


# ── worker ──────────────────────────────────────────────────────────────────


def _add_worker_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "worker",
        help="Run the local job worker process (usually started by `serve`).",
    )
    p.set_defaults(func=_cmd_worker)


def _cmd_worker(args: argparse.Namespace) -> None:
    del args
    from kontext.labs.local_worker import run_worker_process

    run_worker_process()


# ── project subcommands ─────────────────────────────────────────────────────


def _add_project_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("project", help="Manage local projects.")
    sp = p.add_subparsers(dest="project_cmd")

    # project list
    ls = sp.add_parser("list", help="List projects in the local lake.")
    ls.add_argument("--lake-path", default=None, help="Lake directory.")
    ls.set_defaults(func=_cmd_project_list)

    # project create
    cr = sp.add_parser("create", help="Create a new local project.")
    cr.add_argument("name", help="Project name.")
    cr.add_argument("--code", default=None, help="Short code (defaults to slugified name).")
    cr.add_argument("--lake-path", default=None, help="Lake directory.")
    cr.set_defaults(func=_cmd_project_create)

    # project import
    imp = sp.add_parser("import", help="Import files into a project's data directory.")
    imp.add_argument("files", nargs="+", help="File paths to import (CSV, Parquet, JSON, etc.).")
    imp.add_argument("--project", default=None, help="Project ID (defaults to first project).")
    imp.add_argument(
        "--subdir",
        default="raw",
        help="Subdirectory under project data (default: raw).",
    )
    imp.add_argument("--lake-path", default=None, help="Lake directory.")
    imp.set_defaults(func=_cmd_project_import)


def _cmd_project_list(args: argparse.Namespace) -> None:
    _init_engine(getattr(args, "lake_path", None))
    index = _get_project_index()

    if not index:
        print("No projects found.")
        return

    # Simple table output
    print(f"{'ID':<40} {'Code':<16} {'Name'}")
    print("-" * 80)
    for entry in index:
        pid = entry.get("id", "?")
        code = entry.get("project_code", "")
        name = entry.get("project_name", "")
        print(f"{pid:<40} {code:<16} {name}")


def _cmd_project_create(args: argparse.Namespace) -> None:
    import re

    from kontext.account import read_profile
    from kontext.project.local import create_project_service
    from kontext.schema import AccessLevel, CreateProjectRequest

    _init_engine(getattr(args, "lake_path", None))

    profile = read_profile()
    if profile is None:
        print(
            "No local profile found. Run `kontext-labs serve` once to complete setup.",
            file=sys.stderr,
        )
        sys.exit(1)

    code = args.code or re.sub(r"[^a-z0-9]+", "-", args.name.lower()).strip("-")
    result = create_project_service(
        CreateProjectRequest(
            project_name=args.name,
            project_code=code,
            project_description="",
            access_level=AccessLevel.PRIVATE,
        ),
        profile,
    )
    print(f"Created project '{result.project_name}' ({result.id})")


def _cmd_project_import(args: argparse.Namespace) -> None:
    engine = _init_engine(getattr(args, "lake_path", None))
    project_id = _resolve_project_id(args.project)

    target_dir = Path(engine.get_project_data_path(project_id, args.subdir))
    target_dir.mkdir(parents=True, exist_ok=True)

    imported = 0
    for src in args.files:
        src_path = Path(src)
        if not src_path.is_file():
            print(f"Skipping (not a file): {src}", file=sys.stderr)
            continue
        dest = target_dir / src_path.name
        shutil.copy2(src_path, dest)
        print(f"  {src_path.name} → {dest.relative_to(engine._root)}")
        imported += 1

    print(f"\nImported {imported} file(s) into project {project_id}.")


# ── import (top-level convenience) ────────────────────────────────────────────


def _add_import_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "import", help="Import files into a project (shorthand for 'project import')."
    )
    p.add_argument("files", nargs="+", help="File paths to import.")
    p.add_argument("--project", default=None, help="Project ID (defaults to first project).")
    p.add_argument(
        "--subdir",
        default="raw",
        help="Subdirectory under project data (default: raw).",
    )
    p.add_argument("--lake-path", default=None, help="Lake directory.")
    p.set_defaults(func=_cmd_project_import)


# ── job subcommands ──────────────────────────────────────────────────────────


def _add_job_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("job", help="Manage and run jobs.")
    sp = p.add_subparsers(dest="job_cmd")

    # job list
    ls = sp.add_parser("list", help="List available job types.")
    ls.set_defaults(func=_cmd_job_list)

    # job run
    run = sp.add_parser("run", help="Execute a job synchronously.")
    run.add_argument(
        "job_type", help="Job type identifier (e.g. 'python.jobs.DocumentIndexingJob')."
    )
    run.add_argument("--project", default=None, help="Project ID (defaults to first project).")
    run.add_argument("--params", default="{}", help="Job parameters as a JSON string.")
    run.add_argument("--lake-path", default=None, help="Lake directory.")
    run.set_defaults(func=_cmd_job_run)


def _cmd_job_list(args: argparse.Namespace) -> None:
    from kontext.jobs.job_registry import PythonJobRegistry

    registry = PythonJobRegistry()
    jobs = registry.get_all_jobs()

    if not jobs:
        print("No registered job types found.")
        return

    print(f"{'Job Type':<50} {'Name':<25} {'Category'}")
    print("-" * 100)
    for meta in sorted(jobs, key=lambda m: m.type):
        cat = meta.category.value if meta.category else ""
        print(f"{meta.type:<50} {meta.name:<25} {cat}")


def _cmd_job_run(args: argparse.Namespace) -> None:
    _init_engine(getattr(args, "lake_path", None))
    project_id = _resolve_project_id(args.project)

    try:
        params = json.loads(args.params)
    except json.JSONDecodeError as exc:
        print(f"Invalid --params JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(_run_job(project_id, args.job_type, params))


async def _run_job(project_id: str, job_type: str, params: dict[str, Any]) -> None:
    """Instantiate and execute a job directly (one-shot CLI execution)."""
    from kontext.jobs.job_context import IJobExecutionService
    from kontext.jobs.job_registry import PythonJobRegistry

    registry = PythonJobRegistry()
    job_instance = registry.create_job_instance(job_type)
    if job_instance is None:
        print(f"Unknown job type: {job_type}", file=sys.stderr)
        print("Run `kontext-labs job list` to see available types.")
        sys.exit(1)

    from kontext.runtime.providers.local import LocalRuntimeProvider
    from kontext.schema import LogLevel

    runtime_provider = LocalRuntimeProvider(project_id=project_id)

    # Minimal IJobExecutionService that prints logs to stdout.
    class _CliJobExecService(IJobExecutionService):
        async def update_job_run_status_async(
            self, run_id, status, error_message=None, result_data=None
        ):
            pass

        async def update_job_run_worker_async(self, run_id, worker):
            pass

        async def update_job_run_progress_async(self, run_id, progress):
            pass

        async def add_job_run_log_async(self, run_id, level, message, data=None):
            prefix = level.value if isinstance(level, LogLevel) else str(level)
            print(f"[{prefix}] {message}")

    from uuid import uuid4

    from kontext.jobs.job_context import JobContext

    meta = registry.get_job_metadata(job_type)
    context = JobContext(
        job_run_id=str(uuid4()),
        project_id=project_id,
        job_name=meta.name if meta else job_type,
        job_execution_service=_CliJobExecService(),
        parameters=params,
        runtime_provider=runtime_provider,
    )

    result = await job_instance.execute(context, params)
    status = "SUCCESS" if result.success else "FAILED"
    print(f"\n--- {status}: {result.message} ---")
    if result.data:
        print(json.dumps(result.data, indent=2, default=str))


# ── Top-level CLI ────────────────────────────────────────────────────────────


def cli(argv: list[str] | None = None) -> None:
    """Unified CLI entry point: ``kontext-labs``."""
    parser = argparse.ArgumentParser(
        prog="kontext-labs",
        description="Kontext — local-first data & AI workspace.",
    )
    subs = parser.add_subparsers(dest="command")

    _add_serve_parser(subs)
    _add_worker_parser(subs)
    _add_project_parser(subs)
    _add_import_parser(subs)
    _add_job_parser(subs)

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


# ── Legacy entry-point (``kontext-labs-serve``) ─────────────────────────────


def serve() -> None:
    """CLI entry point: ``kontext-labs-serve``.

    Boots a uvicorn server running the local Kontext FastAPI application.
    Pass ``--open`` to launch the browser automatically. Flag parsing and
    execution live in the unified ``serve`` subcommand so the two entry points
    cannot drift.
    """
    cli(["serve", *sys.argv[1:]])
