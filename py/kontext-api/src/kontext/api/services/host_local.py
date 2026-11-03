"""Local host-contract services shared below the /host router."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from kontext.account import UserProfile, is_default_local_profile, read_profile
from kontext.project.local import seed_default_local_project
from kontext.runtime.local.config import get_local_access_token_ttl_seconds
from kontext.runtime.profiles import get_runtime_profile
from kontext.schema import AccessTokenResponse, SiteConfigResponse, UserWithRolesModel

from ..dependencies.local_auth import (
    build_token_response,
    profile_to_model,
    resolve_local_user,
)

HostMode = Literal["local", "hosted"]
_CONSOLE_AUTO_AUTH_ENV = "KONTEXT_LOCAL_CONSOLE_AUTO_AUTH"


class _HostPayloadModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class HostAuthBootstrapResponse(_HostPayloadModel):
    mode: HostMode
    authenticated: bool
    login_url: str | None = None
    logout_url: str | None = None
    access_token: AccessTokenResponse | None = None
    user: UserWithRolesModel | None = None
    project_roles: dict[str, list[str]]
    permissions: list[str]
    expires_at: str | None = None


class HostAuthMeResponse(_HostPayloadModel):
    mode: HostMode
    authenticated: bool
    user: UserWithRolesModel | None
    project_roles: dict[str, list[str]]
    permissions: list[str]
    expires_at: str | None = None


def get_host_mode() -> HostMode:
    return "local" if get_runtime_profile().is_local else "hosted"


def get_local_profile_service() -> UserProfile | None:
    return read_profile()


def ensure_local_project_state_service() -> None:
    if get_local_profile_service() is None:
        return
    seed_default_local_project()


def _should_auto_auth_default_local_profile() -> bool:
    return os.getenv(_CONSOLE_AUTO_AUTH_ENV, "").lower() == "true"


def build_host_auth_bootstrap_response() -> HostAuthBootstrapResponse:
    if not get_runtime_profile().is_local:
        return HostAuthBootstrapResponse(
            mode="hosted",
            authenticated=False,
            login_url=os.getenv("KONTEXT_PLATFORM_LOGIN_URL", "/login"),
            logout_url=os.getenv("KONTEXT_PLATFORM_LOGOUT_URL", "/logout"),
            access_token=None,
            user=None,
            project_roles={},
            permissions=[],
            expires_at=None,
        )

    profile = get_local_profile_service()
    if profile is None:
        return HostAuthBootstrapResponse(
            mode="local",
            authenticated=False,
            login_url=None,
            logout_url=None,
            access_token=None,
            user=None,
            project_roles={},
            permissions=[],
            expires_at=None,
        )

    if is_default_local_profile(profile) and not _should_auto_auth_default_local_profile():
        return HostAuthBootstrapResponse(
            mode="local",
            authenticated=False,
            login_url=None,
            logout_url=None,
            access_token=None,
            user=None,
            project_roles={},
            permissions=[],
            expires_at=None,
        )

    user = profile_to_model(profile)
    return HostAuthBootstrapResponse(
        mode="local",
        authenticated=True,
        login_url=None,
        logout_url=None,
        access_token=build_token_response(profile),
        user=user,
        project_roles=user.project_roles or {},
        permissions=user.permission_claims or [],
        expires_at=_token_expiry_iso(),
    )


async def build_host_auth_me_response(
    credentials: HTTPAuthorizationCredentials | None,
) -> HostAuthMeResponse:
    if get_runtime_profile().is_local and credentials is None:
        profile = get_local_profile_service()
        if profile is None or is_default_local_profile(profile):
            return HostAuthMeResponse(
                mode="local",
                authenticated=False,
                user=None,
                project_roles={},
                permissions=[],
                expires_at=None,
            )
    else:
        profile = await resolve_local_user(None, credentials)
        if profile is None:
            raise HTTPException(status_code=401, detail="Not authenticated.")

    user = profile_to_model(profile)
    return HostAuthMeResponse(
        mode=get_host_mode(),
        authenticated=True,
        user=user,
        project_roles=user.project_roles or {},
        permissions=user.permission_claims or [],
        expires_at=_token_expiry_iso() if get_runtime_profile().is_local else None,
    )


def get_host_config_service() -> SiteConfigResponse:
    return get_runtime_profile().get_site_config()


def _token_expiry_iso() -> str:
    return (datetime.now(UTC) + timedelta(seconds=get_local_access_token_ttl_seconds())).isoformat()
