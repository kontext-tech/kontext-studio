"""Shared chat-session Python execution coordination.

Agent-facing session executions run through
:func:`execute_chat_session_python_script`, which also owns the
consecutive-infrastructure-failure breaker: the agent is told to stop
retrying after the cap instead of holding the run in an endless loop.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import UUID, uuid4

from kontext.common.constants import max_consecutive_kernel_failures
from kontext.common.protocols import IChatSessionProtocol
from kontext.data import ChatSessionDataService
from kontext.execution import PythonExecutionService, PythonExecutionServiceResult
from kontext.schema import (
    ArtifactType,
    ChatSessionArtifactModel,
    ChatSessionModel,
    CodeExecutionOutput,
    CodeTextOutput,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    PythonExecutionResult,
    PythonExecutionTargetType,
    TriggerActorModel,
)

# Module-level breaker state: within one API process (the local and single
# cloud API deployments), consecutive infra failures per chat session are
# tracked here. A cap reached this way does not need to survive restarts:
# (consecutive infra failures, last infrastructure error). Entries are only
# ever replaced or removed, never deleted per-session, so the map is trimmed
# at _BREAKER_KEY_CAP on inserts to stay bounded for long-lived processes.
# Note the cap check (read) and outcome record (write) are separate steps: on
# the exact turn that trips the cap, one in-flight dispatch may already have
# been admitted - the NEXT call always fails fast.
_infra_failure_streaks: dict[str, tuple[int, str | None]] = {}
_streak_lock = threading.Lock()
_BREAKER_KEY_CAP = 4096


def _breaker_key(project_id: UUID | str, chat_session_id: UUID | str) -> str:
    return f"{project_id}:{chat_session_id}"


def _record_breaker_outcome(breaker_key: str, *, infra_failure: bool, error: str | None) -> None:
    with _streak_lock:
        if infra_failure:
            if (
                breaker_key not in _infra_failure_streaks
                and len(_infra_failure_streaks) >= _BREAKER_KEY_CAP
            ):
                # Evict the oldest entry (insertion order) to stay bounded.
                oldest = next(iter(_infra_failure_streaks), None)
                if oldest is not None:
                    _infra_failure_streaks.pop(oldest, None)
            streak, _ = _infra_failure_streaks.get(breaker_key, (0, None))
            _infra_failure_streaks[breaker_key] = (streak + 1, error)
        else:
            # Successes and ordinary user-code execution failures both mean
            # the infrastructure works again.
            _infra_failure_streaks.pop(breaker_key, None)


def _breaker_streak(breaker_key: str) -> tuple[int, str | None]:
    with _streak_lock:
        return _infra_failure_streaks.get(breaker_key, (0, None))


def breaker_stop_message(*, streak: int, last_error: str | None) -> str:
    """Agent-facing instruction when the infra-failure breaker has tripped."""
    attempt_word = "attempt" if streak == 1 else "attempts"
    detail = f" (last error: {last_error})" if last_error else ""
    return (
        f"Python execution infrastructure failed {streak} consecutive "
        f"{attempt_word}{detail}. Do not retry the execution; report the "
        f"infrastructure failure to the user instead."
    )


def _breaker_stop_result(
    *, streak: int, last_error: str | None, target_type: PythonExecutionTargetType
) -> PythonExecutionServiceResult:
    message = breaker_stop_message(streak=streak, last_error=last_error)
    execution_run = ExecutionRunModel(
        id=str(uuid4()),
        kind=ExecutionRunKind.AGENT,
        status=ExecutionRunStatus.FAILED,
        name="ExecutePythonScriptJob",
        created_at=datetime.now(UTC),
        error_message=message,
    )
    return PythonExecutionServiceResult(
        execution_run=execution_run,
        python_result=PythonExecutionResult(
            success=False,
            message=message,
            error=last_error,
            target_type=target_type,
            outputs=[CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content=message))],
        ),
        infra_failure=True,
    )


def _as_uuid(value: UUID | str) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


async def _get_chat_session(
    *,
    chat_session_id: UUID,
    chat_session_service: IChatSessionProtocol | None = None,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> ChatSessionModel | None:
    if chat_session_data_service is not None:
        return await chat_session_data_service.get_session_by_id_async(chat_session_id)
    if chat_session_service is not None:
        return await chat_session_service.get_session(str(chat_session_id))
    raise ValueError("Chat session service is not available for session-scoped Python execution.")


async def _get_chat_session_artifacts(
    *,
    chat_session_id: UUID,
    chat_session_service: IChatSessionProtocol | None = None,
    chat_session_data_service: ChatSessionDataService | None = None,
) -> list[ChatSessionArtifactModel]:
    if chat_session_data_service is not None:
        return await chat_session_data_service.get_session_artifacts_async(chat_session_id)
    if chat_session_service is not None:
        return await chat_session_service.list_artifacts(str(chat_session_id))
    raise ValueError("Chat session service is not available for session-scoped Python execution.")


def _build_session_data_sources(
    artifacts: list[ChatSessionArtifactModel],
) -> dict[str, str]:
    return {
        str(artifact.artifact_id): str(artifact.artifact_id)
        for artifact in artifacts
        if artifact.artifact_type == ArtifactType.DATATABLE and artifact.artifact_id
    }


async def execute_chat_session_python_script(
    *,
    project_id: UUID | str,
    chat_session_id: UUID | str,
    code: str,
    owner_id: UUID | str | None = None,
    triggered_by: TriggerActorModel | None = None,
    chat_session_service: IChatSessionProtocol | None = None,
    chat_session_data_service: ChatSessionDataService | None = None,
    python_execution_service: PythonExecutionService | None = None,
) -> PythonExecutionServiceResult:
    """Execute session-scoped Python using chat-session state as the source of truth."""
    if not str(code).strip():
        raise ValueError("Python code cannot be empty.")

    session_uuid = _as_uuid(chat_session_id)
    chat_session = await _get_chat_session(
        chat_session_id=session_uuid,
        chat_session_service=chat_session_service,
        chat_session_data_service=chat_session_data_service,
    )
    if chat_session is None:
        raise ValueError(f"Chat session {chat_session_id} was not found.")

    artifacts = await _get_chat_session_artifacts(
        chat_session_id=session_uuid,
        chat_session_service=chat_session_service,
        chat_session_data_service=chat_session_data_service,
    )
    execution_service = python_execution_service or PythonExecutionService()

    breaker_key = _breaker_key(project_id, session_uuid)
    streak_cap = max_consecutive_kernel_failures()
    current_streak, last_error = _breaker_streak(breaker_key)
    if current_streak >= streak_cap:
        # The execution infrastructure has failed back-to-back too many times;
        # fail fast with the agent-facing stop message instead of dispatching
        # yet another doomed job run.
        return _breaker_stop_result(
            streak=current_streak,
            last_error=last_error,
            target_type=PythonExecutionTargetType.SESSION,
        )

    execution_result = await execution_service.execute_script_async(
        project_id=project_id,
        code=code,
        data_sources=_build_session_data_sources(artifacts),
        chat_session_id=str(session_uuid),
        query_session_id=(
            str(chat_session.query_session_id)
            if chat_session.query_session_id is not None
            else None
        ),
        catalog_connection_id=(
            str(chat_session.default_catalog_connection_id)
            if chat_session.default_catalog_connection_id is not None
            else None
        ),
        default_namespace=chat_session.default_namespace,
        default_entity_id=(
            str(chat_session.default_entity_id)
            if chat_session.default_entity_id is not None
            else None
        ),
        engine_type=chat_session.engine_type,
        owner_id=owner_id or chat_session.owner_id,
        triggered_by=triggered_by,
    )
    execution_result.python_result.target_type = PythonExecutionTargetType.SESSION
    _record_breaker_outcome(
        breaker_key,
        infra_failure=execution_result.infra_failure,
        error=(execution_result.python_result.message if execution_result.infra_failure else None),
    )
    return execution_result
