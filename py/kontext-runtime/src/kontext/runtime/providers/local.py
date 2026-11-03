"""Local runtime composition: capabilities resolved in this process.

Unlike a client-backed provider, which reaches the platform over the API, this
composes services that talk to the local database and filesystem directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from kontext.common.project_scoped import ProjectIdMismatchError
from kontext.common.protocols import (
    AgentRuntimeStorageProtocol,
    ICatalogIndexServiceProtocol,
    ICatalogManagementServiceProtocol,
    IChatSessionProtocol,
    IDataProfilingProtocol,
    IExecutionRunContextServiceProtocol,
    IFileServiceProtocol,
    IJobRunServiceProtocol,
    IKnowledgeServiceProtocol,
    ILanguageModelProtocol,
    IProjectServiceProtocol,
    IQuerySessionServiceProtocol,
    RuntimeProviderProtocol,
)
from kontext.common.python_execution.runner import DEFAULT_RUNTIME_PROFILE
from kontext.common.query.engine import (
    QueryEngineRequest,
    QueryEngineType,
    QueryExecutionEngine,
)
from kontext.engine.adapters import (
    LocalChatSessionService,
    LocalExecutionRunContextService,
    LocalJobRunService,
)
from kontext.execution.scheduling import handle_run_status_change_hook
from kontext.llm import LanguageModelService
from kontext.project import ProjectService
from kontext.query.in_process_query_session_service import (
    InProcessQuerySessionService,
)
from kontext.runtime.services.agent_runtime_storage_service import (
    AgentRuntimeStorageService,
)
from kontext.storage.providers.base import BaseStorageProvider

if TYPE_CHECKING:
    from kontext.common.python_execution.runner import PythonRunnerBackend, PythonSessionRunner


class LocalRuntimeProvider(RuntimeProviderProtocol):
    """Runtime composition root for local, direct-access services.

    Composition guidance: providers are frequently rebuilt per request or per
    job run, so they must stay cheap to construct and disposable — lazy-init
    lightweight, project-scoped services (as below). Anything expensive or
    connection-bound (HTTP clients, auth managers/token refreshers, database
    drivers) is constructed once per process and shared by the composition
    root instead, never rebuilt inside a provider instance. A future
    client-backed (API/HTTP) provider must follow this when it is added
    behind the same ports.
    """

    def __init__(
        self,
        project_id: str,
        *,
        storage_provider: BaseStorageProvider | None = None,
        query_session_service: IQuerySessionServiceProtocol | None = None,
    ) -> None:
        from kontext.storage import get_storage_provider

        self._project_id = str(project_id)
        self._storage_provider: BaseStorageProvider = storage_provider or get_storage_provider()
        self._catalog_service: ICatalogManagementServiceProtocol | None = None
        self._file_service: IFileServiceProtocol | None = None
        self._query_session_service: IQuerySessionServiceProtocol | None = query_session_service
        self._project_service: IProjectServiceProtocol | None = None
        self._job_run_service: IJobRunServiceProtocol | None = None
        self._execution_run_context_service: IExecutionRunContextServiceProtocol | None = None
        self._chat_session_service: IChatSessionProtocol | None = None
        self._language_model_service: ILanguageModelProtocol | None = None
        self._agent_runtime_storage_service: AgentRuntimeStorageProtocol | None = None
        self._data_profiling_service: IDataProfilingProtocol | None = None
        self._catalog_index_services: dict[str | None, ICatalogIndexServiceProtocol] = {}
        self._knowledge_service: IKnowledgeServiceProtocol | None = None

    def get_catalog_service(self) -> ICatalogManagementServiceProtocol | None:
        if self._catalog_service is None:
            from kontext.catalog import CatalogManagementService

            self._catalog_service = CatalogManagementService(
                project_id=self._project_id,
                runtime_provider=self,
            )
        return self._catalog_service

    def get_file_service(self) -> IFileServiceProtocol | None:
        if self._file_service is None:
            from kontext.file import FileService

            self._file_service = FileService(
                project_id=self._project_id,
                storage_provider=self._storage_provider,
            )
        return self._file_service

    def get_query_session_service(self) -> IQuerySessionServiceProtocol | None:
        if self._query_session_service is None:
            self._query_session_service = InProcessQuerySessionService(
                project_id=self._project_id,
                runtime_provider=self,
            )
        return self._query_session_service

    def get_project_service(self) -> IProjectServiceProtocol | None:
        if self._project_service is None:
            self._project_service = ProjectService(project_id=UUID(self._project_id))
        return self._project_service

    def get_job_run_service(self) -> IJobRunServiceProtocol | None:
        if self._job_run_service is None:
            self._job_run_service = LocalJobRunService(
                self._project_id,
                on_terminal_status=handle_run_status_change_hook,
            )
        return self._job_run_service

    def get_execution_run_context_service(
        self,
    ) -> IExecutionRunContextServiceProtocol | None:
        if self._execution_run_context_service is None:
            self._execution_run_context_service = LocalExecutionRunContextService(self._project_id)
        return self._execution_run_context_service

    def get_chat_session_service(self) -> IChatSessionProtocol | None:
        if self._chat_session_service is None:
            self._chat_session_service = LocalChatSessionService(project_id=self._project_id)
        return self._chat_session_service

    def get_language_model_service(self) -> ILanguageModelProtocol | None:
        if self._language_model_service is None:
            self._language_model_service = LanguageModelService()
        return self._language_model_service

    def get_agent_runtime_storage_service(
        self,
    ) -> AgentRuntimeStorageProtocol | None:
        if self._agent_runtime_storage_service is None:
            self._agent_runtime_storage_service = AgentRuntimeStorageService()
        return self._agent_runtime_storage_service

    def get_data_profiling_service(self) -> IDataProfilingProtocol | None:
        if self._data_profiling_service is None:
            from kontext.file.profiling import DefaultDataProfilingService

            self._data_profiling_service = DefaultDataProfilingService(project_id=self._project_id)
        return self._data_profiling_service

    def create_python_runner_backend(
        self,
        backend_name: str = "kernel",
        *,
        runtime_profile: str = DEFAULT_RUNTIME_PROFILE,
    ) -> PythonRunnerBackend:
        """Select the managed Python runner backend (composition concern)."""
        from kontext.runtime import create_python_runner_backend

        return create_python_runner_backend(
            backend_name,
            runtime_profile=runtime_profile,
        )

    def create_python_session_runner(self) -> PythonSessionRunner | None:
        """Expose the supervisor's session kernels when they are installed."""
        from kontext.kernel.session_runner import get_session_runner

        return get_session_runner()

    def get_catalog_index_service(
        self,
        catalog_connection_id: str | None = None,
    ) -> ICatalogIndexServiceProtocol | None:
        cached = self._catalog_index_services.get(catalog_connection_id)
        if cached is None:
            from kontext.catalog import CatalogIndexService

            cached = CatalogIndexService(
                project_id=self._project_id,
                catalog_connection_id=catalog_connection_id,
                runtime_provider=self,
            )
            self._catalog_index_services[catalog_connection_id] = cached
        return cached

    def get_knowledge_service(
        self,
    ) -> IKnowledgeServiceProtocol | None:
        if self._knowledge_service is None:
            from kontext.catalog.knowledge_service import OKFKnowledgeService

            self._knowledge_service = OKFKnowledgeService(
                self._project_id,
                runtime_provider=self,
            )
        return self._knowledge_service

    def get_query_execution_engine(
        self,
        engine_type: QueryEngineType,
        request: QueryEngineRequest,
        *,
        query_session_service: IQuerySessionServiceProtocol | None = None,
    ) -> QueryExecutionEngine | None:
        if str(request.project_id) != self._project_id:
            raise ProjectIdMismatchError(
                service_project_id=self._project_id,
                method_project_id=str(request.project_id),
            )

        if engine_type == QueryEngineType.DUCKDB:
            from kontext.engine.session.duckdb import DuckDBQueryEngine, SessionConfig

            return DuckDBQueryEngine(
                config=SessionConfig(
                    project_id=request.project_id,
                    session_id=request.session_id,
                    catalog_connection_id=request.catalog_connection_id,
                    default_namespace=request.default_namespace,
                    default_entity_id=request.default_entity_id,
                    user_id=request.user_id,
                    session_name=request.session_name,
                    persistent=request.persistent,
                    shadow=request.shadow,
                ),
                runtime_provider=self,
                query_session_service=query_session_service,
            )

        if engine_type in {
            QueryEngineType.SQLSERVER,
            QueryEngineType.ORACLE,
            QueryEngineType.TERADATA,
        }:
            from kontext.engine.session.live_sql import (
                LiveSqlQueryEngine,
                LiveSqlSessionConfig,
            )

            if request.catalog_connection_id is None:
                raise ValueError(
                    "Live SQL engines resolve a connection: the engine request "
                    "must carry catalog_connection_id."
                )

            return LiveSqlQueryEngine(
                config=LiveSqlSessionConfig(
                    project_id=request.project_id,
                    catalog_connection_id=request.catalog_connection_id,
                    default_namespace=request.default_namespace,
                    default_entity_id=request.default_entity_id,
                    session_id=request.session_id,
                    shadow=request.shadow,
                ),
                query_session_service=query_session_service,
            )

        return None
