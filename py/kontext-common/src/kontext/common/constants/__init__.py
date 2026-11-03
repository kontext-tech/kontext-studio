"""
Constants package for Kontext Core.

This package provides centralized constants including environment variable names,
default values, and other configuration constants.
"""

from .agent import AgentTaskProfile
from .data_lake import DataLakeConstants
from .env_vars import (
    ALL_ENV_VARS,
    ApiEnvVars,
    AuthEnvVars,
    DatabaseEnvVars,
    InteractiveAuthDefaults,
    JobLeaseEnvVars,
    ModelEnvVars,
    PythonExecutionEnvVars,
    StorageEnvVars,
)
from .job_lease import (
    DEFAULT_JOB_RUN_LEASE_SECONDS,
    DEFAULT_JOB_RUN_MAX_LEASE_RECLAIMS,
    job_run_lease_seconds,
    job_run_max_lease_reclaims,
)
from .python_execution import (
    DEFAULT_MAX_CONSECUTIVE_KERNEL_FAILURES,
    MAX_PYTHON_CODE_CHARS,
    max_consecutive_kernel_failures,
)
from .query import QueryConstants
from .site_features import LOCAL_DEFAULT_SITE_FEATURES, SiteFeature
from .tool_names import (
    AGENT_TOOL_NAMES,
    DELEGATE_TASK_TO_MEMBER_TOOL_NAME,
    DELEGATE_TASK_TO_MEMBERS_TOOL_NAME,
    DELEGATION_TOOL_NAMES,
    EXECUTE_PYTHON_CODE_TOOL_NAME,
    EXECUTE_PYTHON_SCRIPT_TOOL_NAME,
    EXTERNAL_EXECUTION_TOOL_NAMES,
)

__all__ = [
    "AGENT_TOOL_NAMES",
    "ALL_ENV_VARS",
    "DEFAULT_JOB_RUN_LEASE_SECONDS",
    "DEFAULT_JOB_RUN_MAX_LEASE_RECLAIMS",
    "DEFAULT_MAX_CONSECUTIVE_KERNEL_FAILURES",
    "DELEGATE_TASK_TO_MEMBERS_TOOL_NAME",
    "DELEGATE_TASK_TO_MEMBER_TOOL_NAME",
    "DELEGATION_TOOL_NAMES",
    "EXECUTE_PYTHON_CODE_TOOL_NAME",
    "EXECUTE_PYTHON_SCRIPT_TOOL_NAME",
    "EXTERNAL_EXECUTION_TOOL_NAMES",
    "LOCAL_DEFAULT_SITE_FEATURES",
    "MAX_PYTHON_CODE_CHARS",
    "AgentTaskProfile",
    "ApiEnvVars",
    "AuthEnvVars",
    "DataLakeConstants",
    "DatabaseEnvVars",
    "InteractiveAuthDefaults",
    "JobLeaseEnvVars",
    "ModelEnvVars",
    "PythonExecutionEnvVars",
    "QueryConstants",
    "SiteFeature",
    "StorageEnvVars",
    "job_run_lease_seconds",
    "job_run_max_lease_reclaims",
    "max_consecutive_kernel_failures",
]
