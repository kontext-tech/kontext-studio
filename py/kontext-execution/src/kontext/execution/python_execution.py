"""Notebook-oriented Python execution orchestration."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from math import ceil
from uuid import UUID

from kontext.common.jobs.trigger_actor import format_trigger_actor
from kontext.data import JobDataService, JobRunDataService
from kontext.execution.polling import poll_job_run_completion
from kontext.schema import (
    CodeExecutionOutput,
    CodeTextOutput,
    CreateJobRequest,
    ExecutionRunModel,
    JobRetryStrategy,
    JobRunModel,
    JobTriggerType,
    PythonExecutionResult,
    PythonExecutionTargetType,
    TriggerActorModel,
)

from .job_definitions.execute_notebook_python_job import (
    ExecuteNotebookPythonJob,
    ExecuteNotebookPythonParams,
)
from .job_definitions.execute_python_script_job import (
    ExecutePythonScriptJob,
    ExecutePythonScriptParams,
)
from .runs import project_execution_run

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PythonExecutionServiceResult:
    execution_run: ExecutionRunModel
    python_result: PythonExecutionResult
    code: str | None = None
    # Whether the run failed in the execution infrastructure (kernel could
    # not start/finish, run wedged) rather than in user code. Callers use
    # this to drive retry policies without mis-counting ordinary cell errors.
    infra_failure: bool = False


class PythonExecutionService:
    async def get_execution_result_async(
        self,
        *,
        project_id: UUID | str,
        run_id: UUID | str,
    ) -> PythonExecutionServiceResult:
        project_uuid = UUID(str(project_id))
        run_service = JobRunDataService(project_uuid)
        refreshed = await run_service.get_run_by_id_async(
            UUID(str(run_id)),
            include_job=True,
            include_trigger=False,
        )
        if refreshed is None:
            raise ValueError(
                f"Python execution run {run_id} was not found. Use the "
                "executionRunId returned in the Python execution envelope; a "
                "chat/session id never resolves to an execution run."
            )

        job_type = _job_type_from_job_run(refreshed)
        if job_type not in {
            ExecuteNotebookPythonJob.get_job_metadata().type,
            ExecutePythonScriptJob.get_job_metadata().type,
        }:
            raise ValueError(f"Run {run_id} is not a managed Python execution run.")

        return _python_service_result_from_job_run(refreshed)

    async def execute_script_async(
        self,
        *,
        project_id: UUID | str,
        code: str,
        data_sources: dict[str, str],
        chat_session_id: str | None = None,
        query_session_id: str | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: str | None = None,
        owner_id: UUID | str | None = None,
        triggered_by: TriggerActorModel | None = None,
        timeout_seconds: int = 300,
        memory_limit_mb: int = 8192,
        stdout_limit_bytes: int = 131072,
        stderr_limit_bytes: int = 131072,
        workspace_limit_bytes: int = 1073741824,
    ) -> PythonExecutionServiceResult:
        params = ExecutePythonScriptParams(
            chat_session_id=chat_session_id,
            query_session_id=query_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
            code=code,
            data_sources=data_sources,
            triggered_by=triggered_by,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
            workspace_limit_bytes=workspace_limit_bytes,
        )
        return await self._execute_job_async(
            project_id=project_id,
            owner_id=owner_id,
            triggered_by=triggered_by,
            params=params,
            metadata=ExecutePythonScriptJob.get_job_metadata(),
        )

    async def execute_notebook_code_async(
        self,
        *,
        project_id: UUID | str,
        notebook_id: str,
        block_id: str,
        code: str,
        data_sources: dict[str, str],
        chat_session_id: str | None = None,
        owner_id: UUID | str | None = None,
        triggered_by: TriggerActorModel | None = None,
        run_id: UUID | str | None = None,
        timeout_seconds: int = 300,
        memory_limit_mb: int = 8192,
        stdout_limit_bytes: int = 131072,
        stderr_limit_bytes: int = 131072,
        workspace_limit_bytes: int = 1073741824,
    ) -> PythonExecutionServiceResult:
        params = ExecuteNotebookPythonParams(
            notebook_id=notebook_id,
            block_id=block_id,
            chat_session_id=chat_session_id,
            triggered_by=triggered_by,
            code=code,
            data_sources=data_sources,
            timeout_seconds=timeout_seconds,
            memory_limit_mb=memory_limit_mb,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
            workspace_limit_bytes=workspace_limit_bytes,
        )
        return await self._execute_job_async(
            project_id=project_id,
            owner_id=owner_id,
            triggered_by=triggered_by,
            params=params,
            metadata=ExecuteNotebookPythonJob.get_job_metadata(),
            run_id=run_id,
        )

    async def _execute_job_async(
        self,
        *,
        project_id: UUID | str,
        owner_id: UUID | str | None,
        triggered_by: TriggerActorModel | None,
        params: ExecuteNotebookPythonParams | ExecutePythonScriptParams,
        metadata,
        run_id: UUID | str | None = None,
    ) -> PythonExecutionServiceResult:
        project_uuid = UUID(str(project_id))
        owner_uuid = UUID(str(owner_id)) if owner_id is not None else None

        job_service = JobDataService(project_uuid)
        timeout_minutes = max(5, ceil((params.timeout_seconds + 60) / 60))
        job_entity = await job_service.get_or_create_job_for_owner_async(
            job_type=metadata.type,
            owner_id=owner_uuid,
            request=CreateJobRequest(
                name=metadata.name or "Execute Python",
                type=metadata.type,
                description=metadata.description,
                timeout=timeout_minutes,
                is_enabled=True,
                retry_strategy=JobRetryStrategy.NONE,
                retry_limit=0,
            ),
            created_by=format_trigger_actor(triggered_by),
        )
        if job_entity is None or job_entity.id is None:
            raise RuntimeError("Failed to provision Python execution job")

        run_service = JobRunDataService(project_uuid)
        job_run = await run_service.create_run_async(
            job_id=job_entity.id,
            parameters=json.dumps(params.model_dump(mode="json", by_alias=True)),
            status="Queued",
            triggered_by=triggered_by,
            trigger_type=JobTriggerType.INTERACTIVE,
            run_id=run_id,
        )
        if job_run.id is None:
            raise RuntimeError("Failed to create Python execution run")

        # The run is executed by the worker (supervisor), which owns the session
        # kernels. This process only enqueues and waits, exactly like query
        # execution, so the API never runs job code.
        poll_result = await poll_job_run_completion(
            project_id=project_uuid,
            job_run_id=str(job_run.id),
            timeout_seconds=float((params.timeout_seconds or 300) + 60),
        )
        if poll_result is None:
            logger.warning("Python execution run %s did not complete in time", job_run.id)

        refreshed = await run_service.get_run_by_id_async(
            UUID(str(job_run.id)),
            include_job=True,
            include_trigger=False,
        )
        if refreshed is None:
            raise RuntimeError("Notebook Python execution run disappeared")

        return _python_service_result_from_job_run(refreshed)


def _python_service_result_from_job_run(
    job_run: JobRunModel,
) -> PythonExecutionServiceResult:
    return PythonExecutionServiceResult(
        execution_run=project_execution_run(job_run),
        python_result=_python_result_from_job_run(job_run),
        code=_python_code_from_job_run(job_run),
        infra_failure=_job_run_infra_failure(job_run),
    )


def _job_run_infra_failure(job_run: JobRunModel) -> bool:
    """Whether the run failed in the execution infrastructure, not user code.

    Infrastructure failures are the job framework's generic exception payload
    (``{"data": {"exception_type": ...}}`` — e.g. the kernel process died at
    startup) or a run with no Python-composed result at all. Ordinary
    execution failures carry the job's own ``python_execution`` payload and
    count differently for retry policies.
    """
    payload: dict | None = None
    if job_run.result_data:
        try:
            parsed = json.loads(job_run.result_data)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = None

    if payload and isinstance(payload.get("data"), dict):
        candidate = payload["data"]
        if candidate.keys() <= {"exception_type"}:
            return True
        if "success" in candidate:
            return False  # a composed execution outcome, failed or not

    status = str(getattr(job_run, "status", "") or "")
    return status.upper() not in {"SUCCEEDED", "SUCCESS"}


def _python_code_from_job_run(job_run: JobRunModel) -> str | None:
    if not job_run.parameters:
        return None

    try:
        parsed = json.loads(job_run.parameters)
    except json.JSONDecodeError:
        logger.exception("Failed to parse Python execution parameters for run %s", job_run.id)
        return None

    if not isinstance(parsed, dict):
        return None

    code = parsed.get("code")
    return code if isinstance(code, str) and code.strip() else None


def _job_type_from_job_run(job_run: JobRunModel) -> str:
    job = getattr(job_run, "job", None)
    if job is None:
        return ""

    job_type = getattr(job, "type", None)
    return job_type if isinstance(job_type, str) else ""


def _failed_python_result_from_job_run(
    job_run: JobRunModel, error_message: str
) -> PythonExecutionResult:
    return PythonExecutionResult(
        success=False,
        message=error_message,
        error=error_message,
        target_type=(
            PythonExecutionTargetType.SESSION
            if _job_type_from_job_run(job_run) == "python.jobs.ExecutePythonScriptJob"
            else PythonExecutionTargetType.NOTEBOOK
        ),
        outputs=[
            CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content=error_message))
        ],
    )


def _python_result_from_job_run(job_run: JobRunModel) -> PythonExecutionResult:
    """Derive the Python envelope from a completed execution run.

    ``execution_run_id`` is stamped from the job run itself — the single
    source of truth for the id callers use downstream (notebook
    ``import_executed_python`` / ``persist_python_execution_state`` work).
    Without a run id in the envelope, session-scope callers only have the
    chat/session id available, which can never resolve to a run.
    """
    result = _python_result_from_payload(job_run)
    result.execution_run_id = str(job_run.id)
    return result


def _python_result_from_payload(job_run: JobRunModel) -> PythonExecutionResult:
    payload: dict | None = None
    if job_run.result_data:
        try:
            parsed = json.loads(job_run.result_data)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            payload = None

    candidate = payload.get("data") if payload else None
    if isinstance(candidate, dict):
        if candidate.keys() <= {"exception_type"}:
            # The job framework's generic infrastructure-exception payload
            # (e.g. the kernel process died at startup). Surface the failure
            # message itself instead of a validation error wall.
            error_message = job_run.error_message or "Python execution failed."
            return _failed_python_result_from_job_run(job_run, error_message)
        try:
            return PythonExecutionResult.model_validate(candidate)
        except Exception:
            logger.exception("Failed to parse notebook Python execution payload")

    error_message = job_run.error_message or "Python execution failed."
    return _failed_python_result_from_job_run(job_run, error_message)
