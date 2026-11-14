"""Kontext Jobs package.

One package for the whole job lifecycle: the harness-neutral framework in this
package (job classes, registry, execution, scheduling) and the orchestration
services that create, dispatch, poll and project job/execution runs, former
``kontext.execution``, now ``kontext.jobs``.

Exports are loaded lazily so importing ``kontext.jobs`` never pulls heavy
dependencies (data layers, optional SDKs) into unrelated processes.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BasePythonJob, IPythonJob
    from .decorators import job, params_model_to_job_params
    from .dispatch import build_job_execution_message
    from .events import EventService
    from .job_execution_service import JobExecutionService
    from .job_management import (
        create_job_service,
        delete_job_service,
        get_job_resource_service,
        get_job_service,
        get_job_type_service,
        list_job_types_service,
        list_jobs_service,
        schedule_job_service,
        update_job_service,
    )
    from .job_run_dispatch import (
        create_job_run_and_maybe_dispatch,
        create_queued_job_run_and_maybe_dispatch,
        handle_run_status_change_hook,
    )
    from .job_run_management import (
        add_job_run_log_service,
        get_job_run_logs_service,
        get_job_run_resource_service,
        get_job_run_service,
        list_job_runs_service,
        reset_job_runs_service,
        update_job_run_progress_service,
        update_job_run_status_service,
        update_job_run_worker_service,
    )
    from .job_run_summary import build_display_summary, enrich_job_run_display_summary
    from .lifecycle import (
        ExecutionLifecycleService,
        ExecutionRunInputValidationError,
        ResolvedExecutionRunInput,
    )
    from .permissions import JobRequiredPermissions
    from .polling import JobRunPollingResult, poll_job_run_completion
    from .runs import (
        ExecutionRunService,
        build_log_event,
        build_status_event,
        get_job_run_resource_async,
        infer_execution_run_kind,
        map_job_run_status,
        project_execution_run,
    )
    from .scheduling import CronParser, JobSchedulerService
    from .workflows import (
        WorkflowJobStepDefinition,
        WorkflowOrchestrationService,
        WorkflowProjectionMetadata,
        WorkflowStartRequest,
        extract_workflow_projection_metadata,
        get_workflow_metadata,
        parse_engine_metadata_json,
        upsert_workflow_metadata_json,
    )


_EXPORTS = {
    # Framework (job classes, registry, execution, CRON scheduling).
    "BasePythonJob": "kontext.jobs.base",
    "IPythonJob": "kontext.jobs.base",
    "job": "kontext.jobs.decorators",
    "params_model_to_job_params": "kontext.jobs.decorators",
    "build_job_execution_message": "kontext.jobs.dispatch",
    "JobExecutionService": "kontext.jobs.job_execution_service",
    "JobRequiredPermissions": "kontext.jobs.permissions",
    "CronParser": "kontext.jobs.scheduling",
    "JobSchedulerService": "kontext.jobs.scheduling",
    # Orchestration (job management).
    "create_job_service": "kontext.jobs.job_management",
    "delete_job_service": "kontext.jobs.job_management",
    "get_job_resource_service": "kontext.jobs.job_management",
    "get_job_service": "kontext.jobs.job_management",
    "get_job_type_service": "kontext.jobs.job_management",
    "list_job_types_service": "kontext.jobs.job_management",
    "list_jobs_service": "kontext.jobs.job_management",
    "schedule_job_service": "kontext.jobs.job_management",
    "update_job_service": "kontext.jobs.job_management",
    # Orchestration (run management).
    "add_job_run_log_service": "kontext.jobs.job_run_management",
    "get_job_run_logs_service": "kontext.jobs.job_run_management",
    "get_job_run_resource_service": "kontext.jobs.job_run_management",
    "get_job_run_service": "kontext.jobs.job_run_management",
    "list_job_runs_service": "kontext.jobs.job_run_management",
    "reset_job_runs_service": "kontext.jobs.job_run_management",
    "update_job_run_progress_service": "kontext.jobs.job_run_management",
    "update_job_run_status_service": "kontext.jobs.job_run_management",
    "update_job_run_worker_service": "kontext.jobs.job_run_management",
    "EventService": "kontext.jobs.events",
    "build_display_summary": "kontext.jobs.job_run_summary",
    "enrich_job_run_display_summary": "kontext.jobs.job_run_summary",
    # Orchestration (run creation, status hooks, execution runs).
    "create_job_run_and_maybe_dispatch": "kontext.jobs.job_run_dispatch",
    "create_queued_job_run_and_maybe_dispatch": "kontext.jobs.job_run_dispatch",
    "handle_run_status_change_hook": "kontext.jobs.job_run_dispatch",
    "ExecutionLifecycleService": "kontext.jobs.lifecycle",
    "ExecutionRunInputValidationError": "kontext.jobs.lifecycle",
    "ResolvedExecutionRunInput": "kontext.jobs.lifecycle",
    "JobRunPollingResult": "kontext.jobs.polling",
    "poll_job_run_completion": "kontext.jobs.polling",
    "ExecutionRunService": "kontext.jobs.runs",
    "build_log_event": "kontext.jobs.runs",
    "build_status_event": "kontext.jobs.runs",
    "get_job_run_resource_async": "kontext.jobs.runs",
    "infer_execution_run_kind": "kontext.jobs.runs",
    "map_job_run_status": "kontext.jobs.runs",
    "project_execution_run": "kontext.jobs.runs",
    "WorkflowJobStepDefinition": "kontext.jobs.workflows",
    "WorkflowOrchestrationService": "kontext.jobs.workflows",
    "WorkflowProjectionMetadata": "kontext.jobs.workflows",
    "WorkflowStartRequest": "kontext.jobs.workflows",
    "extract_workflow_projection_metadata": "kontext.jobs.workflows",
    "get_workflow_metadata": "kontext.jobs.workflows",
    "parse_engine_metadata_json": "kontext.jobs.workflows",
    "upsert_workflow_metadata_json": "kontext.jobs.workflows",
    # Python execution (agent/notebook-facing orchestration).
    "NotebookPythonExecutionError": "kontext.jobs.notebook_python_execution",
    "NotebookPythonExecutionService": "kontext.jobs.notebook_python_execution",
    "PythonExecutionService": "kontext.jobs.python_execution",
    "PythonExecutionServiceResult": "kontext.jobs.python_execution",
}

__all__ = [
    "BasePythonJob",
    "CronParser",
    "EventService",
    "ExecutionLifecycleService",
    "ExecutionRunInputValidationError",
    "ExecutionRunService",
    "IPythonJob",
    "JobExecutionService",
    "JobRequiredPermissions",
    "JobRunPollingResult",
    "JobSchedulerService",
    "NotebookPythonExecutionError",  # pyright: ignore[reportUnsupportedDunderAll]
    "NotebookPythonExecutionService",  # pyright: ignore[reportUnsupportedDunderAll]
    "PythonExecutionService",  # pyright: ignore[reportUnsupportedDunderAll]
    "PythonExecutionServiceResult",  # pyright: ignore[reportUnsupportedDunderAll]
    "ResolvedExecutionRunInput",
    "WorkflowJobStepDefinition",
    "WorkflowOrchestrationService",
    "WorkflowProjectionMetadata",
    "WorkflowStartRequest",
    "add_job_run_log_service",
    "build_display_summary",
    "build_job_execution_message",
    "build_log_event",
    "build_status_event",
    "create_job_run_and_maybe_dispatch",
    "create_job_service",
    "create_queued_job_run_and_maybe_dispatch",
    "delete_job_service",
    "enrich_job_run_display_summary",
    "extract_workflow_projection_metadata",
    "get_job_resource_service",
    "get_job_run_logs_service",
    "get_job_run_resource_async",
    "get_job_run_resource_service",
    "get_job_run_service",
    "get_job_service",
    "get_job_type_service",
    "get_workflow_metadata",
    "handle_run_status_change_hook",
    "infer_execution_run_kind",
    "job",
    "list_job_runs_service",
    "list_job_types_service",
    "list_jobs_service",
    "map_job_run_status",
    "params_model_to_job_params",
    "parse_engine_metadata_json",
    "poll_job_run_completion",
    "project_execution_run",
    "reset_job_runs_service",
    "schedule_job_service",
    "update_job_run_progress_service",
    "update_job_run_status_service",
    "update_job_run_worker_service",
    "update_job_service",
    "upsert_workflow_metadata_json",
]


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'kontext.jobs' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)
