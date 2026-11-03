"""
Job dispatch utilities for creating self-contained job execution messages.

This module provides utilities for building JobExecutionMessage instances
that contain all information needed for job execution without DB lookups.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, overload
from uuid import UUID

from kontext.common.utils.datetime_utils import utc_now
from kontext.jobs.base import BaseJobParams
from kontext.schema import JobExecutionMessage

if TYPE_CHECKING:
    from kontext.jobs.base import BasePythonJob


@overload
def build_job_execution_message(
    *,
    job_class: type["BasePythonJob"],
    params: BaseJobParams,
    job_run_id: str | UUID,
    project_id: str | UUID,
    execution_id: str | None = None,
    timeout_minutes: int = 60,
    priority: int = 5,
    created_at: datetime | None = None,
) -> JobExecutionMessage: ...


@overload
def build_job_execution_message(
    *,
    job_type: str,
    job_name: str,
    parameters: dict[str, Any],
    job_run_id: str | UUID,
    project_id: str | UUID,
    execution_id: str | None = None,
    timeout_minutes: int = 60,
    priority: int = 5,
    created_at: datetime | None = None,
) -> JobExecutionMessage: ...


def build_job_execution_message(
    *,
    # Type-safe mode (provide job_class + params)
    job_class: type["BasePythonJob"] | None = None,
    params: BaseJobParams | None = None,
    # Dynamic mode (provide job_type + job_name + parameters)
    job_type: str | None = None,
    job_name: str | None = None,
    parameters: dict[str, Any] | None = None,
    # Common parameters
    job_run_id: str | UUID,
    project_id: str | UUID,
    execution_id: str | None = None,
    timeout_minutes: int = 60,
    priority: int = 5,
    created_at: datetime | None = None,
) -> JobExecutionMessage:
    """Build a self-contained job execution message.

    This function supports two modes:

    **Type-safe mode** (recommended for new code):
        Provide `job_class` and `params` for compile-time type checking.

    **Dynamic mode** (for queue/scheduler driven dispatch):
        Provide `job_type`, `job_name`, and `parameters` directly.

    Args:
        job_class: Job class with @job decorator (type-safe mode).
        params: Validated Pydantic parameter model (type-safe mode).
        job_type: Job type string like 'python.jobs.ExecuteQueryJob' (dynamic mode).
        job_name: Human-readable job name (dynamic mode).
        parameters: Job parameters dictionary (dynamic mode).
        job_run_id: Unique identifier for this job run.
        project_id: Project context for the job execution.
        execution_id: Human-readable execution ID (timestamp based).
        timeout_minutes: Job timeout in minutes (1-1440, default 60).
        priority: Job priority (0-10, default 5).
        created_at: When the job was created (defaults to now).

    Returns:
        JobExecutionMessage ready to be serialized and sent to the queue.

    Raises:
        ValueError: If neither mode is properly specified.
        TypeError: If params type doesn't match job's expected params model.

    Examples:
        Type-safe mode:
        >>> from kontext.query.jobs.execute_query_job import (
        ...     ExecuteQueryJob,
        ...     ExecuteQueryParams,
        ... )
        >>> params = ExecuteQueryParams(sql="SELECT 1")
        >>> msg = build_job_execution_message(
        ...     job_class=ExecuteQueryJob,
        ...     params=params,
        ...     job_run_id="550e8400-e29b-41d4-a716-446655440000",
        ...     project_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        ... )

        Dynamic mode:
        >>> msg = build_job_execution_message(
        ...     job_type="python.jobs.ExecuteQueryJob",
        ...     job_name="Execute Query",
        ...     parameters={"query": "SELECT 1"},
        ...     job_run_id="550e8400-e29b-41d4-a716-446655440000",
        ...     project_id="6ba7b810-9dad-11d1-80b4-00c04fd430c8",
        ... )
    """
    # Determine mode and extract job_type, job_name, parameters_dict
    if job_class is not None and params is not None:
        metadata = job_class.get_job_metadata()
        expected_model = job_class.get_params_model()

        if not isinstance(params, expected_model):
            raise TypeError(
                f"Expected {expected_model.__name__}, got {type(params).__name__}. "
                f"Params must match the job's defined params model."
            )

        resolved_job_type = metadata.type or ""
        resolved_job_name = metadata.name or ""
        parameters_dict = params.model_dump(by_alias=True)

    elif job_type is not None and job_name is not None:
        resolved_job_type = job_type
        resolved_job_name = job_name
        parameters_dict = parameters or {}

    else:
        raise ValueError(
            "Must provide either (job_class, params) for type-safe mode "
            "or (job_type, job_name, parameters) for dynamic mode."
        )

    return JobExecutionMessage(
        job_run_id=str(job_run_id),
        execution_id=execution_id,
        project_id=str(project_id),
        job_type=resolved_job_type,
        job_name=resolved_job_name,
        timeout_minutes=timeout_minutes,
        parameters=parameters_dict,
        created_at=created_at or utc_now(),
        priority=priority,
    )
