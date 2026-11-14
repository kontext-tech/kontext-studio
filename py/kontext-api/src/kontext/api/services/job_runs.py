"""API adapters for job-run management application services."""

from __future__ import annotations

from uuid import UUID

from fastapi import Request

from kontext.jobs.job_run_management import (
    add_job_run_log_service,
    get_job_run_logs_service,
    get_job_run_service,
    list_job_runs_service,
    reset_job_runs_service,
    update_job_run_progress_service,
    update_job_run_status_service,
    update_job_run_worker_service,
)
from kontext.jobs.job_run_management import (
    get_job_run_resource_service as get_job_run_resource,
)
from kontext.schema import JobRunModel

from ..dependencies import AuthContext, extract_path_param


async def get_job_run_resource_service(
    request: Request, auth_context: AuthContext[JobRunModel]
) -> JobRunModel | None:
    run_id = extract_path_param(request, "run_id")
    if not run_id:
        return None
    return await get_job_run_resource(
        run_id=UUID(str(run_id)),
        auth_context=auth_context,
    )


__all__ = [
    "add_job_run_log_service",
    "get_job_run_logs_service",
    "get_job_run_resource_service",
    "get_job_run_service",
    "list_job_runs_service",
    "reset_job_runs_service",
    "update_job_run_progress_service",
    "update_job_run_status_service",
    "update_job_run_worker_service",
]
