"""Request guard for the loopback-only local server.

Browsers do not enforce same-origin policy for a page whose DNS name resolves
to ``127.0.0.1`` (DNS rebinding), so the local server must validate the Host
header itself. State-changing requests additionally validate Origin, which
stops cross-site form/fetch posts even when the request never reaches CORS.
"""

from __future__ import annotations

import os

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from kontext.runtime.local.hosts import (
    ALLOWED_HOSTS_ENV,
    LOOPBACK_HOSTNAMES,
    normalize_host,
)

_REJECTION_DETAIL = "Request rejected: local server host validation failed."


def allowed_hostnames() -> set[str]:
    """Return loopback names plus any explicitly configured extra hosts."""
    allowed = set(LOOPBACK_HOSTNAMES)
    for entry in os.getenv(ALLOWED_HOSTS_ENV, "").split(","):
        hostname = normalize_host(entry)
        if hostname:
            allowed.add(hostname)
    return allowed


def _origin_is_allowed(origin: str, allowed: set[str]) -> bool:
    hostname = normalize_host(origin)
    return hostname is not None and hostname in allowed


class LocalRequestGuard:
    """Reject non-loopback Host headers and foreign Origins in local mode."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        allowed = allowed_hostnames()

        hostname = normalize_host(headers.get("host"))
        if hostname is None or hostname not in allowed:
            await self._reject(scope, receive, send)
            return

        origin = headers.get("origin")
        if origin and not _origin_is_allowed(origin, allowed):
            await self._reject(scope, receive, send)
            return

        await self.app(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        response = JSONResponse(status_code=403, content={"detail": _REJECTION_DETAIL})
        await response(scope, receive, send)
