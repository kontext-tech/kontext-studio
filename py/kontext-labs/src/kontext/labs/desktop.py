"""Desktop-managed launch mode.

The Tauri shell starts this module as a child process, reads one readiness
line from stdout, and points its webview at the URL. The server remains the
only API entry point; this module only adds a deterministic port, a
machine-readable handshake, and a shutdown path tied to the shell.
"""

from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import sys
import threading
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import quote

from kontext.runtime.local.hosts import browser_host, is_loopback_host

from .parent_watchdog import parent_pid_from_env, start_parent_watchdog
from .sqlite_compat import ensure_supported_sqlite

READY_MARKER = "@@KONTEXT_READY@@"
DEFAULT_PREFERRED_PORT = 47800

_READY_POLL_SECONDS = 0.05


def run_desktop(args: Any) -> None:
    """Run the local server in the shape the desktop shell expects."""
    os.environ["KONTEXT_LOCAL_MODE"] = "true"

    try:
        ensure_supported_sqlite()
    except RuntimeError as exc:
        raise SystemExit(f"❌ {exc}") from None

    if getattr(args, "dist_dir", None):
        os.environ["KONTEXT_DIST_DIR"] = args.dist_dir
    if getattr(args, "lake_path", None):
        os.environ["KONTEXT_LAKE_PATH"] = args.lake_path

    host = getattr(args, "host", "127.0.0.1")
    if not is_loopback_host(host):
        raise SystemExit("Desktop mode requires a loopback bind address.")

    from kontext.runtime.local.hosts import configure_allowed_hosts
    from kontext.runtime.local.launch_token import (
        LAUNCH_TOKEN_ENV,
        generate_launch_token,
    )

    configure_allowed_hosts(host)

    from .cli import _init_engine, _WorkerSupervisor

    _init_engine(getattr(args, "lake_path", None))

    token = os.getenv(LAUNCH_TOKEN_ENV, "").strip() or generate_launch_token()
    os.environ[LAUNCH_TOKEN_ENV] = token

    supervisor = _WorkerSupervisor(quiet=True)
    if not getattr(args, "no_worker", False):
        supervisor.start()

    parent_pid = getattr(args, "parent_pid", None) or parent_pid_from_env()
    try:
        _run_server(args, token, host=host, parent_pid=parent_pid)
    finally:
        supervisor.stop()


def _run_server(args: Any, token: str, *, host: str, parent_pid: int | None) -> None:
    import uvicorn

    from .server import create_app

    preferred_port = getattr(args, "preferred_port", DEFAULT_PREFERRED_PORT)
    ports = [_choose_port(host, preferred_port)]
    if ports[0] != 0:
        # One retry on an ephemeral port when the preferred bind races another
        # process between our probe and uvicorn's bind.
        ports.append(0)

    for port in ports:
        app = create_app(dist_dir=getattr(args, "dist_dir", None))
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)

        if parent_pid is not None:

            def _request_shutdown(target: Any = server) -> None:
                target.should_exit = True

            start_parent_watchdog(_request_shutdown, watch_stdin=True)

        threading.Thread(
            target=_announce_when_ready,
            args=(server, token, host),
            name="kontext-desktop-ready",
            daemon=True,
        ).start()

        with _graceful_signal_handlers(server):
            server.run()
        if getattr(server, "started", False):
            return

    raise SystemExit("Could not start the Kontext desktop server.")


@contextlib.contextmanager
def _graceful_signal_handlers(server: Any) -> Iterator[None]:
    """Keep uvicorn's shutdown from re-raising the default signal.

    After a graceful shutdown uvicorn restores the original handlers and
    re-raises SIGINT/SIGTERM. With the default disposition that terminates the
    process before our ``finally`` runs. Installing a handler that only flips
    ``should_exit`` turns the re-raise into a no-op.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def _handle(_signum: int, _frame: object) -> None:
        server.should_exit = True

    original: dict[int, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(ValueError, OSError):
            original[sig] = signal.signal(sig, _handle)
    try:
        yield
    finally:
        for sig, handler in original.items():
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, handler)


def _announce_when_ready(server: Any, token: str, host: str) -> None:
    while not server.started and not server.should_exit:
        time.sleep(_READY_POLL_SECONDS)
    if not server.started:
        return

    port = _bound_port(server)
    url = f"http://{browser_host(host)}:{port}"
    launch_url = f"{url}/#token={quote(token, safe='')}"

    from kontext.runtime.local.launch_token import persist_launch_token

    persist_launch_token(token, port=port)

    payload = {
        "schema": 1,
        "event": "ready",
        "pid": os.getpid(),
        "port": port,
        "url": url,
        "launchUrl": launch_url,
    }
    print(f"{READY_MARKER}{json.dumps(payload)}", flush=True)


def _bound_port(server: Any) -> int:
    for listener in getattr(server, "servers", None) or []:
        for sock in getattr(listener, "sockets", None) or []:
            with contextlib.suppress(OSError):
                return int(sock.getsockname()[1])
    raise RuntimeError("uvicorn did not expose a bound socket")


def _choose_port(host: str, preferred: int) -> int:
    if preferred <= 0:
        return 0
    return preferred if _port_available(host, preferred) else 0


def _port_available(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


if __name__ == "__main__":
    # Not the public entry point; ``python -m kontext.labs desktop`` goes
    # through the CLI parser. This guard only makes direct module execution
    # fail loudly instead of starting an unconfigured server.
    print("Use `kontext desktop` or `python -m kontext.labs desktop`.", file=sys.stderr)
    raise SystemExit(2)
