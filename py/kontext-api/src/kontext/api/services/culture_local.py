"""Local-mode culture data shared by host and native culture endpoints."""

from __future__ import annotations

from kontext.schema import CultureInfoModel


def get_cultures_service() -> list[CultureInfoModel]:
    return [
        CultureInfoModel(
            code="en",
            display_name="English",
            native_name="English",
            is_right_to_left=False,
        ),
        CultureInfoModel(
            code="zh",
            display_name="Chinese",
            native_name="中文",
            is_right_to_left=False,
        ),
    ]
