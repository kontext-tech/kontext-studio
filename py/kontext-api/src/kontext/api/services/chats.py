"""API adapters for chat-session application services."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Mapping
from uuid import UUID

from fastapi import HTTPException, Request

from kontext.agentic.chat_handler import DEFAULT_CHAT_AGENT_WORKFLOW
from kontext.catalog import CatalogManagementService
from kontext.chat import (
    ChatRuntimeProviderFactoryProtocol,
    ChatServiceError,
    ChatStreamContext,
)
from kontext.chat import (
    create_chat_session as create_chat_session_impl,
)
from kontext.chat import (
    delete_chat_session as delete_chat_session_impl,
)
from kontext.chat import (
    execute_chat_session_python_script as execute_chat_session_python_impl,
)
from kontext.chat import (
    get_chat_session_artifacts as get_chat_session_artifacts_impl,
)
from kontext.chat import (
    get_chat_session_resource as get_chat_session_resource_impl,
)
from kontext.chat import (
    get_project_daily_token_usage as get_project_daily_token_usage_impl,
)
from kontext.chat import (
    get_project_token_usage as get_project_token_usage_impl,
)
from kontext.chat import (
    get_stream_chat_session as get_stream_chat_session_impl,
)
from kontext.chat import (
    list_chat_sessions as list_chat_sessions_impl,
)
from kontext.chat import (
    stream_chat_session as stream_chat_session_impl,
)
from kontext.chat import (
    update_chat_session as update_chat_session_impl,
)
from kontext.common.constants import DataLakeConstants
from kontext.common.jobs.trigger_actor import chat_session_actor
from kontext.common.jobs.trigger_actor import system_actor as make_system_actor
from kontext.common.messaging import IQueueClient
from kontext.common.protocols import RuntimeProviderProtocol
from kontext.data import (
    ChatSessionDataService,
    ExecutionRunContextDataService,
    JobRunDataService,
)
from kontext.file import create_file_service, infer_file_type
from kontext.jobs import (
    ExecutionRunService,
    extract_workflow_projection_metadata,
)
from kontext.jobs.runs import map_job_run_status
from kontext.schema import (
    ArtifactListResponse,
    ChatAttachmentContext,
    ChatAttachmentContextFile,
    ChatAttachmentContextTable,
    ChatRequest,
    ChatSessionModel,
    ChatUploadPreparationFailure,
    ChatUploadPreparationStatus,
    ChatUploadPreparationStep,
    CreateChatSessionRequest,
    PaginatedChatSessionResponse,
    ProjectDailyTokenUsageResponse,
    ProjectTokenUsageResponse,
    PythonExecutionResult,
    SeedChatAttachmentContextRequest,
    StartChatUploadPreparationResponse,
    TriggerActorModel,
    UpdateChatSessionRequest,
)

from ..dependencies import AuthContext, extract_path_param
from ..transport_adapters import (
    build_chat_access_context,
    build_query_access_context,
    domain_error_to_http,
)
from .agent_run_tracking import EXECUTION_RUN_TRACKER
from .chat_upload_preparation import (
    CHAT_UPLOAD_PREPARATION_WORKFLOW_KEY,
    ChatUploadPreparationMetadata,
    as_optional_uuid_str,
    chat_attachment_file_from_accepted_file,
    chat_attachment_tables_from_catalog_details,
    normalize_chat_upload_failure,
    parse_chat_upload_preparation_metadata,
    parse_lakehouse_ingest_result_data,
    parse_payload_model,
    to_chat_upload_accepted_file,
    upsert_chat_upload_preparation_metadata_json,
)
from .runtime import build_authorized_runtime_provider

logger = logging.getLogger(__name__)


class _RuntimeFactory(ChatRuntimeProviderFactoryProtocol):
    """Fixed runtime factory for API-hosted chat execution."""

    def __init__(self, *, runtime_provider: RuntimeProviderProtocol) -> None:
        self._runtime_provider = runtime_provider

    async def create_runtime_provider(
        self,
        *,
        project_id: UUID | str,
        headers: Mapping[str, str],
    ) -> RuntimeProviderProtocol:
        _ = (project_id, headers)
        return self._runtime_provider


async def get_chat_session_resource_service(
    request: Request, auth_context: AuthContext[ChatSessionModel]
) -> ChatSessionModel | None:
    session_id = extract_path_param(request, "chat_session_id")
    if not session_id:
        return None
    return await get_chat_session_resource_impl(
        project_id=auth_context.project_id,
        chat_session_id=UUID(str(session_id)),
    )


async def create_chat_session_service(
    *, request: CreateChatSessionRequest, auth_context: AuthContext[ChatSessionModel]
) -> ChatSessionModel:
    try:
        return await create_chat_session_impl(
            request=request,
            access_context=build_chat_access_context(auth_context),
        )
    except ChatServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def start_chat_upload_preparation_service(
    *,
    project_id: UUID,
    files,
    owner_id: UUID | None,
    ip_address: str | None,
    triggered_by: TriggerActorModel | None,
    queue_client: IQueueClient | None,
    allow_overwrite: bool = False,
) -> StartChatUploadPreparationResponse:
    catalog_service = CatalogManagementService(project_id=str(project_id))
    internal_connection = await catalog_service.ensure_default_internal_connection()
    if not internal_connection.id:
        raise HTTPException(
            status_code=500,
            detail="Unable to resolve the internal lakehouse connection.",
        )

    file_service = create_file_service(project_id, queue_client)
    validation_batch = await file_service.validate_upload_files(
        project_id=project_id,
        files=files,
        infer_type_func=infer_file_type,
        allowed_file_format_types=DataLakeConstants.get_supported_data_file_types(),
    )
    persisted_batch = await file_service.persist_uploaded_files(
        project_id=project_id,
        files=validation_batch.files,
        owner_id=owner_id,
        allow_overwrite=allow_overwrite,
    )

    upload_failures = [*validation_batch.failures, *persisted_batch.failures]
    accepted_files = persisted_batch.successful_files
    accepted_file_models = [
        to_chat_upload_accepted_file(file_record) for file_record in accepted_files
    ]
    upload_error_models = [
        normalize_chat_upload_failure(
            filename=failure.filename,
            error=failure.error,
            file_id=str(failure.file_id) if failure.file_id else None,
        )
        for failure in upload_failures
    ]
    run_id = await file_service.dispatch_post_upload_processing(
        persisted_batch=persisted_batch,
        owner_id=owner_id,
        ip_address=ip_address,
        triggered_by=triggered_by,
        force_workflow=True,
        workflow_key=CHAT_UPLOAD_PREPARATION_WORKFLOW_KEY,
        workflow_name="Chat Upload Preparation",
        workflow_description=(
            "Prepares staged chat attachments by ingesting them into the "
            "internal lakehouse and refreshing catalog metadata."
        ),
        system_actor=make_system_actor("ChatUploadPreparation"),
    )
    if run_id is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to start chat upload preparation workflow.",
        )

    context_service = ExecutionRunContextDataService(project_id)
    root_context = await context_service.get_by_run_id_async(run_id)
    await context_service.upsert_context_async(
        run_id=run_id,
        engine_metadata_json=upsert_chat_upload_preparation_metadata_json(
            root_context.engine_metadata_json if root_context else None,
            internal_catalog_connection_id=internal_connection.id,
            accepted_files=accepted_file_models,
            upload_errors=upload_error_models,
        ),
    )

    return StartChatUploadPreparationResponse(
        run_id=str(run_id),
        internal_catalog_connection_id=internal_connection.id,
        accepted_files=accepted_file_models,
        upload_errors=upload_error_models,
        success_count=len(accepted_files),
        failure_count=len(upload_failures),
    )


async def get_chat_upload_preparation_status_service(
    *,
    project_id: UUID,
    run_id: UUID,
) -> ChatUploadPreparationStatus:
    execution_run_service = ExecutionRunService()
    root_run = await execution_run_service.get_run_async(
        project_id=project_id,
        run_id=run_id,
        include_job=False,
    )
    if root_run is None:
        raise HTTPException(status_code=404, detail="Chat upload preparation not found")

    job_run_service = JobRunDataService(project_id)
    root_job_run = await job_run_service.get_run_by_id_async(
        run_id,
        include_job=False,
        include_trigger=False,
    )
    if root_job_run is None:
        raise HTTPException(status_code=404, detail="Chat upload preparation not found")

    context_service = ExecutionRunContextDataService(project_id)
    root_context = await context_service.get_by_run_id_async(run_id)
    workflow_projection = extract_workflow_projection_metadata(root_context)
    workflow_state = workflow_projection.workflow_state
    if (
        workflow_state is None
        or workflow_state.workflow_key != CHAT_UPLOAD_PREPARATION_WORKFLOW_KEY
    ):
        raise HTTPException(status_code=404, detail="Chat upload preparation not found")

    chat_preparation_metadata = parse_chat_upload_preparation_metadata(
        root_context.engine_metadata_json if root_context else None
    )
    initial_metadata = chat_preparation_metadata or parse_payload_model(
        root_job_run.parameters,
        ChatUploadPreparationMetadata,
    )
    if initial_metadata is None:
        initial_metadata = ChatUploadPreparationMetadata()

    initial_failures = list(initial_metadata.upload_errors)
    accepted_files = list(initial_metadata.accepted_files)
    filename_by_file_id = {
        accepted_file.file_id: accepted_file.filename for accepted_file in accepted_files
    }
    internal_connection_id = initial_metadata.internal_catalog_connection_id

    child_contexts = await context_service.list_by_root_run_id_async(run_id)
    child_run_ids: list[UUID] = []
    for context in child_contexts:
        child_run_id = as_optional_uuid_str(getattr(context, "run_id", None))
        if child_run_id is None or child_run_id == str(run_id):
            continue
        child_run_ids.append(UUID(child_run_id))

    child_runs = await job_run_service.get_runs_by_ids_async(
        child_run_ids,
        include_job=False,
        include_trigger=False,
    )
    child_runs_by_id = {str(child_run.id): child_run for child_run in child_runs}

    ready_file_ids: list[str] = []
    failed_files: list[ChatUploadPreparationFailure] = list(initial_failures)
    steps: list[ChatUploadPreparationStep] = []

    for step in workflow_state.steps:
        child_run = child_runs_by_id.get(str(step.run_id)) if step.run_id else None
        step_status = (
            map_job_run_status(child_run.status, job_run=child_run).value
            if child_run is not None
            else step.status
        )
        step_progress = child_run.progress if child_run is not None else None
        step_error = step.error_message or (
            child_run.error_message if child_run is not None else None
        )

        result_data = parse_lakehouse_ingest_result_data(
            child_run.result_data if child_run is not None else None
        )

        ready_file_ids.extend(
            file_id
            for file_id in (
                as_optional_uuid_str(file_id) for file_id in result_data.successful_file_ids
            )
            if file_id is not None
        )

        if not internal_connection_id and result_data.connection_id:
            internal_connection_id = result_data.connection_id

        for failed_file in result_data.failed_files:
            normalized_failed_file_id = as_optional_uuid_str(failed_file.file_id)
            failed_filename = (
                filename_by_file_id.get(normalized_failed_file_id)
                if normalized_failed_file_id is not None
                else None
            )
            failed_files.append(
                normalize_chat_upload_failure(
                    filename=failed_filename,
                    error=failed_file.error,
                    file_id=normalized_failed_file_id,
                )
            )

        steps.append(
            ChatUploadPreparationStep(
                key=step.key,
                name=step.name,
                status=step_status,
                run_id=str(step.run_id) if step.run_id else None,
                progress=step_progress,
                error_message=step_error,
            )
        )

    unique_ready_file_ids = list(dict.fromkeys(ready_file_ids))
    deduped_failures: list[ChatUploadPreparationFailure] = []
    seen_failures: set[tuple[str | None, str | None, str]] = set()
    for failure in failed_files:
        failure_key = (failure.file_id, failure.filename, failure.error)
        if failure_key in seen_failures:
            continue
        seen_failures.add(failure_key)
        deduped_failures.append(failure)

    normalized_status = root_run.status.value
    if normalized_status == "succeeded" and not unique_ready_file_ids and deduped_failures:
        normalized_status = "failed"

    progress = root_run.progress
    if progress is None:
        progress = (
            100 if normalized_status in {"succeeded", "failed", "cancelled", "timed_out"} else 0
        )

    return ChatUploadPreparationStatus(
        run_id=str(run_id),
        status=normalized_status,
        progress=progress,
        internal_catalog_connection_id=internal_connection_id,
        ready_file_ids=unique_ready_file_ids,
        failed_files=deduped_failures,
        steps=steps,
    )


async def seed_chat_attachment_context_service(
    *,
    chat_session_id: UUID,
    project_id: UUID,
    request: SeedChatAttachmentContextRequest,
) -> None:
    preparation_status = await get_chat_upload_preparation_status_service(
        project_id=project_id,
        run_id=UUID(str(request.upload_preparation_run_id)),
    )
    if not preparation_status.ready_file_ids:
        raise HTTPException(
            status_code=400,
            detail="This upload preparation does not have any ready attached files.",
        )

    context_service = ExecutionRunContextDataService(project_id)
    root_context = await context_service.get_by_run_id_async(request.upload_preparation_run_id)
    if root_context is None:
        raise HTTPException(status_code=404, detail="Chat upload preparation not found")

    chat_preparation_metadata = parse_chat_upload_preparation_metadata(
        root_context.engine_metadata_json
    )
    accepted_files = (
        list(chat_preparation_metadata.accepted_files)
        if chat_preparation_metadata is not None
        else []
    )
    accepted_files_by_id = {
        accepted_file.file_id: accepted_file for accepted_file in accepted_files
    }

    ready_context_files: list[ChatAttachmentContextFile] = []
    ready_context_tables: list[ChatAttachmentContextTable] = []
    catalog_service = CatalogManagementService(project_id=str(project_id))

    for ready_file_id in preparation_status.ready_file_ids:
        accepted_file = accepted_files_by_id.get(ready_file_id)
        if accepted_file is None:
            continue

        ready_context_files.append(chat_attachment_file_from_accepted_file(accepted_file))
        entity_details = await catalog_service.get_source_entities(
            source_type="file",
            source_id=ready_file_id,
        )
        ready_context_tables.extend(
            chat_attachment_tables_from_catalog_details(
                file_id=ready_file_id,
                entity_details=entity_details,
            )
        )

    if not ready_context_files:
        raise HTTPException(
            status_code=400,
            detail="We couldn't resolve the prepared attached files for this chat.",
        )
    if not ready_context_tables:
        raise HTTPException(
            status_code=400,
            detail="We couldn't resolve any attached tables for this chat.",
        )

    internal_catalog_connection_id = preparation_status.internal_catalog_connection_id or (
        chat_preparation_metadata.internal_catalog_connection_id
        if chat_preparation_metadata is not None
        else None
    )
    if not internal_catalog_connection_id:
        raise HTTPException(
            status_code=400,
            detail="The upload preparation is missing its internal catalog connection.",
        )

    attachment_context = ChatAttachmentContext(
        upload_preparation_run_id=str(request.upload_preparation_run_id),
        internal_catalog_connection_id=internal_catalog_connection_id,
        files=ready_context_files,
        tables=ready_context_tables,
    )
    await ChatSessionDataService(project_id).upsert_attachment_context_async(
        chat_session_id,
        attachment_context,
    )


async def get_filtered_chat_sessions_service(
    *,
    project_id: UUID,
    filter_string: str | None,
    page_index: int,
    page_size: int,
    my_sessions_only: bool,
    auth_context: AuthContext[ChatSessionModel],
) -> PaginatedChatSessionResponse:
    try:
        return await list_chat_sessions_impl(
            project_id=project_id,
            filter_string=filter_string,
            page_index=page_index,
            page_size=page_size,
            my_sessions_only=my_sessions_only,
            access_context=build_chat_access_context(auth_context),
        )
    except ChatServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def update_chat_session_service(
    *,
    chat_session_id: UUID,
    request: UpdateChatSessionRequest,
    project_id: UUID,
    auth_context: AuthContext[ChatSessionModel],
) -> ChatSessionModel:
    _ = project_id
    try:
        return await update_chat_session_impl(
            chat_session_id=chat_session_id,
            request=request,
            access_context=build_chat_access_context(auth_context, resource=auth_context.resource),
        )
    except ChatServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def delete_chat_session_service(
    *,
    chat_session_id: UUID,
    project_id: UUID,
    auth_context: AuthContext[ChatSessionModel],
) -> None:
    _ = project_id
    try:
        await delete_chat_session_impl(
            chat_session_id=chat_session_id,
            access_context=build_chat_access_context(auth_context, resource=auth_context.resource),
        )
    except ChatServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def get_chat_session_artifacts_service(
    *, chat_session_id: UUID, project_id: UUID
) -> ArtifactListResponse:
    return await get_chat_session_artifacts_impl(
        chat_session_id=chat_session_id,
        project_id=project_id,
    )


async def execute_chat_session_python_service(
    *,
    chat_session_id: UUID,
    project_id: UUID,
    code: str,
    auth_context: AuthContext[ChatSessionModel],
) -> PythonExecutionResult:
    chat_session_data_service = ChatSessionDataService(project_id)
    try:
        execution_result = await execute_chat_session_python_impl(
            project_id=str(project_id),
            chat_session_id=str(chat_session_id),
            code=code,
            owner_id=auth_context.user_id,
            triggered_by=chat_session_actor(str(chat_session_id)),
            chat_session_data_service=chat_session_data_service,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        # Bad input (empty code, unknown session) rather than an infra failure.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Unhandled exceptions reach Starlette's ServerErrorMiddleware, which
        # sits OUTSIDE CORSMiddleware, so the browser sees a CORS error instead
        # of the real 500. Translate to an HTTPException (handled inside CORS)
        # so the client gets a readable, CORS-headed response.
        logger.exception("Chat session Python execution failed for %s", chat_session_id)
        raise HTTPException(
            status_code=503,
            detail=f"Python execution failed: {exc!s}",
        ) from exc
    return execution_result.python_result


async def get_project_token_usage_service(
    project_id: UUID,
) -> ProjectTokenUsageResponse:
    return await get_project_token_usage_impl(project_id)


async def get_project_daily_token_usage_service(
    project_id: UUID, month: str | None
) -> ProjectDailyTokenUsageResponse:
    return await get_project_daily_token_usage_impl(project_id, month)


async def get_stream_chat_session_service(
    *, project_id: UUID | str, session_id: UUID | str
) -> ChatSessionModel:
    try:
        return await get_stream_chat_session_impl(
            project_id=project_id,
            session_id=session_id,
        )
    except ChatServiceError as exc:
        raise domain_error_to_http(exc) from exc


async def stream_chat_session_service(
    *,
    request: ChatRequest,
    headers: Mapping[str, str],
    auth_context: AuthContext[ChatSessionModel],
    queue_client: IQueueClient | None,
) -> AsyncGenerator[str, None]:
    try:
        return await stream_chat_session_impl(
            context=ChatStreamContext(
                request=request,
                access=build_chat_access_context(auth_context),
                headers=headers,
            ),
            runtime_factory=_RuntimeFactory(
                runtime_provider=build_authorized_runtime_provider(
                    project_id=str(auth_context.project_id),
                    access_context=build_query_access_context(auth_context),
                    queue_client=queue_client,
                )
            ),
            agent_workflow=DEFAULT_CHAT_AGENT_WORKFLOW,
            execution_tracker=EXECUTION_RUN_TRACKER,
        )
    except ChatServiceError as exc:
        raise domain_error_to_http(exc) from exc
