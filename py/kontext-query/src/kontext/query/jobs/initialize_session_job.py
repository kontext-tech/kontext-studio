"""
Initialize Session Job

Initializes a query session with catalog context, creates cloud storage
connections, and sets up Iceberg-backed relations for data querying.
Supports multiple engines including DuckDB, Snowflake, and others.
"""

import logging

from pydantic import Field

from kontext.common.query.engine import QueryEngineRequest
from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.jobs.permissions import JobRequiredPermissions
from kontext.query.engine_factory import resolve_engine_for_session
from kontext.schema import JobCategory, QueryEngineType, QuerySessionStatus

logger = logging.getLogger(__name__)


class InitializeSessionParams(BaseJobParams):
    """Parameters for initializing query sessions."""

    session_id: str = Field(..., description="Session ID to initialize")
    project_id: str = Field(..., description="Project ID for the session")
    catalog_connection_id: str | None = Field(
        default=None, description="Optional default catalog connection ID"
    )
    default_namespace: str | None = Field(default=None, description="Optional default namespace")
    default_entity_id: str | None = Field(default=None, description="Optional default entity ID")
    user_id: str | None = Field(default=None, description="User ID who owns the session")
    persistent: bool = Field(default=True, description="Whether the session is persistent")
    engine_type: QueryEngineType = Field(
        default=QueryEngineType.DUCKDB,
        description="The query engine type (e.g. DuckDB, Snowflake)",
    )


@job(
    job_type="python.jobs.InitializeSessionJob",
    name="Initialize Session",
    description="Initializes a query session with project and catalog context",
    category=JobCategory.SYSTEMMAINTENANCE,
    params_model=InitializeSessionParams,
    required_permissions=JobRequiredPermissions.SYSTEM_INTERNAL,
    display_parameter="session_id",
    is_system_job=True,
    icon="power",
)
class InitializeSessionJob(BasePythonJob[InitializeSessionParams]):
    """Job for initializing query sessions."""

    async def execute_job(
        self, context: JobContext, parameters: InitializeSessionParams
    ) -> JobResult:
        """Execute session initialization."""
        session_id = parameters.session_id
        project_id = parameters.project_id
        catalog_connection_id = parameters.catalog_connection_id
        default_namespace = parameters.default_namespace
        default_entity_id = parameters.default_entity_id
        user_id = parameters.user_id
        persistent = parameters.persistent

        try:
            await context.log_info(
                f"Starting to initialize {parameters.engine_type} session "
                f"{session_id}, project {project_id}",
                {
                    "session_id": session_id,
                    "project_id": project_id,
                    "engine_type": parameters.engine_type,
                },
            )

            runtime_provider = context.get_runtime_provider()
            query_session_service = context.get_query_session_service()
            session_vm = await query_session_service.get_query_session(
                session_id=session_id, project_id=project_id
            )
            session_name = session_vm.session_name if session_vm else session_id

            engine = await resolve_engine_for_session(
                engine_type=parameters.engine_type,
                runtime_provider=runtime_provider,
                request=QueryEngineRequest(
                    project_id=str(project_id),
                    session_id=session_id,
                    catalog_connection_id=catalog_connection_id,
                    default_namespace=default_namespace,
                    default_entity_id=default_entity_id,
                    user_id=user_id,
                    persistent=persistent,
                ),
            )
            await engine.connect()

            database_size = None
            if hasattr(engine, "get_session_file_size"):
                database_size = engine.get_session_file_size()  # type: ignore[attr-defined]

            await self._update_session_status(
                context,
                session_id,
                project_id,
                QuerySessionStatus.ACTIVE,
                database_size,
            )

            await context.log_info(
                f"Session {session_id} initialized successfully: {session_name}",
                {
                    "session_name": session_name,
                    "database_size_bytes": database_size,
                    "session_status": QuerySessionStatus.ACTIVE,
                },
            )

            return JobResult.success_result(
                f"Session initialized successfully: {session_name}",
                data={
                    "session_name": session_name,
                    "database_size_bytes": database_size,
                    "session_id": session_id,
                },
            )
        except Exception as e:
            logger.error(f"Failed to initialize session {session_id}: {e}")

            await context.log_error(
                f"Session initialization failed: {e!s}",
                {
                    "error_message": str(e),
                    "session_id": session_id,
                    "project_id": project_id,
                },
            )

            try:
                await self._update_session_status(
                    context, session_id, project_id, QuerySessionStatus.ERROR
                )
            except Exception as status_error:
                logger.warning(f"Failed to update session status to Error: {status_error}")

            return JobResult.error_result(f"Session initialization failed: {e!s}")

    async def _update_session_status(
        self,
        context: JobContext,
        session_id: str,
        project_id: str,
        status: QuerySessionStatus,
        database_size: int | None = None,
    ) -> None:
        """Update session status via API."""
        query_session_service = context.get_query_session_service()
        await query_session_service.update_query_session(
            session_id=session_id,
            project_id=project_id,
            status=status,
            database_size_bytes=database_size,
        )
