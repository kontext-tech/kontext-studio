"""Kontext Jobs Package.

Job execution framework for Kontext Python jobs.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kontext.common.messaging import IQueueClient, QueueMessage

    from .base import BasePythonJob, IPythonJob
    from .decorators import job, params_model_to_job_params
    from .dispatch import build_job_execution_message
    from .job_execution_service import (
        JobExecutionService,
    )
    from .permissions import JobRequiredPermissions
    from .scheduling import CronParser, JobSchedulerService


_EXPORTS = {
    "BasePythonJob": "kontext.jobs.base",
    "IPythonJob": "kontext.jobs.base",
    "job": "kontext.jobs.decorators",
    "params_model_to_job_params": "kontext.jobs.decorators",
    "build_job_execution_message": "kontext.jobs.dispatch",
    "JobExecutionService": "kontext.jobs.job_execution_service",
    "JobRequiredPermissions": "kontext.jobs.permissions",
    "IQueueClient": "kontext.common.messaging",
    "QueueMessage": "kontext.common.messaging",
    "CronParser": "kontext.jobs.scheduling",
    "JobSchedulerService": "kontext.jobs.scheduling",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'kontext.jobs' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)


__all__ = [
    # Base classes
    "BasePythonJob",
    # Scheduling
    "CronParser",
    "IPythonJob",
    # Queue client
    "IQueueClient",
    # Job execution
    "JobExecutionService",
    # Permissions
    "JobRequiredPermissions",
    "JobSchedulerService",
    "QueueMessage",
    # Dispatch utilities
    "build_job_execution_message",
    # Decorators
    "job",
    "params_model_to_job_params",
]
