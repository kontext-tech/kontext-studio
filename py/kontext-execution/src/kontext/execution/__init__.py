"""Execution orchestration package for long-running Kontext work."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .events import EventService
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

if TYPE_CHECKING:
    from .notebook_python_execution import (
        NotebookPythonExecutionError,
        NotebookPythonExecutionService,
    )
    from .python_execution import PythonExecutionService, PythonExecutionServiceResult

__all__ = [
    "EventService",
    "ExecutionLifecycleService",
    "ExecutionRunInputValidationError",
    "ExecutionRunService",
    "JobRunPollingResult",
    "NotebookPythonExecutionError",
    "NotebookPythonExecutionService",
    "PythonExecutionService",
    "PythonExecutionServiceResult",
    "ResolvedExecutionRunInput",
    "WorkflowJobStepDefinition",
    "WorkflowOrchestrationService",
    "WorkflowProjectionMetadata",
    "WorkflowStartRequest",
    "add_job_run_log_service",
    "build_display_summary",
    "build_log_event",
    "build_status_event",
    "create_job_service",
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
    "infer_execution_run_kind",
    "list_job_runs_service",
    "list_job_types_service",
    "list_jobs_service",
    "map_job_run_status",
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

_PYTHON_EXECUTION_EXPORTS = {
    "NotebookPythonExecutionError",
    "NotebookPythonExecutionService",
    "PythonExecutionService",
    "PythonExecutionServiceResult",
}


def __getattr__(name: str) -> Any:
    if name in _PYTHON_EXECUTION_EXPORTS:
        from .notebook_python_execution import (
            NotebookPythonExecutionError,
            NotebookPythonExecutionService,
        )
        from .python_execution import (
            PythonExecutionService,
            PythonExecutionServiceResult,
        )

        exports = {
            "NotebookPythonExecutionError": NotebookPythonExecutionError,
            "NotebookPythonExecutionService": NotebookPythonExecutionService,
            "PythonExecutionService": PythonExecutionService,
            "PythonExecutionServiceResult": PythonExecutionServiceResult,
        }
        return exports[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
