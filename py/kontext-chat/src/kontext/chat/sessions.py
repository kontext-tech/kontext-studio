"""Chat-session orchestration and authorization workflows."""

from __future__ import annotations

from uuid import UUID

from kontext.common.utils.datetime_utils import utc_now
from kontext.data import (
    ChatSessionDataService,
    ChatSessionNotFoundError,
)
from kontext.llm import resolve_model_selection
from kontext.schema import (
    ArtifactListResponse,
    ChatSessionModel,
    CreateChatSessionRequest,
    PaginatedChatSessionResponse,
    ProjectDailyTokenUsageResponse,
    ProjectTokenUsageResponse,
    TokenUsageDailyStatsModel,
    TokenUsageStatsModel,
    UpdateChatSessionRequest,
)

from .errors import ChatServiceError
from .models import ChatAccessContext


def _user_id_str(access_context: ChatAccessContext) -> str | None:
    return str(access_context.user_id) if access_context.user_id else None


def _enrich_usages_with_model_names(
    usages: list[TokenUsageStatsModel] | list[TokenUsageDailyStatsModel],
) -> None:
    """Fill canonical model id and display name on token-usage rows in place.

    Rows only persist the model *selection id*, so the display name is resolved
    from the model-connection store here. Connections may have been deleted since
    the usage was recorded; a missing entry is left as-is rather than failing.
    """
    from kontext.llm.model_connection_store import get_local_model_store

    store = get_local_model_store()
    if store is None:
        return

    resolved: dict[str, tuple[str | None, str | None]] = {}
    for usage in usages:
        selection_id = usage.model_selection_id
        if not selection_id:
            continue
        if selection_id not in resolved:
            connection = store.get_model_connection(selection_id)
            resolved[selection_id] = (
                (connection.canonical_model_id, connection.display_name)
                if connection is not None
                else (None, None)
            )
        canonical_model_id, display_name = resolved[selection_id]
        if usage.canonical_model_id is None and canonical_model_id:
            usage.canonical_model_id = canonical_model_id
        if display_name:
            usage.model_display_name = display_name


def _resolve_chat_session_data_service(
    *,
    project_id: UUID | str,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ChatSessionDataService:
    if chat_session_data_service is not None:
        return chat_session_data_service
    return ChatSessionDataService(project_id)


async def get_chat_session_resource(
    *,
    project_id: UUID,
    chat_session_id: UUID,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ChatSessionModel | None:
    if not project_id:
        return None

    service = _resolve_chat_session_data_service(
        project_id=project_id,
        chat_session_data_service=chat_session_data_service,
    )
    return await service.get_session_by_id_async(chat_session_id)


async def get_project_token_usage(
    project_id: UUID,
    *,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ProjectTokenUsageResponse:
    service = _resolve_chat_session_data_service(
        project_id=str(project_id),
        chat_session_data_service=chat_session_data_service,
    )
    usages = await service.get_project_token_usage_stats_async()
    _enrich_usages_with_model_names(usages)
    return ProjectTokenUsageResponse(
        project_id=str(project_id),
        usages=usages,
        total_inbound_tokens=sum(stat.inbound_tokens for stat in usages),
        total_outbound_tokens=sum(stat.outbound_tokens for stat in usages),
        total_tokens=sum(stat.inbound_tokens + stat.outbound_tokens for stat in usages),
    )


async def get_project_daily_token_usage(
    project_id: UUID,
    month: str | None,
    *,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ProjectDailyTokenUsageResponse:
    service = _resolve_chat_session_data_service(
        project_id=str(project_id),
        chat_session_data_service=chat_session_data_service,
    )
    usages = await service.get_project_daily_token_usage_stats_async(month)
    _enrich_usages_with_model_names(usages)
    resolved_month = month or utc_now().strftime("%Y-%m")
    return ProjectDailyTokenUsageResponse(
        project_id=str(project_id),
        month=resolved_month,
        usages=usages,
        total_inbound_tokens=sum(stat.inbound_tokens for stat in usages),
        total_outbound_tokens=sum(stat.outbound_tokens for stat in usages),
        total_tokens=sum(stat.inbound_tokens + stat.outbound_tokens for stat in usages),
    )


async def get_stream_chat_session(
    *,
    project_id: UUID | str,
    session_id: UUID | str,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ChatSessionModel:
    service = _resolve_chat_session_data_service(
        project_id=project_id,
        chat_session_data_service=chat_session_data_service,
    )
    session = await service.get_session_by_id_async(UUID(str(session_id)))
    if not session:
        raise ChatServiceError(404, f"Chat session {session_id} not found")
    return session


async def create_chat_session(
    *,
    request: CreateChatSessionRequest,
    access_context: ChatAccessContext,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ChatSessionModel:
    if not request.project_id:
        raise ChatServiceError(400, "Project ID is required")

    if access_context.project is None:
        raise ChatServiceError(400, "Project context required")

    if str(request.project_id) != str(access_context.project_id):
        raise ChatServiceError(403, "Project ID does not match authenticated context")

    service = _resolve_chat_session_data_service(
        project_id=access_context.project.id,
        chat_session_data_service=chat_session_data_service,
    )
    resolved_model_config = None
    if request.model_selection_id:
        try:
            resolved_model_config = (
                await resolve_model_selection(
                    selection_id=request.model_selection_id,
                    project_id=str(access_context.project.id),
                    auth_manager=access_context.auth_manager,
                )
            ).model_dump(exclude_none=True)
        except LookupError as exc:
            raise ChatServiceError(400, str(exc)) from exc

    return await service.create_session_async(
        request,
        _user_id_str(access_context),
        resolved_model_config=resolved_model_config,
    )


async def list_chat_sessions(
    *,
    project_id: UUID,
    filter_string: str | None,
    page_index: int,
    page_size: int,
    my_sessions_only: bool,
    access_context: ChatAccessContext,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> PaginatedChatSessionResponse:
    service = _resolve_chat_session_data_service(
        project_id=project_id,
        chat_session_data_service=chat_session_data_service,
    )
    owner_filter = access_context.user_id if my_sessions_only else access_context.effective_owner_id
    return await service.get_filtered_sessions_async(
        filter_string,
        page_index,
        page_size,
        str(owner_filter) if owner_filter else None,
    )


async def update_chat_session(
    *,
    chat_session_id: UUID,
    request: UpdateChatSessionRequest,
    access_context: ChatAccessContext,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ChatSessionModel:
    if not access_context.resource:
        raise ChatServiceError(404, "Chat session not found")

    service = _resolve_chat_session_data_service(
        project_id=access_context.project_id,
        chat_session_data_service=chat_session_data_service,
    )
    try:
        resolved_model_config = None
        if request.model_selection_id:
            try:
                resolved_model_config = (
                    await resolve_model_selection(
                        selection_id=request.model_selection_id,
                        project_id=str(access_context.project_id),
                        auth_manager=access_context.auth_manager,
                    )
                ).model_dump(exclude_none=True)
            except LookupError as exc:
                raise ChatServiceError(400, str(exc)) from exc

        return await service.update_session_async(
            chat_session_id,
            request,
            _user_id_str(access_context),
            resolved_model_config=resolved_model_config,
        )
    except ChatSessionNotFoundError as exc:
        raise ChatServiceError(404, "Chat session not found") from exc


async def delete_chat_session(
    *,
    chat_session_id: UUID,
    access_context: ChatAccessContext,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> None:
    if not access_context.resource:
        raise ChatServiceError(404, "Chat session not found")

    service = _resolve_chat_session_data_service(
        project_id=access_context.project_id,
        chat_session_data_service=chat_session_data_service,
    )
    try:
        await service.delete_session_async(chat_session_id, _user_id_str(access_context))
    except ChatSessionNotFoundError as exc:
        raise ChatServiceError(404, "Chat session not found") from exc


async def get_chat_session_artifacts(
    *,
    chat_session_id: UUID,
    project_id: UUID,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ArtifactListResponse:
    service = _resolve_chat_session_data_service(
        project_id=project_id,
        chat_session_data_service=chat_session_data_service,
    )
    artifacts = await service.get_session_artifacts_async(chat_session_id)
    return ArtifactListResponse(artifacts=artifacts)
