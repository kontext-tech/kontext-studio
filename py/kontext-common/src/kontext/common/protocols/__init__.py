"""Service and provider contracts shared across Kontext Python packages.

Operation-level interfaces live in one module per domain (``files``,
``catalog``, ``query``, ``project``, ``chat``, ``agent``, ``jobs``,
``execution``, ``knowledge``, ``profiling``). Capability/provider surfaces that
composition resolves live in :mod:`.providers`.

The facade is lazy so importing one contract does not load every protocol.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS: dict[str, str] = {
    # operation-level service contracts
    "AgentRuntimeStorageConfig": "agent",
    "AgentRuntimeStorageProtocol": "agent",
    "ILanguageModelProtocol": "agent",
    "ICatalogIndexServiceProtocol": "catalog",
    "ICatalogManagementServiceProtocol": "catalog",
    "IChatSessionProtocol": "chat",
    "ExecutionRunProvenance": "execution",
    "IExecutionRunContextServiceProtocol": "execution",
    "IFileServiceProtocol": "files",
    "IJobRunServiceProtocol": "jobs",
    "JobRunLogEntry": "jobs",
    "IKnowledgeServiceProtocol": "knowledge",
    "DataProfilingResult": "profiling",
    "IDataProfilingProtocol": "profiling",
    "IProjectServiceProtocol": "project",
    "IQuerySessionServiceProtocol": "query",
    # capability/provider surfaces
    "AgentRuntimeProviderProtocol": "providers",
    "AgentRuntimeStorageProviderProtocol": "providers",
    "AIToolkitServiceProviderProtocol": "providers",
    "CatalogManagementServiceProviderProtocol": "providers",
    "JobRuntimeProviderProtocol": "providers",
    "LanguageModelServiceProviderProtocol": "providers",
    "QueryEngineResolverProtocol": "providers",
    "QueryRuntimeProviderProtocol": "providers",
    "RuntimeProviderProtocol": "providers",
    "resolve_agent_runtime_storage_provider": "providers",
}

if TYPE_CHECKING:
    from .agent import (
        AgentRuntimeStorageConfig,
        AgentRuntimeStorageProtocol,
        ILanguageModelProtocol,
    )
    from .catalog import ICatalogIndexServiceProtocol, ICatalogManagementServiceProtocol
    from .chat import IChatSessionProtocol
    from .execution import ExecutionRunProvenance, IExecutionRunContextServiceProtocol
    from .files import IFileServiceProtocol
    from .jobs import IJobRunServiceProtocol, JobRunLogEntry
    from .knowledge import IKnowledgeServiceProtocol
    from .profiling import DataProfilingResult, IDataProfilingProtocol
    from .project import IProjectServiceProtocol
    from .providers import (
        AgentRuntimeProviderProtocol,
        AgentRuntimeStorageProviderProtocol,
        AIToolkitServiceProviderProtocol,
        CatalogManagementServiceProviderProtocol,
        JobRuntimeProviderProtocol,
        LanguageModelServiceProviderProtocol,
        QueryEngineResolverProtocol,
        QueryRuntimeProviderProtocol,
        RuntimeProviderProtocol,
        resolve_agent_runtime_storage_provider,
    )
    from .query import IQuerySessionServiceProtocol


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, name)


__all__ = sorted(_EXPORTS)  # pyright: ignore[reportUnsupportedDunderAll]
