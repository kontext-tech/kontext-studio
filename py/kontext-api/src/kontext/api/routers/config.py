"""
Config API endpoints for local mode. Kontext host config is also available at
/host/config.
"""

from __future__ import annotations

from fastapi import APIRouter

from kontext.runtime.profiles import get_runtime_profile

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/site")
def get_site_config():
    return get_runtime_profile().get_site_config()
