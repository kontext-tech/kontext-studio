"""Local profile endpoints used by Kontext local mode."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from kontext.account import UserProfile, write_profile
from kontext.schema import UpdateUserProfileRequest, UserWithRolesModel

from ..dependencies.local_auth import get_current_user, profile_to_model

router = APIRouter(prefix="/account", tags=["Account"])

_CURRENT_USER_DEP = Depends(get_current_user)


@router.get("/info")
def account_info(
    current_user: UserProfile = _CURRENT_USER_DEP,
) -> UserWithRolesModel:
    return profile_to_model(current_user)


@router.post("/profile")
def update_profile(
    request: UpdateUserProfileRequest, current_user: UserProfile = _CURRENT_USER_DEP
) -> UserWithRolesModel:
    updated = UserProfile(
        id=current_user.id,
        first_name=request.first_name,
        last_name=request.last_name,
        email=current_user.email,
        preferred_language_code=request.preferred_language_code
        or current_user.preferred_language_code,
    )
    write_profile(None, updated)
    return profile_to_model(updated)
