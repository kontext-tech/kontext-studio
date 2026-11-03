"""Query execution orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from uuid import UUID

from kontext.common.jobs.trigger_actor import format_trigger_actor, user_actor
from kontext.common.messaging import IQueueClient
from kontext.data import (
    ExecutionRunContextDataService,
    QueryHistoryDataService,
    QuerySessionDataService,
)
from kontext.execution.lifecycle import ExecutionLifecycleService
from kontext.execution.polling import poll_job_run_completion
from kontext.execution.scheduling import create_job_run_and_maybe_dispatch
from kontext.query.jobs.execute_query_job import ExecuteQueryJob, ExecuteQueryParams
from kontext.schema import (
    ArtifactOrigin,
    ArtifactProvenance,
    CreateQueryRequest,
    ExecutionRunModel,
    JobTriggerType,
    QueryEngineType,
    QueryExecRequest,
    QueryResponse,
    QuerySessionModel,
    QuerySessionStatus,
    TriggerActorModel,
    TriggerActorType,
)

from .context import QueryAccessContext
from .errors import QueryServiceError

logger = logging.getLogger(__name__)
_EXECUTION_LIFECYCLE = ExecutionLifecycleService()


async def execute_query_sync(
    *,
    request: QueryExecRequest,
    access_context: QueryAccessContext,
    queue_client: IQueueClient | None,
) -> QueryResponse:
    session = _get_authorized_active_session(request=request, access_context=access_context)
    project_id = UUID(str(session.project_id))

    if not queue_client:
        raise QueryServiceError(503, "Queue service unavailable. Cannot execute query.")

    query_timeout = int(request.query_timeout_seconds or 300)
    job_run = await _create_query_execution_run(
        request=request,
        project_id=project_id,
        session=session,
        engine_type=session.engine_type,
        user_id=access_context.user_id,
        actor_label=access_context.actor_label,
        queue_client=queue_client,
    )
    job_run_id = UUID(str(job_run.id))

    start_time = time.time()
    poll_result = await poll_job_run_completion(
        project_id=project_id,
        job_run_id=str(job_run_id),
        timeout_seconds=float(query_timeout + 30),
    )
    if poll_result is None:
        raise QueryServiceError(504, f"Query execution timed out after {query_timeout + 30}s")

    execution_duration_ms = int((time.time() - start_time) * 1000)
    user_id = str(access_context.user_id)

    if poll_result.succeeded and poll_result.result_data:
        try:
            execution_data = json.loads(poll_result.result_data)
        except json.JSONDecodeError:
            return QueryResponse(
                success=False,
                error_message="Failed to parse query results",
                data_id=None,
            )

        query_data = (
            execution_data["data"]
            if isinstance(execution_data.get("data"), dict)
            else execution_data
        )
        query_response = QueryResponse(**query_data)
        total_row_count = query_response.result.row_count if query_response.result else 0
        if query_response.success:
            # The queued job's stored payload has no actor context; stamp the
            # authoritative provenance here from the authorized requester.
            query_response.provenance = ArtifactProvenance(
                origin=ArtifactOrigin.SQLQUERY,
                created_by=TriggerActorModel(
                    type=TriggerActorType.USER, id=str(access_context.user_id)
                ),
                execution_run_id=str(job_run_id),
            )

        await _record_query_execution(
            project_id=str(access_context.project_id),
            user_id=user_id,
            create_query_request=CreateQueryRequest(
                code=request.sql_query,
                succeeded=query_response.success or False,
                record_count=total_row_count if query_response.success else None,
                message=query_response.error_message,
                session_id=request.session_id,
                job_run_id=str(job_run_id),
                duration_ms=execution_duration_ms,
            ),
        )
        return query_response

    await _record_query_execution(
        project_id=str(access_context.project_id),
        user_id=user_id,
        create_query_request=CreateQueryRequest(
            code=request.sql_query,
            succeeded=False,
            record_count=None,
            message=(poll_result.error_message or f"Query execution {poll_result.status}"),
            session_id=request.session_id,
            job_run_id=str(job_run_id),
            duration_ms=execution_duration_ms,
        ),
    )
    return QueryResponse(
        success=False,
        error_message=(poll_result.error_message or f"Query execution {poll_result.status}"),
        data_id=None,
        # Failed runs persist too; stamp the run so clients can link back to
        # it exactly like successful responses do.
        provenance=ArtifactProvenance(
            origin=ArtifactOrigin.SQLQUERY,
            created_by=TriggerActorModel(
                type=TriggerActorType.USER, id=str(access_context.user_id)
            ),
            execution_run_id=str(job_run_id),
        ),
    )


async def execute_query_async(
    *,
    request: QueryExecRequest,
    access_context: QueryAccessContext,
    queue_client: IQueueClient | None,
) -> ExecutionRunModel:
    session = _get_authorized_active_session(request=request, access_context=access_context)

    if not queue_client:
        raise QueryServiceError(503, "Queue service unavailable. Cannot execute query.")

    job_run = await _create_query_execution_run(
        request=request,
        project_id=UUID(str(session.project_id)),
        session=session,
        engine_type=session.engine_type,
        user_id=access_context.user_id,
        actor_label=access_context.actor_label,
        queue_client=queue_client,
    )
    return _EXECUTION_LIFECYCLE.project_job_run(job_run)


def get_session_query_history(
    *,
    project_id: str,
    session_id: str,
    page_index: int,
    page_size: int,
) -> dict[str, object]:
    query_data_service = QueryHistoryDataService(project_id)
    queries, total_count = query_data_service.get_session_queries(
        session_id=session_id,
        page_index=page_index,
        page_size=page_size,
    )
    return {"queries": queries, "total": total_count}


def _get_authorized_active_session(
    *,
    request: QueryExecRequest,
    access_context: QueryAccessContext,
):
    query_session_data_service = QuerySessionDataService(str(access_context.project_id))
    session = query_session_data_service.get_session(
        str(request.session_id),
        owner_id=(
            str(access_context.effective_owner_id) if access_context.effective_owner_id else None
        ),
    )
    if not session:
        raise QueryServiceError(404, f"Session {request.session_id} not found")

    if str(session.project_id) != str(access_context.project_id):
        raise QueryServiceError(403, "Session does not belong to the authorized project")

    if not access_context.project_scope and str(session.owner_id) != str(access_context.user_id):
        raise QueryServiceError(403, "Session belongs to another user. Access denied.")

    if session.status != QuerySessionStatus.ACTIVE:
        raise QueryServiceError(
            400,
            f"Session is not active (status: {session.status}). "
            "Please ensure the session is properly initialized.",
        )

    return session


async def _create_query_execution_run(
    *,
    request: QueryExecRequest,
    project_id: UUID,
    session: QuerySessionModel,
    engine_type: str,
    user_id: UUID,
    actor_label: str | None = None,
    queue_client: IQueueClient,
):
    query_timeout = int(request.query_timeout_seconds or 300)
    params = ExecuteQueryParams(
        sql=request.sql_query,
        session_id=str(request.session_id),
        catalog_connection_id=(
            str(session.catalog_connection_id) if session.catalog_connection_id else None
        ),
        default_namespace=session.default_namespace,
        default_entity_id=(str(session.default_entity_id) if session.default_entity_id else None),
        engine_type=QueryEngineType(engine_type),
        query_timeout_seconds=query_timeout,
        store_result_as_resource=request.store_result_as_resource or False,
        store_result_threshold_rows=request.store_result_threshold_rows,
        store_result_name=request.store_result_name,
        existing_data_id=(str(request.existing_data_id) if request.existing_data_id else None),
    )

    triggered_by_actor = request.triggered_by or user_actor(str(user_id))
    triggered_by_label = actor_label or format_trigger_actor(triggered_by_actor)

    job_run, _dispatched = await create_job_run_and_maybe_dispatch(
        project_id=project_id,
        queue_client=queue_client,
        owner_id=user_id,
        job_class=ExecuteQueryJob,
        job_params=params,
        triggered_by=triggered_by_actor,
        trigger_type=JobTriggerType.INTERACTIVE,
        created_by=triggered_by_label,
        timeout_minutes=int(max(1, (query_timeout + 60) // 60)),
        priority=10,
        on_run_created=lambda run: _upsert_query_execution_context(
            project_id=project_id,
            job_run_id=UUID(str(run.id)),
            chat_session_id=request.chat_session_id,
            parent_run_id=request.parent_run_id,
        ),
    )
    return job_run


async def _upsert_query_execution_context(
    *,
    project_id: UUID,
    job_run_id: UUID,
    chat_session_id: str | None,
    parent_run_id: str | None,
) -> None:
    if not chat_session_id and not parent_run_id:
        return

    context_service = ExecutionRunContextDataService(project_id)
    root_run_id: UUID | None = None

    if parent_run_id:
        parent_context = await context_service.get_by_run_id_async(parent_run_id)
        if parent_context and parent_context.root_run_id is not None:
            root_run_id = parent_context.root_run_id
        else:
            root_run_id = UUID(str(parent_run_id))

    await context_service.upsert_context_async(
        run_id=job_run_id,
        chat_session_id=chat_session_id,
        parent_run_id=parent_run_id,
        root_run_id=root_run_id,
    )


async def _record_query_execution(
    *,
    project_id: str,
    user_id: str,
    create_query_request: CreateQueryRequest,
) -> None:
    try:
        query_data_service = QueryHistoryDataService(project_id)
        await asyncio.to_thread(query_data_service.record_query, create_query_request, user_id)
    except Exception as record_error:
        logger.warning("Failed to record query execution history: %s", record_error)
