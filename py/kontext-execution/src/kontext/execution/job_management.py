"""Execution-owned job management helpers."""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from kontext.common import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from kontext.data import JobDataService, JobRunDataService, JobTriggerDataService
from kontext.jobs import CronParser, JobSchedulerService
from kontext.jobs.job_registry import get_job_registry
from kontext.schema import (
    CreateJobRequest,
    ExecuteJobNowRequest,
    JobCategory,
    JobExecutionRuntime,
    JobModel,
    JobRunModel,
    JobRunStatus,
    JobTriggerType,
    PaginatedListOfJobModel,
    UnifiedJobParameterModel,
    UnifiedJobTypeModel,
    UpdateJobRequest,
)

logger = logging.getLogger(__name__)

_AGENT_CHAT_JOB_TYPE = "python.agent.ChatSessionRun"
_AGENT_CHAT_JOB_NAME = "Agent Chat Session Run"
_WORKFLOW_ROOT_JOB_TYPE_PATTERN = re.compile(
    r"^python\.workflow\.(?P<workflow_key>[A-Za-z0-9_]+)\.Root$"
)


def _get_synthetic_job_type(job_type: str) -> UnifiedJobTypeModel | None:
    if job_type == _AGENT_CHAT_JOB_TYPE:
        return UnifiedJobTypeModel(
            type=_AGENT_CHAT_JOB_TYPE,
            name=_AGENT_CHAT_JOB_NAME,
            description="Interactive chat-linked agent execution run.",
            category=JobCategory.PROCESSING,
            runtime=JobExecutionRuntime.PYTHON,
            parameters=[],
            is_system_job=True,
            required_permissions=[],
        )

    workflow_match = _WORKFLOW_ROOT_JOB_TYPE_PATTERN.match(job_type)
    if workflow_match is None:
        return None

    workflow_key = workflow_match.group("workflow_key")
    workflow_label = workflow_key.replace("_", " ").strip()
    return UnifiedJobTypeModel(
        type=job_type,
        name=f"{workflow_label.title()} Workflow Root",
        description=(f"System-managed workflow root for '{workflow_label or workflow_key}'."),
        category=JobCategory.PROCESSING,
        runtime=JobExecutionRuntime.PYTHON,
        parameters=[],
        is_system_job=True,
        required_permissions=[],
    )


async def get_job_resource_service(*, job_id: UUID, auth_context: Any) -> JobModel | None:
    """Fetch a job resource for authorization checks."""
    job_service = JobDataService(auth_context.project_id)
    return await job_service.get_job_by_id_async(job_id)


async def list_jobs_service(
    *,
    project_id: UUID,
    page_index: int,
    page_size: int,
    is_enabled: bool | None,
    auth_context: Any,
) -> PaginatedListOfJobModel:
    job_service = JobDataService(project_id)
    run_service = JobRunDataService(project_id)

    result = await job_service.get_jobs_paginated_async(
        page_index=page_index,
        is_enabled=is_enabled,
        owner_id=auth_context.effective_owner_id,
    )

    enriched_items = await job_service.enrich_jobs_with_stats_batch_async(
        result.items or [], run_service
    )

    total_count = result.total_count or 0
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

    return PaginatedListOfJobModel(
        items=enriched_items,
        total_count=total_count,
        page_index=page_index - 1,
        page_size=page_size,
        total_pages=total_pages,
    )


def list_job_types_service() -> list[UnifiedJobTypeModel]:
    registry = get_job_registry()
    job_registrations = registry.get_all_jobs()

    return [
        UnifiedJobTypeModel(
            type=registration.type,
            name=registration.name,
            description=registration.description,
            category=registration.category,
            runtime=JobExecutionRuntime.PYTHON,
            parameters=[
                UnifiedJobParameterModel(
                    name=p.name,
                    type=p.type,
                    required=p.required,
                    default_value=p.default_value,
                    description=p.description,
                )
                for p in (registration.parameters or [])
            ],
            is_system_job=False,
            required_permissions=[],
        )
        for registration in job_registrations
    ]


def get_job_type_service(job_type: str) -> UnifiedJobTypeModel:
    synthetic = _get_synthetic_job_type(job_type)
    if synthetic is not None:
        return synthetic

    registry = get_job_registry()
    metadata = registry.get_job_metadata(job_type)

    if not metadata:
        raise NotFoundError(f"Job type {job_type} not found")

    return UnifiedJobTypeModel(
        type=job_type,
        name=metadata.name,
        description=metadata.description,
        category=metadata.category,
        runtime=JobExecutionRuntime.PYTHON,
        parameters=[
            UnifiedJobParameterModel(
                name=p.name,
                type=p.type,
                required=p.required,
                default_value=p.default_value,
                description=p.description,
            )
            for p in (metadata.parameters or [])
        ],
        is_system_job=False,
        required_permissions=[],
    )


async def get_job_service(
    *,
    job_id: UUID,
    auth_context: Any,
) -> JobModel:
    if not auth_context.resource:
        raise NotFoundError(f"Job {job_id} not found")

    job_service = JobDataService(auth_context.project_id)
    run_service = JobRunDataService(auth_context.project_id)
    return await job_service.enrich_job_with_stats_async(auth_context.resource, run_service)


async def create_job_service(
    *,
    request: CreateJobRequest,
    project_id: UUID,
    auth_context: Any,
) -> JobModel:
    job_service = JobDataService(project_id)
    trigger_service = JobTriggerDataService(project_id)

    if request.schedule and not CronParser.is_valid(request.schedule):
        raise BadRequestError(f"Invalid CRON expression: {request.schedule}")

    if request.name and await job_service.job_exists_by_name_async(request.name):
        raise ConflictError(f"Job with name '{request.name}' already exists")

    parameters_json: str | None = None
    if request.parameters:
        if isinstance(request.parameters, dict):
            parameters_json = json.dumps(request.parameters)
        else:
            parameters_json = request.parameters

    create_request = CreateJobRequest(
        name=request.name,
        type=request.type,
        description=request.description,
        schedule=request.schedule,
        parameters=parameters_json,
        timeout=request.timeout,
        is_enabled=request.is_enabled,
        retry_strategy=request.retry_strategy,
        retry_limit=request.retry_limit,
    )

    job = await job_service.create_job_async(
        create_request,
        owner_id=auth_context.user_id,
        created_by=auth_context.user.email if auth_context.user else None,
    )

    if request.schedule and job.id:
        await trigger_service.create_trigger_async(
            job_id=UUID(job.id),
            trigger_type=JobTriggerType.SCHEDULED,
            configuration=json.dumps({"schedule": request.schedule}),
            triggered_by=auth_context.trigger_actor if auth_context.user else None,
        )

    logger.info("Created job %s for project %s", job.id, project_id)
    return job


async def update_job_service(
    *,
    job_id: UUID,
    request: UpdateJobRequest,
    auth_context: Any,
) -> JobModel:
    if not auth_context.resource:
        raise NotFoundError(f"Job {job_id} not found")

    job_service = JobDataService(auth_context.project_id)
    run_service = JobRunDataService(auth_context.project_id)
    existing_job = auth_context.resource

    if not existing_job.owner_id:
        raise ForbiddenError("System jobs cannot be modified")

    if request.schedule and not CronParser.is_valid(request.schedule):
        raise BadRequestError(f"Invalid CRON expression: {request.schedule}")

    if (
        request.name
        and request.name != existing_job.name
        and await job_service.job_exists_by_name_async(request.name, exclude_id=job_id)
    ):
        raise ConflictError(f"Job with name '{request.name}' already exists")

    parameters_json: str | None = None
    if request.parameters:
        if isinstance(request.parameters, dict):
            parameters_json = json.dumps(request.parameters)
        else:
            parameters_json = request.parameters

    update_request = UpdateJobRequest(
        name=request.name,
        type=request.type,
        description=request.description,
        schedule=request.schedule,
        parameters=parameters_json,
        timeout=request.timeout,
        is_enabled=request.is_enabled,
        retry_strategy=request.retry_strategy,
        retry_limit=request.retry_limit,
    )

    updated_job = await job_service.update_job_async(
        job_id,
        update_request,
        updated_by=auth_context.user.email if auth_context.user else None,
    )
    if not updated_job:
        raise NotFoundError(f"Job {job_id} not found")

    logger.info("Updated job %s", job_id)
    return await job_service.enrich_job_with_stats_async(updated_job, run_service)


async def delete_job_service(
    *,
    job_id: UUID,
    auth_context: Any,
) -> None:
    if not auth_context.resource:
        raise NotFoundError(f"Job {job_id} not found")

    job_service = JobDataService(auth_context.project_id)
    existing_job = auth_context.resource

    if not existing_job.owner_id:
        raise ForbiddenError("System jobs cannot be deleted")

    deleted = await job_service.soft_delete_job_async(job_id)
    if not deleted:
        raise NotFoundError(f"Job {job_id} not found")

    logger.info("Deleted job %s", job_id)


async def schedule_job_service(
    *,
    job_id: UUID,
    request: ExecuteJobNowRequest | None,
    project_id: UUID,
    auth_context: Any,
) -> JobRunModel:
    if not auth_context.resource:
        raise NotFoundError(f"Job {job_id} not found")

    existing_job = auth_context.resource
    if not existing_job.owner_id:
        raise ForbiddenError("System jobs cannot be run manually")

    parameters_json = None
    if request and request.parameters:
        parameters_json = json.dumps(request.parameters)

    scheduler = JobSchedulerService()
    job_run = await scheduler.schedule_job_manually_async(
        job_id=job_id,
        project_id=project_id,
        parameters=parameters_json,
        triggered_by=auth_context.user.email if auth_context.user else None,
        execution_id=request.execution_id if request else None,
    )

    logger.info("Scheduled job %s (run %s)", job_id, job_run.id)

    return JobRunModel(
        id=str(job_run.id),
        job_id=str(job_run.job_id),
        status=JobRunStatus(job_run.status) if job_run.status else JobRunStatus.QUEUED,
        job_trigger_id=str(job_run.trigger_id) if job_run.trigger_id else None,
        created_at=job_run.created_at,
        started_at=job_run.created_at,
        attempt_count=job_run.attempt_count,
        execution_id=job_run.execution_id,
    )
