"""Local authentication and authorization helpers for the runtime layer."""

from __future__ import annotations

import base64
import secrets
from datetime import UTC, datetime
from pathlib import Path

from kontext.project.local_data import get_local_project_roles_for_user
from kontext.schema import UserType, UserWithRolesModel


def _get_key_file() -> Path:
    from .config import get_local_data_dir

    return get_local_data_dir() / "local.key"


def get_local_jwt_secret() -> str:
    """Return or create the persistent local signing secret."""
    key_file = _get_key_file()
    if key_file.exists():
        return key_file.read_text(encoding="utf-8").strip()

    raw = secrets.token_bytes(32)
    secret = base64.urlsafe_b64encode(raw).decode("utf-8")
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(secret + "\n", encoding="utf-8")
    return secret


def get_local_permission_claims() -> list[str]:
    """Return the canonical local-mode permission claims."""
    from kontext.auth import (
        ChatSessionPermissions,
        EventPermissions,
        FilePermissions,
        JobPermissions,
        ProjectPermissions,
        QuerySessionPermissions,
    )

    return [
        ChatSessionPermissions.CREATE,
        ChatSessionPermissions.READ,
        ChatSessionPermissions.UPDATE,
        ChatSessionPermissions.DELETE,
        QuerySessionPermissions.CREATE,
        QuerySessionPermissions.READ,
        QuerySessionPermissions.UPDATE,
        QuerySessionPermissions.DELETE,
        QuerySessionPermissions.EXECUTE,
        FilePermissions.CREATE,
        FilePermissions.READ,
        FilePermissions.UPDATE,
        FilePermissions.DELETE,
        JobPermissions.CREATE,
        JobPermissions.READ,
        JobPermissions.UPDATE,
        JobPermissions.DELETE,
        JobPermissions.EXECUTE,
        EventPermissions.READ,
        EventPermissions.CREATE,
        ProjectPermissions.READ,
        ProjectPermissions.UPDATE,
    ]


def get_local_project_roles(user_id: str) -> dict[str, list[str]]:
    """Return local project-role assignments for the supplied user."""
    return get_local_project_roles_for_user(user_id)


def build_local_user_with_roles(profile) -> UserWithRolesModel:
    """Build the frontend-facing user model for local mode."""
    return UserWithRolesModel(
        id=profile.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        email=profile.email,
        preferred_language_code=profile.preferred_language_code,
        is_enabled=True,
        is_deleted=False,
        lockout_enabled=False,
        lockout_end=None,
        is_locked_out=False,
        email_confirmed=True,
        user_type=UserType.USER,
        roles=["local_admin"],
        permission_claims=get_local_permission_claims(),
        project_roles=get_local_project_roles(profile.id),
        date_register=datetime.now(UTC),
    )
