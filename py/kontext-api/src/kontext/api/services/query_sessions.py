"""API adapters for query-session application services."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request

from kontext.query import (
    QueryServiceError,
    create_query_session,
    delete_query_session,
    get_query_session_resource,
    initialize_session_async,
    initialize_session_sync,
    list_query_sessions,
    update_query_session,
)
from kontext.schema import (
    CreateQuerySessionRequest,
    ExecutionRunModel,
    PaginatedListOfQuerySessionModel,
    QuerySessionModel,
    SessionInitRequest,
    SessionInitResponse,
    UpdateQuerySessionRequest,
)

from ..dependencies import AuthContext, extract_path_param
from ..transport_adapters import (
    build_query_access_context,
    domain_error_to_http,
)


async def get_query_session_resource_service(
    request: Request, auth_context: AuthContext[QuerySessionModel]
) -> QuerySessionModel | None:
    session_id = extract_path_param(request, "session_id")
    if not session_id:
        return None

    return await get_query_session_resource(
        project_id=auth_context.project_id,
        session_id=UUID(str(session_id)),
    )


async def create_query_session_service(
    *,
    request: CreateQuerySessionRequest,
    auth_context: AuthContext[Any],
) -> QuerySessionModel:
    try:
        return await create_query_session(
            request=request,
            access_context=build_query_access_context(auth_context),
        )
    except QueryServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def initialize_session_service(
    *,
    request: SessionInitRequest,
    auth_context: AuthContext[Any],
    queue_client,
) -> SessionInitResponse:
    try:
        return await initialize_session_sync(
            request=request,
            access_context=build_query_access_context(auth_context),
            queue_client=queue_client,
        )
    except QueryServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def initialize_session_async_service(
    *,
    request: SessionInitRequest,
    auth_context: AuthContext[Any],
    queue_client,
) -> ExecutionRunModel:
    try:
        return await initialize_session_async(
            request=request,
            access_context=build_query_access_context(auth_context),
            queue_client=queue_client,
        )
    except QueryServiceError as exc:
        raise domain_error_to_http(exc) from exc


def list_query_sessions_service(
    *,
    auth_context: AuthContext[Any],
    my_sessions_only: bool,
    page_index: int,
    page_size: int,
) -> PaginatedListOfQuerySessionModel:
    try:
        return list_query_sessions(
            access_context=build_query_access_context(auth_context),
            my_sessions_only=my_sessions_only,
            page_index=page_index,
            page_size=page_size,
        )
    except QueryServiceError as exc:
        raise domain_error_to_http(exc) from exc


def update_query_session_service(
    *,
    session_id: UUID,
    request: UpdateQuerySessionRequest,
    auth_context: AuthContext[QuerySessionModel],
) -> QuerySessionModel:
    try:
        return update_query_session(
            session_id=session_id,
            request=request,
            access_context=build_query_access_context(auth_context, resource=auth_context.resource),
        )
    except QueryServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def delete_query_session_service(
    *,
    session_id: UUID,
    project_id: UUID,
    auth_context: AuthContext[QuerySessionModel],
    queue_client,
) -> None:
    _ = project_id
    try:
        await delete_query_session(
            session_id=session_id,
            access_context=build_query_access_context(auth_context, resource=auth_context.resource),
            queue_client=queue_client,
        )
    except QueryServiceError as exc:
        raise domain_error_to_http(exc) from exc
