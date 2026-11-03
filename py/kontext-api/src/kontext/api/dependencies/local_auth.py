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
from fastapi import Depends, HTTPException, Request
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

    1. A valid Bearer token always wins and is enforced: invalid, expired, or
       subject-less tokens are rejected, never silently replaced by the
       console auto-auth profile.
    2. Without credentials, the console auto-auth ambient profile is used so
       local CLI/first-launch flows work without a login round trip.

    ``get_auth_context`` and the router-facing ``get_current_user`` both
    funnel through this function, so token semantics cannot diverge per
    surface.
    """

    if credentials is not None:
        claims = decode_access_token(credentials.credentials)
        email: str | None = claims.get("email")
        if not email:
            return None  # surface as unauthenticated; callers raise 401
        profile = read_profile(email=email)
        if profile is None:
            return None
        return profile

    _ = request
    return read_profile()


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
