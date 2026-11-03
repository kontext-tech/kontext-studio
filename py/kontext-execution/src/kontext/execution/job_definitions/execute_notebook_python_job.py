"""Durable notebook Python execution job."""

from __future__ import annotations

from uuid import UUID

from pydantic import Field, field_validator

from kontext.auth import FilePermissions, JobPermissions
from kontext.common.constants import MAX_PYTHON_CODE_CHARS
from kontext.common.jobs.trigger_actor import notebook_actor
from kontext.common.python_execution.runner import PythonRunnerRequest, PythonRunnerResult
from kontext.execution.python_data_hydration import hydrate_data_payloads
from kontext.jobs.base import BaseJobParams, BasePythonJob
from kontext.jobs.decorators import job
from kontext.jobs.job_context import JobContext
from kontext.jobs.job_result import JobResult
from kontext.schema import ArtifactOrigin, JobCategory, TriggerActorModel

from .python_host_bridge import ManagedPythonBridge


class ExecuteNotebookPythonParams(BaseJobParams):
    notebook_id: str = Field(..., description="Notebook file ID")
    block_id: str = Field(..., description="Notebook code block ID")
    chat_session_id: str | None = Field(
        default=None,
        description="Chat session ID that triggered the execution",
    )
    triggered_by: TriggerActorModel | None = Field(
        default=None,
        description="Actor that triggered the execution (artifact provenance)",
    )
    code: str = Field(
        ..., min_length=1, max_length=MAX_PYTHON_CODE_CHARS, description="Python code"
    )
    data_sources: dict[str, str] = Field(
        default_factory=dict,
        description="Scoped data IDs mapped to persisted inline-data file IDs",
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

    @field_validator("notebook_id", "block_id", "chat_session_id")
    @classmethod
    def _validate_uuid(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        UUID(value)
        return value


@job(
    job_type="python.jobs.ExecuteNotebookPythonJob",
    name="Execute Notebook Python",
    description="Runs notebook Python code inside a managed local CPython subprocess",
    category=JobCategory.DATAPROCESSING,
    params_model=ExecuteNotebookPythonParams,
    required_permissions=[JobPermissions.EXECUTE, FilePermissions.READ],
    display_parameter="code",
    is_system_job=True,
    icon="code",
)
class ExecuteNotebookPythonJob(BasePythonJob[ExecuteNotebookPythonParams]):
    async def execute_job(
        self, context: JobContext, parameters: ExecuteNotebookPythonParams
    ) -> JobResult:
        project_id = context.project_id
        if not project_id:
            return JobResult.error_result("Project ID not available in job context")

        await context.log_info(
            "Starting managed notebook Python execution",
            {
                "NotebookId": parameters.notebook_id,
                "BlockId": parameters.block_id,
                "RuntimeBackend": parameters.runtime_backend,
                "RuntimeProfile": parameters.runtime_profile,
                "ScopedDataIds": sorted(parameters.data_sources.keys()),
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
                "Managed notebook Python execution skipped unresolvable data sources",
                {"SkippedDataIds": skipped_data_ids},
            )

        host_bridge = ManagedPythonBridge(
            context=context,
            chat_session_id=parameters.chat_session_id,
            origin=ArtifactOrigin.NOTEBOOKRUN,
            triggered_by=parameters.triggered_by or notebook_actor(parameters.notebook_id),
            block_id=parameters.block_id,
        )
        runner_result = await _run_notebook_code(
            context=context,
            parameters=parameters,
            data_payloads=data_payloads,
            host_bridge=host_bridge,
        )

        if runner_result.stdout.strip():
            await context.log_info(
                "Captured notebook Python stdout",
                {"stdout": runner_result.stdout},
            )
        if runner_result.stderr.strip():
            await context.log_warning(
                "Captured notebook Python stderr",
                {"stderr": runner_result.stderr},
            )

        execution_payload = {
            "type": "python_execution",
            "success": runner_result.success,
            "message": runner_result.message,
            "error": runner_result.error,
            "targetType": "notebook",
            "outputs": runner_result.outputs,
        }
        if host_bridge.saved_tables:
            execution_payload["savedTables"] = host_bridge.saved_tables
        # Run-level provenance for direct run lookups (``get_execution_result_async``).
        # The notebook execution service also stamps the envelope for its route;
        # both derive the same values from the bridge.
        execution_payload["provenance"] = host_bridge.provenance().model_dump(
            by_alias=True, exclude_none=True
        )

        if runner_result.success:
            await context.log_info(
                "Managed notebook Python execution completed successfully",
                {"OutputCount": len(runner_result.outputs)},
            )
            return JobResult.success_result(runner_result.message, data=execution_payload)

        await context.log_error(
            "Managed notebook Python execution failed",
            {"Error": runner_result.error, "OutputCount": len(runner_result.outputs)},
        )
        return JobResult.error_result(
            runner_result.error or runner_result.message,
            data=execution_payload,
        )


async def _run_notebook_code(
    *,
    context: JobContext,
    parameters: ExecuteNotebookPythonParams,
    data_payloads: dict[str, str],
    host_bridge: ManagedPythonBridge | None = None,
) -> PythonRunnerResult:
    """Run notebook code in a session kernel when one is available.

    The supervisor installs a :class:`SessionKernelManager` for its process, so
    consecutive blocks of the same notebook share a namespace. When no manager
    is present (a one-shot CLI run), fall back to the single-use runner backend.
    """
    session_runner = context.get_runtime_provider().create_python_session_runner()
    if session_runner is not None:
        return await session_runner.run(
            # A notebook id is already a stable, unique session key.
            session_id=parameters.notebook_id,
            code=parameters.code,
            host_bridge=host_bridge,
            data_payloads=data_payloads,
            timeout_seconds=parameters.timeout_seconds,
            stdout_limit_bytes=parameters.stdout_limit_bytes,
            stderr_limit_bytes=parameters.stderr_limit_bytes,
        )

    backend = context.get_runtime_provider().create_python_runner_backend(
        parameters.runtime_backend,
        runtime_profile=parameters.runtime_profile,
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
