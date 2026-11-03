"""Shared contracts and cross-cutting primitives for Kontext Python packages.

This is the dependency leaf of the workspace. The facade is intentionally lazy:
importing :mod:`kontext.common` (or any of its submodules) must not pull in
configuration, logging, schema models, protocols, and query primitives unless
the caller actually asks for them.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS: dict[str, str] = {
    # configuration
    "KontextConfig": "config",
    "get_config": "config",
    "provide_config": "config",
    "reset_config": "config",
    # constants
    "ALL_ENV_VARS": "constants",
    "LOCAL_DEFAULT_SITE_FEATURES": "constants",
    "AgentTaskProfile": "constants",
    "ApiEnvVars": "constants",
    "AuthEnvVars": "constants",
    "DatabaseEnvVars": "constants",
    "DataLakeConstants": "constants",
    "InteractiveAuthDefaults": "constants",
    "ModelEnvVars": "constants",
    "QueryConstants": "constants",
    "SiteFeature": "constants",
    "StorageEnvVars": "constants",
    # exceptions
    "BadRequestError": "exceptions",
    "ConflictError": "exceptions",
    "ForbiddenError": "exceptions",
    "KontextError": "exceptions",
    "NotFoundError": "exceptions",
    "UnauthorizedError": "exceptions",
    # cross-cutting infrastructure
    "configure_structured_logging": "logging",
    "IQueueClient": "messaging",
    "QueueMessage": "messaging",
    "PaginatedResult": "pagination",
    "ProjectIdMismatchError": "project_scoped",
    "ProjectScopedService": "project_scoped",
    "CronParser": "jobs.scheduling",
    # shared runtime data contracts
    "AgentConfig": "contracts",
    "CamelCaseModel": "pydantic",
    "KontextBaseModel": "pydantic",
    "ModelRuntime": "contracts",
    "PascalModel": "pydantic",
    "ResolvedModelConfig": "contracts",
    # query contracts
    "QueryEngineRequest": "query.engine",
    "QueryEngineType": "query.engine",
    "QueryExecutionEngine": "query.engine",
    # trigger actors
    "agent_actor": "jobs.trigger_actor",
    "chat_session_actor": "jobs.trigger_actor",
    "event_actor": "jobs.trigger_actor",
    "file_actor": "jobs.trigger_actor",
    "format_trigger_actor": "jobs.trigger_actor",
    "notebook_actor": "jobs.trigger_actor",
    "scheduler_actor": "jobs.trigger_actor",
    "system_actor": "jobs.trigger_actor",
    "user_actor": "jobs.trigger_actor",
}

if TYPE_CHECKING:
    from .config import KontextConfig, get_config, provide_config, reset_config
    from .constants import (
        ALL_ENV_VARS,
        LOCAL_DEFAULT_SITE_FEATURES,
        AgentTaskProfile,
        ApiEnvVars,
        AuthEnvVars,
        DatabaseEnvVars,
        DataLakeConstants,
        InteractiveAuthDefaults,
        ModelEnvVars,
        QueryConstants,
        SiteFeature,
        StorageEnvVars,
    )
    from .contracts import AgentConfig, ModelRuntime, ResolvedModelConfig
    from .exceptions import (
        BadRequestError,
        ConflictError,
        ForbiddenError,
        KontextError,
        NotFoundError,
        UnauthorizedError,
    )
    from .jobs.scheduling import CronParser
    from .jobs.trigger_actor import (
        agent_actor,
        chat_session_actor,
        event_actor,
        file_actor,
        format_trigger_actor,
        notebook_actor,
        scheduler_actor,
        system_actor,
        user_actor,
    )
    from .logging import configure_structured_logging
    from .messaging import IQueueClient, QueueMessage
    from .pagination import PaginatedResult
    from .project_scoped import ProjectIdMismatchError, ProjectScopedService
    from .pydantic import CamelCaseModel, KontextBaseModel, PascalModel
    from .query.engine import QueryEngineRequest, QueryEngineType, QueryExecutionEngine


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, name)


__all__ = sorted(_EXPORTS)  # pyright: ignore[reportUnsupportedDunderAll]
