"""Launch token that gates local credential issuance.

The local server mints JWTs for the workspace owner. Without a second secret
that only the launcher knows, any browser page that can reach loopback (for
example through DNS rebinding) could ask the API for those tokens. The
launcher generates this token, passes it to the server through the environment,
and opens the UI with the token in the URL fragment so the browser can present
it once.
"""

from __future__ import annotations

import contextlib
import hmac
import os
import secrets
from pathlib import Path

from .private_files import read_private_file, write_private_file

LAUNCH_TOKEN_ENV = "KONTEXT_LOCAL_LAUNCH_TOKEN"
LAUNCH_TOKEN_FILENAME = "launch.token"


def _runtime_dir() -> Path:
    from .config import get_local_data_dir

    runtime_dir = get_local_data_dir() / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    with contextlib.suppress(OSError):
        os.chmod(runtime_dir, 0o700)
    return runtime_dir


def _token_file(port: int | None = None) -> Path:
    filename = f"launch-{port}.token" if port is not None else LAUNCH_TOKEN_FILENAME
    return _runtime_dir() / filename


def generate_launch_token() -> str:
    """Return a fresh, unguessable launch token."""
    return secrets.token_urlsafe(32)


def persist_launch_token(token: str, *, port: int | None = None) -> Path:
    """Write the token for *port* and update the latest-token file.

    The per-port file keeps a second server instance from invalidating the
    first instance's recovery token; the generic file is what direct
    ``uvicorn`` starts and the docs harness read.
    """
    content = token + "\n"
    target = _token_file(port)
    write_private_file(target, content)
    latest = _token_file()
    if target != latest:
        write_private_file(latest, content)
    return target


def get_launch_token() -> str:
    """Return the configured launch token, creating the file fallback if needed.

    The CLI supplies a per-run token through ``KONTEXT_LOCAL_LAUNCH_TOKEN``.
    Direct entrypoints (``uvicorn ...``) fall back to an owner-only file so the
    server still has a credential the user can read.
    """
    configured = os.getenv(LAUNCH_TOKEN_ENV, "").strip()
    if configured:
        return configured

    path = _token_file()
    existing = read_private_file(path)
    if existing is not None:
        return existing

    token = generate_launch_token()
    write_private_file(path, token + "\n", exclusive=True)
    persisted = read_private_file(path)
    if persisted is None:
        # Repair an empty file left by an interrupted create or external touch,
        # otherwise every call would generate a different, unpersisted token.
        write_private_file(path, token + "\n")
        persisted = read_private_file(path)
    return persisted or token


def verify_launch_token(presented: str | None) -> bool:
    """Return True when *presented* matches the process launch token."""
    if not presented:
        return False
    return hmac.compare_digest(
        presented.strip().encode("utf-8"), get_launch_token().encode("utf-8")
    )
