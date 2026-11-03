"""
Culture API endpoints for local mode. Kontext host culture is also available at
/host/culture.
"""

from __future__ import annotations

from fastapi import APIRouter

from kontext.schema import CultureInfoModel

from ..services.culture_local import get_cultures_service

router = APIRouter(prefix="/culture", tags=["Culture"])


@router.get("")
def get_cultures() -> list[CultureInfoModel]:
    return get_cultures_service()
