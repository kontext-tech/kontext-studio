"""Durable session-scoped Python execution job."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from kontext.auth import FilePermissions, JobPermissions
from kontext.common.constants import MAX_PYTHON_CODE_CHARS
from kontext.common.jobs.trigger_actor import agent_actor
from kontext.common.python_execution.helpers import uses_kontext_execute_sql
from kontext.common.python_execution.runner import (
    PythonRunnerBackend,
    PythonRunnerHostBridge,
    PythonRunnerRequest,
    PythonRunnerResult,
)
from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.jobs.python_data_hydration import hydrate_data_payloads
from kontext.schema import ArtifactOrigin, JobCategory, TriggerActorModel

# Re-exported for the bridge tests and for callers that cap payloads.
from .python_host_bridge import _SAVE_TABLE_MAX_ROWS as _SAVE_TABLE_MAX_ROWS
from .python_host_bridge import ManagedPythonBridge


class ExecutePythonScriptParams(BaseJobParams):
    chat_session_id: str | None = Field(
        default=None,
        description="Chat session ID that triggered the execution",
    )
    query_session_id: str | None = Field(
        default=None,
        description="Existing query session ID for managed SQL access",
    )
    catalog_connection_id: str | None = Field(
        default=None,
        description="Default catalog connection for managed SQL access",
    )
    default_namespace: str | None = Field(
        default=None,
        description="Default namespace for managed SQL access",
    )
    default_entity_id: str | None = Field(
        default=None,
        description="Default entity ID for managed SQL access",
    )
    engine_type: str | None = Field(
        default=None,
        description="Sticky query engine type for managed SQL access",
    )
    code: str = Field(
        ..., min_length=1, max_length=MAX_PYTHON_CODE_CHARS, description="Python code"
    )
    data_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Scoped data IDs mapped to persisted inline-data file IDs",
    )
    triggered_by: TriggerActorModel | None = Field(
        default=None,
        description="Actor that triggered the execution (used for artifact provenance)",
    )
    runtime_backend: str = Field(
        default="kernel",
        description="Internal python runner backend identifier",
    )
    runtime_profile: str = Field(
        default="ml-default",
        description="Managed Python runtime profile",
    )
    timeout_seconds: int = Field(default=300, ge=1, le=1800)
    memory_limit_mb: int = Field(default=8192, ge=256, le=16384)
    stdout_limit_bytes: int = Field(default=131072, ge=1024, le=1048576)
    stderr_limit_bytes: int = Field(default=131072, ge=1024, le=1048576)
    workspace_limit_bytes: int = Field(default=1073741824, ge=1048576, le=2147483648)

    @field_validator("chat_session_id")
    @classmethod
    def _validate_uuid(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        UUID(value)
        return value


@job(
    job_type="python.jobs.ExecutePythonScriptJob",
    name="Execute Python Script",
    description=("Runs session-scoped Python code inside a managed local CPython subprocess"),
    category=JobCategory.DATAPROCESSING,
    params_model=ExecutePythonScriptParams,
    required_permissions=[JobPermissions.EXECUTE, FilePermissions.READ],
    display_parameter="code",
    is_system_job=True,
    icon="code",
)
class ExecutePythonScriptJob(BasePythonJob[ExecutePythonScriptParams]):
    async def execute_job(
        self, context: JobContext, parameters: ExecutePythonScriptParams
    ) -> JobResult:
        project_id = context.project_id
        if not project_id:
            return JobResult.error_result("Project ID not available in job context")

        requires_python_sql = uses_kontext_execute_sql(parameters.code)
        if requires_python_sql and not _has_python_sql_query_context(parameters):
            error_message = (
                "Managed Python SQL execution requires an active query context. "
                "Run SQL first in this chat session or select a catalog scope before "
                "using `kontext.execute_sql(...)`."
            )
            await context.log_warning(
                "Managed Python SQL execution rejected because query context is missing",
                {"ChatSessionId": parameters.chat_session_id},
            )
            return JobResult.error_result(
                error_message,
                data={
                    "type": "python_execution",
                    "success": False,
                    "message": error_message,
                    "error": error_message,
                    "targetType": "session",
                    "outputs": [],
                },
            )

        await context.log_info(
            "Starting managed Python script execution",
            {
                "ChatSessionId": parameters.chat_session_id,
                "RuntimeBackend": parameters.runtime_backend,
                "RuntimeProfile": parameters.runtime_profile,
                "ScopedDataIds": sorted(parameters.data_sources.keys()),
                "ManagedSqlEnabled": requires_python_sql,
            },
        )

        file_service = context.get_file_service()
        data_payloads, skipped_data_ids = await hydrate_data_payloads(
            project_id=project_id,
            data_sources=parameters.data_sources,
            file_service=file_service,
        )
        if skipped_data_ids:
            await context.log_warning(
                "Managed Python script skipped unresolvable data sources",
                {"SkippedDataIds": skipped_data_ids},
            )

        backend = context.get_runtime_provider().create_python_runner_backend(
            parameters.runtime_backend,
            runtime_profile=parameters.runtime_profile,
        )
        host_bridge = _ManagedPythonBridge(context=context, parameters=parameters)
        runner_result = await _run_python_script(
            context=context,
            parameters=parameters,
            data_payloads=data_payloads,
            host_bridge=host_bridge,
            session_id=_script_session_id(parameters, context),
            backend=backend,
        )

        execution_payload = {
            "type": "python_execution",
            "success": runner_result.success,
            "message": runner_result.message,
            "error": runner_result.error,
            "targetType": "session",
            "outputs": runner_result.outputs,
        }
        if host_bridge.saved_tables:
            execution_payload["savedTables"] = host_bridge.saved_tables
        # Stamp the run-level provenance here as well: the envelope is returned
        # to HITL clients straight from the job payload (server tool bodies
        # never run for ``external_execution`` tools), so the tool-side stamp
        # alone would leave session-script results without provenance.
        execution_payload["provenance"] = host_bridge.provenance().model_dump(
            by_alias=True, exclude_none=True
        )

        if runner_result.success:
            await context.log_info(
                "Managed Python script execution completed successfully",
                {"OutputCount": len(runner_result.outputs)},
            )
            return JobResult.success_result(runner_result.message, data=execution_payload)

        await context.log_error(
            "Managed Python script execution failed",
            {"Error": runner_result.error, "OutputCount": len(runner_result.outputs)},
        )
        return JobResult.error_result(
            runner_result.error or runner_result.message,
            data=execution_payload,
        )


def _has_python_sql_query_context(parameters: ExecutePythonScriptParams) -> bool:
    return any(
        [
            parameters.query_session_id,
            parameters.catalog_connection_id,
            parameters.default_namespace,
            parameters.default_entity_id,
        ]
    )


def _script_session_id(
    parameters: ExecutePythonScriptParams,
    context: JobContext,
) -> str:
    """Key session-scoped Python by chat/query session, else the job run.

    Chat scripts share a namespace across calls in the same chat session; a run
    with no session scope gets a unique id so it never shares state by accident.
    """
    from kontext.common.python_execution.kernel_identity import (
        chat_session_kernel_id,
        query_session_kernel_id,
    )

    if parameters.chat_session_id:
        return chat_session_kernel_id(parameters.chat_session_id)
    if parameters.query_session_id:
        return query_session_kernel_id(parameters.query_session_id)
    return f"run:{context.job_run_id}"


async def _run_python_script(
    *,
    context: JobContext,
    parameters: ExecutePythonScriptParams,
    data_payloads: dict[str, str],
    host_bridge: PythonRunnerHostBridge | None,
    session_id: str,
    backend: PythonRunnerBackend,
) -> PythonRunnerResult:
    """Run a session-scoped script in a session kernel when one is available.

    The supervisor installs a :class:`SessionKernelManager`; when absent, fall
    back to the single-use runner backend.
    """
    session_runner = context.get_runtime_provider().create_python_session_runner()
    if session_runner is not None:
        return await session_runner.run(
            session_id=session_id,
            code=parameters.code,
            host_bridge=host_bridge,
            data_payloads=data_payloads,
            timeout_seconds=parameters.timeout_seconds,
            stdout_limit_bytes=parameters.stdout_limit_bytes,
            stderr_limit_bytes=parameters.stderr_limit_bytes,
            # Chat/query sessions are reusable; a bare run id is not.
            ephemeral=not (parameters.chat_session_id or parameters.query_session_id),
        )

    return await backend.run(
        PythonRunnerRequest(
            code=parameters.code,
            data_payloads=data_payloads,
            host_bridge=host_bridge,
            timeout_seconds=parameters.timeout_seconds,
            memory_limit_mb=parameters.memory_limit_mb,
            stdout_limit_bytes=parameters.stdout_limit_bytes,
            stderr_limit_bytes=parameters.stderr_limit_bytes,
            workspace_limit_bytes=parameters.workspace_limit_bytes,
            runtime_profile=parameters.runtime_profile,
            run_id=context.job_run_id,
        )
    )


class _ManagedPythonBridge(ManagedPythonBridge):
    """Session-script bridge: agent provenance plus managed SQL access."""

    def __init__(
        self,
        *,
        context: JobContext,
        parameters: ExecutePythonScriptParams,
    ) -> None:
        super().__init__(
            context=context,
            chat_session_id=parameters.chat_session_id,
            origin=ArtifactOrigin.AGENTPYTHON,
            triggered_by=parameters.triggered_by or agent_actor("python_tool"),
            query_parameters=parameters,
        )
