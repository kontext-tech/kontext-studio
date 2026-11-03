"""
Local-mode auth resolution shared by routers, services, and dependencies.

Lives under ``dependencies/`` because service modules import it too; routers
must never be imported from the service layer.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import jwt as _jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kontext.account import UserProfile, read_profile
from kontext.runtime.local.auth import (
    build_local_user_with_roles,
    get_local_jwt_secret,
)
from kontext.runtime.local.config import (
    get_local_access_token_ttl_seconds,
    get_local_refresh_token_ttl_seconds,
)
from kontext.schema import AccessTokenResponse, UserWithRolesModel

logger = logging.getLogger(__name__)

LOCAL_SESSION_COOKIE = "kontext_local_session"

_ROLE_CLAIM = "http://schemas.microsoft.com/ws/2008/06/identity/claims/role"
_bearer_scheme = HTTPBearer(auto_error=False)
_BEARER_DEP = Depends(_bearer_scheme)


def mint_local_tokens(profile: UserProfile) -> tuple[str, str]:
    """Return ``(access_token, refresh_token)`` signed with the local key."""
    now = int(datetime.now(UTC).timestamp())
    secret = get_local_jwt_secret()
    access_ttl = get_local_access_token_ttl_seconds()
    refresh_ttl = get_local_refresh_token_ttl_seconds()
    access_payload = {
        "jwt_ver": 2,
        "sub": profile.id,
        "email": profile.email,
        "name": f"{profile.first_name} {profile.last_name or ''}".strip(),
        "user_type": "User",
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + access_ttl,
        "iss": "kontext-local",
        "aud": "kontext-platform",
        _ROLE_CLAIM: ["local_admin"],
    }
    refresh_payload = {
        "sub": profile.id,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + refresh_ttl,
        "iss": "kontext-local",
        "aud": "kontext-platform",
    }
    access_token = _jwt.encode(access_payload, secret, algorithm="HS256")
    refresh_token = _jwt.encode(refresh_payload, secret, algorithm="HS256")
    return access_token, refresh_token


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a local access token; raises HTTPException on failure."""
    try:
        secret = get_local_jwt_secret()
        return _jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="kontext-platform",
            issuer="kontext-local",
        )
    except _jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token has expired.") from exc
    except _jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc


async def resolve_local_user(
    request: Request | None,
    credentials: HTTPAuthorizationCredentials | None,
) -> UserProfile | None:
    """Single policy for local identity resolution.

    A valid Bearer token — or the HttpOnly local session cookie, which exists
    only after a launch-token bootstrap — is required. Invalid, expired, or
    subject-less tokens are rejected. There is no ambient-profile fallback, so
    an unauthenticated request can never act as the workspace owner.

    ``get_auth_context`` and the router-facing ``get_current_user`` both
    funnel through this function, so token semantics cannot diverge per
    surface.
    """

    if credentials is not None:
        return _profile_from_token(credentials.credentials)
    if request is not None:
        cookie = request.cookies.get(LOCAL_SESSION_COOKIE)
        if cookie:
            return _profile_from_token(cookie)
    return None


def _profile_from_token(token: str) -> UserProfile | None:
    claims = decode_access_token(token)
    email: str | None = claims.get("email")
    if not email:
        return None  # surface as unauthenticated; callers raise 401
    return read_profile(email=email)


def set_local_session_cookie(
    response: Response,
    access_token: AccessTokenResponse | None,
) -> None:
    """Mirror the local session into an HttpOnly cookie for browser loads.

    ``<img>``, notebook embeds, and direct download links cannot attach an
    Authorization header; the cookie gives them the same identity while
    remaining unreadable to scripts and restricted to same-site requests.
    """
    if access_token is None:
        response.delete_cookie(LOCAL_SESSION_COOKIE, path="/")
        return
    response.set_cookie(
        LOCAL_SESSION_COOKIE,
        access_token.access_token,
        httponly=True,
        samesite="strict",
        path="/",
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = _BEARER_DEP,
) -> UserProfile:
    """Router-facing local user dependency (strict 401 surface)."""
    profile = await resolve_local_user(request, credentials)
    if profile is None:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Not authenticated.")
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return profile


def profile_to_model(profile: UserProfile) -> UserWithRolesModel:
    return build_local_user_with_roles(profile)


def build_token_response(profile: UserProfile) -> AccessTokenResponse:
    access_token, refresh_token = mint_local_tokens(profile)
    return AccessTokenResponse(
        token_type="Bearer",
        access_token=access_token,
        expires_in=get_local_access_token_ttl_seconds(),
        refresh_token=refresh_token,
    )
