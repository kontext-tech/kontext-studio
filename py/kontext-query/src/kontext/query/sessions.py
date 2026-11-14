"""Query session orchestration."""

from __future__ import annotations

from uuid import UUID

from kontext.common.jobs.trigger_actor import format_trigger_actor, user_actor
from kontext.common.messaging import IQueueClient
from kontext.common.pagination import page_flags as common_page_flags
from kontext.common.pagination import total_pages as common_total_pages
from kontext.data import QuerySessionDataService
from kontext.jobs.job_run_dispatch import create_job_run_and_maybe_dispatch
from kontext.jobs.lifecycle import ExecutionLifecycleService
from kontext.jobs.polling import poll_job_run_completion
from kontext.query.jobs.dispatch import dispatch_cleanup_session_job
from kontext.query.jobs.initialize_session_job import (
    InitializeSessionJob,
    InitializeSessionParams,
)
from kontext.schema import (
    CreateQuerySessionRequest,
    ExecutionRunModel,
    JobTriggerType,
    PaginatedListOfQuerySessionModel,
    QueryEngineType,
    QuerySessionModel,
    QuerySessionStatus,
    SessionInitRequest,
    SessionInitResponse,
    UpdateQuerySessionRequest,
)

from .context import QueryAccessContext
from .errors import QueryServiceError
from .query_session_service import QuerySessionService

SESSION_INIT_TIMEOUT_SECONDS = 60
_EXECUTION_LIFECYCLE = ExecutionLifecycleService()


async def get_query_session_resource(
    *, project_id: UUID, session_id: UUID
) -> QuerySessionModel | None:
    service = QuerySessionDataService(project_id)
    return await service.get_by_id_async(session_id)


async def create_query_session(
    *,
    request: CreateQuerySessionRequest,
    access_context: QueryAccessContext,
) -> QuerySessionModel:
    service = QuerySessionService(str(request.project_id))
    session = await service.create_session_async(
        request=request,
        user_id=str(access_context.user_id),
    )
    if not session:
        raise QueryServiceError(500, "Failed to create query session")
    return session


async def initialize_session_sync(
    *,
    request: SessionInitRequest,
    access_context: QueryAccessContext,
    queue_client: IQueueClient | None,
) -> SessionInitResponse:
    _validate_project_match(request=request, access_context=access_context)
    session_vm = _get_session_for_execution(request=request, access_context=access_context)

    if session_vm.status == QuerySessionStatus.ACTIVE:
        return SessionInitResponse(success=True, session=session_vm)

    existing_result = await _try_reuse_existing_initialization(
        request=request,
        access_context=access_context,
        session_vm=session_vm,
    )
    if existing_result is not None:
        return existing_result

    if not queue_client:
        return SessionInitResponse(
            success=False,
            error_message="Queue service unavailable. Cannot initialize session.",
        )

    job_run = await _create_session_initialization_run(
        request=request,
        session_engine_type=session_vm.engine_type,
        user_id=access_context.user_id,
        actor_label=access_context.actor_label,
        queue_client=queue_client,
    )
    job_run_id = UUID(str(job_run.id))

    poll_result = await poll_job_run_completion(
        project_id=UUID(str(request.project_id)),
        job_run_id=str(job_run_id),
        timeout_seconds=SESSION_INIT_TIMEOUT_SECONDS,
    )
    if poll_result is None:
        return SessionInitResponse(
            success=False,
            job_run_id=str(job_run_id),
            error_message=(
                f"Session initialization timed out after {SESSION_INIT_TIMEOUT_SECONDS}s"
            ),
        )

    if poll_result.succeeded:
        query_session_data_service = QuerySessionDataService(str(request.project_id))
        updated_session = query_session_data_service.get_session(
            str(request.session_id),
            owner_id=(
                str(access_context.effective_owner_id)
                if access_context.effective_owner_id
                else None
            ),
        )
        if updated_session:
            return SessionInitResponse(
                success=True,
                job_run_id=str(job_run_id),
                session=updated_session,
            )
        return SessionInitResponse(
            success=False,
            job_run_id=str(job_run_id),
            error_message="Session not found after initialization",
        )

    return SessionInitResponse(
        success=False,
        job_run_id=str(job_run_id),
        error_message=poll_result.error_message or "Session initialization failed",
    )


async def initialize_session_async(
    *,
    request: SessionInitRequest,
    access_context: QueryAccessContext,
    queue_client: IQueueClient | None,
) -> ExecutionRunModel:
    _validate_project_match(request=request, access_context=access_context)

    if not queue_client:
        raise QueryServiceError(503, "Queue service unavailable. Cannot initialize session.")

    session_vm = _get_session_for_execution(request=request, access_context=access_context)
    if session_vm.status == QuerySessionStatus.ACTIVE:
        raise QueryServiceError(409, f"Session {request.session_id} is already active")

    job_run = await _create_session_initialization_run(
        request=request,
        session_engine_type=session_vm.engine_type,
        user_id=access_context.user_id,
        actor_label=access_context.actor_label,
        queue_client=queue_client,
    )
    return _EXECUTION_LIFECYCLE.project_job_run(job_run)


def list_query_sessions(
    *,
    access_context: QueryAccessContext,
    my_sessions_only: bool,
    page_index: int,
    page_size: int,
) -> PaginatedListOfQuerySessionModel:
    query_session_data_service = QuerySessionDataService(str(access_context.project_id))
    owner_filter = access_context.user_id if my_sessions_only else access_context.effective_owner_id
    sessions, total_count = query_session_data_service.list_sessions(
        owner_id=str(owner_filter) if owner_filter else None,
        page_index=page_index,
        page_size=page_size,
    )
    total_pages = common_total_pages(total_count, page_size)
    previous_page, next_page = common_page_flags(page_index, total_pages)
    return PaginatedListOfQuerySessionModel(
        items=sessions,
        total_count=total_count,
        page_index=page_index,
        page_size=page_size,
        total_pages=total_pages,
        has_previous_page=previous_page,
        has_next_page=next_page,
    )


def update_query_session(
    *,
    session_id: UUID,
    request: UpdateQuerySessionRequest,
    access_context: QueryAccessContext,
) -> QuerySessionModel:
    resource = access_context.resource
    if not resource:
        raise QueryServiceError(404, f"Query session {session_id} not found")

    if str(resource.owner_id) != str(access_context.user_id) and not access_context.project_scope:
        raise QueryServiceError(403, "You do not have permission to update this session.")

    if (
        request.status
        and request.status != QuerySessionStatus.CLOSED
        and not access_context.project_scope
        and str(resource.owner_id) != str(access_context.user_id)
    ):
        raise QueryServiceError(
            403,
            "Only administrators or authorized service accounts can change "
            "the status of another user's session.",
        )

    query_session_data_service = QuerySessionDataService(str(access_context.project_id))
    updated_session = query_session_data_service.update_session(
        str(session_id), request, str(access_context.user_id)
    )
    if not updated_session:
        raise QueryServiceError(404, f"Session {session_id} not found")
    return updated_session


async def delete_query_session(
    *,
    session_id: UUID,
    access_context: QueryAccessContext,
    queue_client: IQueueClient | None,
) -> None:
    resource = access_context.resource
    if not resource:
        raise QueryServiceError(404, f"Query session {session_id} not found")

    if (
        access_context.project_scope
        and str(resource.owner_id) != str(access_context.user_id)
        and resource.status == QuerySessionStatus.ACTIVE
    ):
        raise QueryServiceError(
            400,
            "Cannot delete an active session belonging to another user. "
            "Please close the session first.",
        )

    query_session_data_service = QuerySessionDataService(str(access_context.project_id))
    success = query_session_data_service.delete_session(
        str(session_id), str(access_context.user_id)
    )
    if not success:
        raise QueryServiceError(404, f"Session {session_id} not found")

    if queue_client:
        await dispatch_cleanup_session_job(
            queue_client=queue_client,
            project_id=access_context.project_id,
            session_ids=[session_id],
            triggered_by=user_actor(str(access_context.user_id)),
            owner_id=access_context.user_id,
        )


def _validate_project_match(
    *, request: SessionInitRequest, access_context: QueryAccessContext
) -> None:
    if str(request.project_id) != str(access_context.project_id):
        raise QueryServiceError(403, "Session does not belong to the authorized project")


def _get_session_for_execution(
    *,
    request: SessionInitRequest,
    access_context: QueryAccessContext,
) -> QuerySessionModel:
    query_session_data_service = QuerySessionDataService(str(request.project_id))
    session_vm = query_session_data_service.get_session(
        request.session_id,
        owner_id=(
            str(access_context.effective_owner_id) if access_context.effective_owner_id else None
        ),
    )
    if not session_vm:
        raise QueryServiceError(404, f"Session {request.session_id} not found")
    return session_vm


async def _try_reuse_existing_initialization(
    *,
    request: SessionInitRequest,
    access_context: QueryAccessContext,
    session_vm: QuerySessionModel,
) -> SessionInitResponse | None:
    if not session_vm.job_run_id:
        return None

    existing_poll_result = await poll_job_run_completion(
        project_id=UUID(str(request.project_id)),
        job_run_id=session_vm.job_run_id,
        timeout_seconds=SESSION_INIT_TIMEOUT_SECONDS,
    )
    if existing_poll_result is None or not existing_poll_result.succeeded:
        return None

    query_session_data_service = QuerySessionDataService(str(request.project_id))
    updated_session = query_session_data_service.get_session(
        str(request.session_id),
        owner_id=(
            str(access_context.effective_owner_id) if access_context.effective_owner_id else None
        ),
    )
    if not updated_session:
        return None

    return SessionInitResponse(
        success=True,
        job_run_id=session_vm.job_run_id,
        session=updated_session,
    )


async def _create_session_initialization_run(
    *,
    request: SessionInitRequest,
    session_engine_type: str,
    user_id: UUID,
    actor_label: str | None = None,
    queue_client: IQueueClient,
):
    persistent = request.persistent if request.persistent is not None else True
    params = InitializeSessionParams(
        session_id=str(request.session_id),
        project_id=str(request.project_id),
        catalog_connection_id=(
            str(request.catalog_connection_id) if request.catalog_connection_id else None
        ),
        default_namespace=request.default_namespace,
        default_entity_id=(str(request.default_entity_id) if request.default_entity_id else None),
        user_id=str(user_id),
        persistent=persistent,
        engine_type=QueryEngineType(session_engine_type),
    )

    triggered_by_actor = user_actor(str(user_id))
    created_by_label = actor_label or format_trigger_actor(triggered_by_actor)

    job_run, _dispatched = await create_job_run_and_maybe_dispatch(
        project_id=UUID(str(request.project_id)),
        queue_client=queue_client,
        owner_id=user_id,
        job_class=InitializeSessionJob,
        job_params=params,
        triggered_by=triggered_by_actor,
        trigger_type=JobTriggerType.INTERACTIVE,
        created_by=created_by_label,
        timeout_minutes=5,
        priority=10,
        on_run_created=lambda run: QuerySessionDataService(str(request.project_id)).set_job_run_id(
            session_id=str(request.session_id),
            job_run_id=str(run.id),
            user_id=str(user_id),
        ),
    )
    return job_run
