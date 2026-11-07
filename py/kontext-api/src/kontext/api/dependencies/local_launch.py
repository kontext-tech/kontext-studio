"""Launch-token dependency for local credential-issuing endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, Request

from kontext.runtime.local.launch_token import verify_launch_token

from .local_auth import LOCAL_SESSION_COOKIE, decode_access_token

LAUNCH_TOKEN_HEADER = "X-Kontext-Launch-Token"

_MISSING_TOKEN_DETAIL = (
    "Missing or invalid local launch token. Open the URL printed by "
    "`kontext serve` (direct server starts: see "
    "~/.kontext/runtime/launch.token)."
)


def _session_cookie_is_valid(request: Request) -> bool:
    token = request.cookies.get(LOCAL_SESSION_COOKIE)
    if not token:
        return False
    try:
        decode_access_token(token)
    except HTTPException:
        return False
    return True


def require_local_launch_token(
    request: Request,
    x_kontext_launch_token: Annotated[str | None, Header(alias=LAUNCH_TOKEN_HEADER)] = None,
) -> None:
    """Require the launcher secret on a local-composed app.

    A valid local session cookie also counts: it can only exist after a
    launch-token bootstrap, and it lets a new tab or bookmark re-bootstrap
    without the URL fragment.
    """
    if not getattr(request.app.state, "local_auth_required", False):
        return
    if verify_launch_token(x_kontext_launch_token):
        return
    if _session_cookie_is_valid(request):
        return
    raise HTTPException(status_code=401, detail=_MISSING_TOKEN_DETAIL)
