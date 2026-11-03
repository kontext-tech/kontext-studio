"""Project statistics helpers."""

from __future__ import annotations

from uuid import UUID

from kontext.data.chat_session_service import ChatSessionDataService
from kontext.schema import ProjectStatsModel

from .service import ProjectService


async def get_project_stats(project_id: UUID) -> ProjectStatsModel:
    service = ProjectService(project_id=project_id)
    stats = await service.get_project_stats_async()

    chat_service = ChatSessionDataService(project_id=str(project_id))
    usages = await chat_service.get_project_token_usage_stats_async()

    stats.total_tokens_inbound = sum(u.inbound_tokens for u in usages)
    stats.total_tokens_outbound = sum(u.outbound_tokens for u in usages)

    return stats
