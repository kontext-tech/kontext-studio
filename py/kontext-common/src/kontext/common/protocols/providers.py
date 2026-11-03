"""Provider/port contracts: capability surfaces resolved by composition.

Single-method per-capability fragments were collapsed into the aggregate
surfaces they compose. Only two fragments remain, each with real adopters outside
this module; the aggregates now declare their capabilities directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

from kontext.schema import (
    QueryEngineType,
)

if TYPE_CHECKING:
    from kontext.common.python_execution.runner import (
        PythonRunnerBackend,
        PythonSessionRunner,
    )
    from kontext.common.query.engine import QueryEngineRequest, QueryExecutionEngine
from kontext.common.python_execution.runner import DEFAULT_RUNTIME_PROFILE

from .agent import AgentRuntimeStorageProtocol, ILanguageModelProtocol
from .catalog import ICatalogIndexServiceProtocol, ICatalogManagementServiceProtocol
from .chat import IChatSessionProtocol
from .execution import IExecutionRunContextServiceProtocol
from .files import IFileServiceProtocol
from .jobs import IJobRunServiceProtocol
from .knowledge import IKnowledgeServiceProtocol
from .profiling import IDataProfilingProtocol
from .project import IProjectServiceProtocol
from .query import IQuerySessionServiceProtocol


class CatalogManagementServiceProviderProtocol(Protocol):
    """Provider capable of resolving the catalog management service."""

    def get_catalog_service(self) -> ICatalogManagementServiceProtocol | None: ...


class AgentRuntimeStorageProviderProtocol(Protocol):
    """Provider capable of resolving agent runtime storage."""

    def get_agent_runtime_storage_service(
        self,
    ) -> AgentRuntimeStorageProtocol | None: ...


def resolve_agent_runtime_storage_provider(
    runtime_provider: Any,
) -> AgentRuntimeStorageProviderProtocol | None:
    """Structurally narrow *runtime_provider* to the agent-runtime storage port.

    Providers typed against narrower surfaces (e.g.
    :class:`AIToolkitServiceProviderProtocol`) may or may not expose
    agent-runtime storage. The port is deliberately not ``runtime_checkable``,
    so callers probe with ``hasattr`` instead of ``isinstance`` — this helper
    encodes that narrowing once instead of at every call site.
    """
    if runtime_provider is None or not hasattr(
        runtime_provider, "get_agent_runtime_storage_service"
    ):
        return None
    return cast(AgentRuntimeStorageProviderProtocol, runtime_provider)


class LanguageModelServiceProviderProtocol(Protocol):
    """Provider capable of resolving language-model services."""

    def get_language_model_service(self) -> ILanguageModelProtocol | None: ...


class QueryEngineResolverProtocol(Protocol):
    """Provider capable of resolving query execution engines."""

    def get_query_execution_engine(
        self,
        engine_type: QueryEngineType,
        request: QueryEngineRequest,
        *,
        query_session_service: IQuerySessionServiceProtocol | None = None,
    ) -> QueryExecutionEngine | None:
        """Build an engine for *engine_type* from the typed *request*.

        The request carries the session shape (project, session id, catalog
        connection, namespace/entity defaults, owner, shadow mode); providers
        map it onto their concrete session config. Returns ``None`` when the
        engine type is unsupported by this provider.
        """
        ...


class QueryRuntimeProviderProtocol(
    QueryEngineResolverProtocol,
    CatalogManagementServiceProviderProtocol,
    Protocol,
):
    """Minimum provider surface required for query runtime composition."""

    def get_query_session_service(self) -> IQuerySessionServiceProtocol | None: ...


class AIToolkitServiceProviderProtocol(
    CatalogManagementServiceProviderProtocol,
    AgentRuntimeStorageProviderProtocol,
    Protocol,
):
    """Provider surface needed by AI toolkits and tool execution."""

    def get_file_service(self) -> IFileServiceProtocol | None: ...

    def get_query_session_service(self) -> IQuerySessionServiceProtocol | None: ...

    def get_project_service(self) -> IProjectServiceProtocol | None: ...

    def get_chat_session_service(self) -> IChatSessionProtocol | None: ...

    def get_catalog_index_service(
        self,
        catalog_connection_id: str | None = None,
    ) -> ICatalogIndexServiceProtocol | None: ...

    def get_knowledge_service(self) -> IKnowledgeServiceProtocol | None: ...

    def get_query_execution_engine(
        self,
        engine_type: QueryEngineType,
        request: QueryEngineRequest,
        *,
        query_session_service: IQuerySessionServiceProtocol | None = None,
    ) -> QueryExecutionEngine | None:
        """Build an engine for *engine_type* from the typed *request*."""
        ...


class DataProfilingCapableProviderProtocol(Protocol):
    """Provider capable of resolving data-profiling services."""

    def get_data_profiling_service(self) -> IDataProfilingProtocol | None: ...


class JobRuntimeProviderProtocol(
    CatalogManagementServiceProviderProtocol,
    AgentRuntimeStorageProviderProtocol,
    QueryEngineResolverProtocol,
    DataProfilingCapableProviderProtocol,
    Protocol,
):
    """Provider surface needed by Python job execution and job contexts."""

    def get_file_service(self) -> IFileServiceProtocol | None: ...

    def get_query_session_service(self) -> IQuerySessionServiceProtocol | None: ...

    def get_job_run_service(self) -> IJobRunServiceProtocol | None: ...

    def get_execution_run_context_service(
        self,
    ) -> IExecutionRunContextServiceProtocol | None: ...

    def get_chat_session_service(self) -> IChatSessionProtocol | None: ...

    def create_python_runner_backend(
        self,
        backend_name: str = "kernel",
        *,
        runtime_profile: str = DEFAULT_RUNTIME_PROFILE,
    ) -> PythonRunnerBackend: ...

    def create_python_session_runner(self) -> PythonSessionRunner | None:
        """Return the process-shared session-kernel runner, when installed."""
        ...


class AgentRuntimeProviderProtocol(
    AIToolkitServiceProviderProtocol,
    LanguageModelServiceProviderProtocol,
    AgentRuntimeStorageProviderProtocol,
    Protocol,
):
    """Provider surface needed by agent construction and runtime state."""


class RuntimeProviderProtocol(
    QueryRuntimeProviderProtocol,
    AIToolkitServiceProviderProtocol,
    LanguageModelServiceProviderProtocol,
    DataProfilingCapableProviderProtocol,
    Protocol,
):
    """Full runtime-provider surface used by the platform."""

    def get_project_service(self) -> IProjectServiceProtocol | None: ...

    def get_job_run_service(self) -> IJobRunServiceProtocol | None: ...

    def get_execution_run_context_service(
        self,
    ) -> IExecutionRunContextServiceProtocol | None: ...

    def create_python_runner_backend(
        self,
        backend_name: str = "kernel",
        *,
        runtime_profile: str = DEFAULT_RUNTIME_PROFILE,
    ) -> PythonRunnerBackend: ...

    def create_python_session_runner(self) -> PythonSessionRunner | None:
        """Return the process-shared session-kernel runner, when installed."""
        ...
