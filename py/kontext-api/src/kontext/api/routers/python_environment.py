"""Managed Python environment endpoints for local mode.

Mounted only when the active profile advertises
:attr:`~kontext.common.SiteFeature.PYTHON_ENVIRONMENT` (see
``register_local_platform_routers``).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from kontext.account import UserProfile
from kontext.common import SiteFeature
from kontext.runtime import (
    get_managed_python_environment_info,
    prepare_managed_python_environment,
)
from kontext.schema import PythonEnvironmentInfo

from ..dependencies import require_site_feature
from ..dependencies.local_auth import get_current_user

router = APIRouter(
    prefix="/account",
    tags=["Account"],
    dependencies=[require_site_feature(SiteFeature.PYTHON_ENVIRONMENT)],
)

_CURRENT_USER_DEP = Depends(get_current_user)


@router.get("/python-environment")
async def get_python_environment(
    current_user: UserProfile = _CURRENT_USER_DEP,
) -> PythonEnvironmentInfo:
    del current_user
    # Listing installed packages shells out to ``pip list``; keep it off the loop.
    return await asyncio.to_thread(get_managed_python_environment_info)


@router.post("/python-environment/prepare")
async def prepare_python_environment(
    current_user: UserProfile = _CURRENT_USER_DEP,
) -> PythonEnvironmentInfo:
    del current_user
    # Preparing the environment creates a venv and pip-installs packages, which
    # can take minutes; never run that on the event loop thread.
    return await asyncio.to_thread(prepare_managed_python_environment)
