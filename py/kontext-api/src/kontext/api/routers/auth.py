"""Token refresh/logoff endpoints for local mode."""

from __future__ import annotations

from typing import Any

import jwt as _jwt
from fastapi import APIRouter, HTTPException

from kontext.account import UserProfile, load_local_profile_by_subject
from kontext.runtime.local.auth import get_local_jwt_secret
from kontext.schema import AccessTokenResponse

from ..dependencies.local_auth import build_token_response

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/refresh")
def refresh(body: dict[str, Any] | None = None) -> AccessTokenResponse:
    """Exchange a valid refresh token for a new token pair.

    A missing or malformed token must never mint credentials from the ambient
    profile; that turned the endpoint into unauthenticated token issuance.
    """
    token = body.get("refresh_token") if isinstance(body, dict) else None
    if not token or not isinstance(token, str):
        raise HTTPException(status_code=401, detail="Refresh token required.")

    try:
        secret = get_local_jwt_secret()
        claims = _jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="kontext-platform",
            issuer="kontext-local",
        )
    except _jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token.") from exc

    sub = claims.get("sub")
    profile: UserProfile | None = load_local_profile_by_subject(sub) if sub else None
    if profile is None:
        raise HTTPException(status_code=401, detail="User not found.")

    return build_token_response(profile)


@router.post("/logoff", status_code=200)
def logoff(body: dict[str, Any] | None = None) -> None:
    """Local-mode logoff — stateless JWT, nothing to revoke."""
