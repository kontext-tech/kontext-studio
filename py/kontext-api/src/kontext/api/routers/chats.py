"""
Combined AI chat and chat session routers.

This module merges `ai.py` and `chat_sessions.py` into a single `chats` router
mounted under `/ai` to simplify routing and client generation.
"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse

from kontext.agentic.chat_handler import (
    DEFAULT_CHAT_AGENT_WORKFLOW,
)
from kontext.auth import (
    AuthenticationError,
    ChatSessionPermissions,
    FilePermissions,
)
from kontext.common import NotFoundError
from kontext.common.messaging import IQueueClient
from kontext.schema import (
    ArtifactListResponse,
    ChatMessage,
    ChatRequest,
    ChatSessionModel,
    ChatUploadPreparationStatus,
    CreateChatSessionRequest,
    ExecutePythonScriptRequest,
    PaginatedChatSessionResponse,
    ProjectDailyTokenUsageResponse,
    ProjectFeature,
    ProjectTokenUsageResponse,
    PythonExecutionResult,
    SeedChatAttachmentContextRequest,
    StartChatUploadPreparationResponse,
    UpdateChatSessionRequest,
)

from ..dependencies import (
    CHAT_SESSION_ID_PATH,
    FILTER_QUERY,
    MY_OWNED_ONLY_QUERY,
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_ID_QUERY,
    QUEUE_CLIENT_DEP,
    RUN_ID_PATH,
    AuthContext,
    create_auth_dependency,
    get_client_ip,
)
from ..services.chats import (
    create_chat_session_service,
    delete_chat_session_service,
    execute_chat_session_python_service,
    get_chat_session_artifacts_service,
    get_chat_session_resource_service,
    get_chat_upload_preparation_status_service,
    get_filtered_chat_sessions_service,
    get_project_daily_token_usage_service,
    get_project_token_usage_service,
    seed_chat_attachment_context_service,
    start_chat_upload_preparation_service,
    stream_chat_session_service,
    update_chat_session_service,
)
from ..services.runtime import build_authorized_runtime_provider
from ..transport_adapters import build_query_access_context

logger = logging.getLogger(__name__)


router = APIRouter()


# Create authorization dependency for AI chat endpoints
CHAT_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.CHAT],
    required_permissions=[ChatSessionPermissions.CREATE],
)

# Create authorization dependencies for AI chat session endpoints
CHAT_SESSION_CREATE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.CHAT],
    required_permissions=[ChatSessionPermissions.CREATE],
)
CHAT_SESSION_LIST_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.CHAT],
    required_permissions=[ChatSessionPermissions.READ],
    allow_owner=True,
)
CHAT_UPLOAD_PREPARATION_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.CHAT],
    required_permissions=[ChatSessionPermissions.CREATE, FilePermissions.CREATE],
)

ChatPreparationFileUpload = Annotated[
    list[UploadFile], File(description="Files to prepare before starting chat")
]
ALLOW_OVERWRITE_QUERY: bool = Query(
    default=False,
    alias="allowOverwrite",
    description=(
        "If true, replace existing files with the same name when preparing chat attachments."
    ),
)


# ------------------------- AI Chat Endpoint -------------------------------
@router.get(
    "/chat/usage",
    response_model=ProjectTokenUsageResponse,
    operation_id="GetProjectTokenUsage",
)
async def get_project_token_usage(
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_LIST_AUTH,
):
    """
    Get token usage statistics for the project,
    aggregated by month and model.
    """
    _ = auth_context
    return await get_project_token_usage_service(project_id)


@router.get(
    "/chat/usage/daily",
    response_model=ProjectDailyTokenUsageResponse,
    operation_id="GetProjectDailyTokenUsage",
)
async def get_project_daily_token_usage(
    project_id: PROJECT_ID_QUERY,
    month: str | None = None,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_LIST_AUTH,
):
    """
    Get daily token usage statistics for the project for a specific month.
    Defaults to the current month.
    """
    _ = auth_context
    return await get_project_daily_token_usage_service(project_id, month)


@router.post("/chat/stream", operation_id="AIChatStream", response_model=None)
async def ai_chat_stream(
    request: ChatRequest,
    fastapi_request: Request,
    auth_context: AuthContext[ChatSessionModel] = CHAT_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
) -> StreamingResponse:
    logger.info(f"AI chat stream requested for project {request.project_id}")

    try:
        stream = await stream_chat_session_service(
            request=request,
            headers=dict(fastapi_request.headers),
            auth_context=auth_context,
            queue_client=queue_client,
        )
        return StreamingResponse(
            stream,
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked",
            },
        )

    except PermissionError as e:
        logger.warning(f"Forbidden access: {e}")
        raise HTTPException(status_code=403, detail=str(e)) from None
    except NotFoundError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from None
    except ValueError as e:
        logger.warning(f"Bad request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from None
    except AuthenticationError as e:
        logger.warning(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail=str(e)) from None


# ----------------------- Chat Session Endpoints ---------------------------


async def get_chat_session_resource(
    request: Request, auth_context: AuthContext[ChatSessionModel]
) -> ChatSessionModel | None:
    return await get_chat_session_resource_service(request, auth_context)


# Auth dependencies that resolve the chat session resource for ownership checks
CHAT_SESSION_READ_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.CHAT],
    required_permissions=[ChatSessionPermissions.READ],
    resource_getter=get_chat_session_resource,
    allow_owner=True,
)
CHAT_SESSION_UPDATE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.CHAT],
    required_permissions=[ChatSessionPermissions.UPDATE],
    resource_getter=get_chat_session_resource,
    allow_owner=True,
)
CHAT_SESSION_DELETE_AUTH = create_auth_dependency(
    required_features=[ProjectFeature.CHAT],
    required_permissions=[ChatSessionPermissions.DELETE],
    resource_getter=get_chat_session_resource,
    allow_owner=True,
)


@router.post(
    "/chat/session",
    response_model=ChatSessionModel,
    status_code=status.HTTP_201_CREATED,
    operation_id="CreateChatSession",
)
async def create_chat_session(
    request: CreateChatSessionRequest,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_CREATE_AUTH,
):
    return await create_chat_session_service(request=request, auth_context=auth_context)


@router.post(
    "/chat/upload-preparations",
    response_model=StartChatUploadPreparationResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="StartChatUploadPreparation",
)
async def start_chat_upload_preparation(
    files: ChatPreparationFileUpload,
    http_request: Request,
    project_id: PROJECT_ID_QUERY,
    allow_overwrite: bool = ALLOW_OVERWRITE_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_UPLOAD_PREPARATION_AUTH,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    if not auth_context.project:
        raise HTTPException(status_code=400, detail="Project context required")

    try:
        return await start_chat_upload_preparation_service(
            project_id=project_id,
            files=files,
            owner_id=auth_context.user_id if auth_context.user else None,
            ip_address=get_client_ip(http_request),
            triggered_by=auth_context.trigger_actor if auth_context.user else None,
            queue_client=queue_client,
            allow_overwrite=allow_overwrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/chat/upload-preparations/{runId}",
    response_model=ChatUploadPreparationStatus,
    operation_id="GetChatUploadPreparationStatus",
)
async def get_chat_upload_preparation_status(
    run_id: Annotated[UUID, RUN_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_UPLOAD_PREPARATION_AUTH,
):
    _ = auth_context
    return await get_chat_upload_preparation_status_service(
        project_id=project_id,
        run_id=run_id,
    )


@router.post(
    "/chat/session/{chatSessionId}/attachment-context",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="SeedChatAttachmentContext",
)
async def seed_chat_attachment_context(
    chat_session_id: Annotated[UUID, CHAT_SESSION_ID_PATH],
    request: SeedChatAttachmentContextRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_UPDATE_AUTH,
):
    _ = auth_context
    await seed_chat_attachment_context_service(
        chat_session_id=chat_session_id,
        project_id=project_id,
        request=request,
    )


@router.get(
    "/chat/session/filtered",
    response_model=PaginatedChatSessionResponse,
    operation_id="GetFilteredChatSessions",
)
async def get_filtered_chat_sessions(
    project_id: PROJECT_ID_QUERY,
    filter: FILTER_QUERY = None,
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    my_sessions_only: MY_OWNED_ONLY_QUERY = False,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_LIST_AUTH,
):
    return await get_filtered_chat_sessions_service(
        project_id=project_id,
        filter_string=filter,
        page_index=page_index,
        page_size=page_size,
        my_sessions_only=my_sessions_only,
        auth_context=auth_context,
    )


@router.get(
    "/chat/session/{chatSessionId}",
    response_model=ChatSessionModel,
    operation_id="GetChatSession",
)
def get_chat_session(
    chat_session_id: Annotated[UUID, CHAT_SESSION_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_READ_AUTH,
):
    chat_session = auth_context.resource
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return chat_session


@router.post(
    "/chat/session/{chatSessionId}/execute-python",
    response_model=PythonExecutionResult,
    operation_id="ExecutePythonScript",
)
async def execute_python_script(
    chat_session_id: Annotated[UUID, CHAT_SESSION_ID_PATH],
    request: ExecutePythonScriptRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_UPDATE_AUTH,
):
    return await execute_chat_session_python_service(
        chat_session_id=chat_session_id,
        project_id=project_id,
        code=request.code,
        auth_context=auth_context,
    )


@router.get(
    "/chat/session/{chatSessionId}/messages",
    response_model=list[ChatMessage],
    operation_id="GetChatSessionMessages",
)
async def get_chat_session_messages(
    chat_session_id: Annotated[UUID, CHAT_SESSION_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    queue_client: IQueueClient | None = QUEUE_CLIENT_DEP,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_READ_AUTH,
):
    """Retrieve all chat messages for a session to restate it in the UI."""
    chat_session = auth_context.resource
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    try:
        # Validate project is loaded
        if not auth_context.project:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Project context not loaded",
            )

        runtime_provider = build_authorized_runtime_provider(
            project_id=str(project_id),
            access_context=build_query_access_context(auth_context),
            queue_client=queue_client,
        )

        # Read persisted harness-session messages without materializing a
        # runnable agent (no model client, tool bindings, or credentials).
        messages = await DEFAULT_CHAT_AGENT_WORKFLOW.load_session_messages(
            ChatRequest(project_id=str(project_id), session_id=str(chat_session_id), message=""),
            runtime_provider,
            auth_context.project,
            str(auth_context.user_id),
            session=chat_session,
        )

        # Apply the same tool-call visibility/detail policy used by streaming events.
        # - Non-local: only user-visible tool calls, with args/results stripped.
        # - Local dev: include all tool calls with full details.
        from kontext.agent.client_policy import (
            sanitize_chat_messages_for_client,
        )

        return sanitize_chat_messages_for_client(messages)

    except NotFoundError as e:
        logger.warning(f"Resource not found: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from None
    except ValueError as e:
        logger.warning(f"Bad request: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from None
    except AuthenticationError as e:
        logger.warning(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail=str(e)) from None


@router.put(
    "/chat/session/{chatSessionId}",
    response_model=ChatSessionModel,
    operation_id="UpdateChatSession",
)
async def update_chat_session(
    chat_session_id: Annotated[UUID, CHAT_SESSION_ID_PATH],
    request: UpdateChatSessionRequest,
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_UPDATE_AUTH,
):
    return await update_chat_session_service(
        chat_session_id=chat_session_id,
        request=request,
        project_id=project_id,
        auth_context=auth_context,
    )


@router.delete(
    "/chat/session/{chatSessionId}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="DeleteChatSession",
)
async def delete_chat_session(
    chat_session_id: Annotated[UUID, CHAT_SESSION_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_DELETE_AUTH,
):
    await delete_chat_session_service(
        chat_session_id=chat_session_id,
        project_id=project_id,
        auth_context=auth_context,
    )


@router.get(
    "/chat/session/{chatSessionId}/artifacts",
    response_model=ArtifactListResponse,
    operation_id="GetChatSessionArtifacts",
)
async def get_chat_session_artifacts(
    chat_session_id: Annotated[UUID, CHAT_SESSION_ID_PATH],
    project_id: PROJECT_ID_QUERY,
    auth_context: AuthContext[ChatSessionModel] = CHAT_SESSION_READ_AUTH,
):
    """Retrieve all artifacts for a chat session."""
    _ = auth_context
    return await get_chat_session_artifacts_service(
        chat_session_id=chat_session_id,
        project_id=project_id,
    )
