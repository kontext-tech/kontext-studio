from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from kontext.chat.python_execution import (
    _infra_failure_streaks,
    breaker_stop_message,
    execute_chat_session_python_script,
)
from kontext.common.jobs.trigger_actor import chat_session_actor
from kontext.jobs import PythonExecutionServiceResult
from kontext.schema import (
    ArtifactType,
    ChatSessionArtifactModel,
    ChatSessionModel,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    PythonExecutionApprovalMode,
    PythonExecutionResult,
    PythonExecutionTargetType,
)


def _chat_session(*, session_id: str, project_id: str) -> ChatSessionModel:
    return ChatSessionModel.model_construct(
        id=session_id,
        project_id=project_id,
        session_name="Session",
        owner_id=str(uuid4()),
        date_created=datetime.now(UTC),
        query_session_id=str(uuid4()),
        default_catalog_connection_id=str(uuid4()),
        default_namespace="analytics",
        default_entity_id=str(uuid4()),
        engine_type="DuckDB",
        python_execution_approval_mode=PythonExecutionApprovalMode.ALWAYSASK,
        is_deleted=False,
    )


def _artifact(
    *,
    session_id: str,
    artifact_id: str,
    artifact_type: ArtifactType,
) -> ChatSessionArtifactModel:
    now = datetime.now(UTC)
    return ChatSessionArtifactModel.model_construct(
        id=str(uuid4()),
        session_id=session_id,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        title="Artifact",
        created_at=now,
        updated_at=now,
    )


def _python_execution_result() -> PythonExecutionServiceResult:
    return PythonExecutionServiceResult(
        execution_run=ExecutionRunModel.model_construct(
            id="run-chat-1",
            kind=ExecutionRunKind.AGENT,
            status=ExecutionRunStatus.SUCCEEDED,
            created_at=datetime.now(UTC),
        ),
        python_result=PythonExecutionResult(
            success=True,
            message="ok",
            execution_run_id="run-chat-1",
            target_type=PythonExecutionTargetType.SESSION,
            outputs=[],
        ),
        code="print('ok')",
        infra_failure=False,
    )


def _infra_failure_execution_result(*, message: str) -> PythonExecutionServiceResult:
    return PythonExecutionServiceResult(
        execution_run=ExecutionRunModel.model_construct(
            id="run-infra-1",
            kind=ExecutionRunKind.AGENT,
            status=ExecutionRunStatus.FAILED,
            created_at=datetime.now(UTC),
            error_message=message,
        ),
        python_result=PythonExecutionResult(
            success=False,
            message=message,
            error=message,
            target_type=PythonExecutionTargetType.SESSION,
            outputs=[],
        ),
        infra_failure=True,
    )


@pytest.mark.asyncio
async def test_execute_chat_session_python_script_uses_runtime_chat_session_artifacts() -> None:
    project_id = str(uuid4())
    session_id = str(uuid4())
    data_id_one = str(uuid4())
    data_id_two = str(uuid4())

    chat_session_service = MagicMock()
    chat_session_service.get_session = AsyncMock(
        return_value=_chat_session(session_id=session_id, project_id=project_id)
    )
    chat_session_service.list_artifacts = AsyncMock(
        return_value=[
            _artifact(
                session_id=session_id,
                artifact_id=data_id_one,
                artifact_type=ArtifactType.DATATABLE,
            ),
            _artifact(
                session_id=session_id,
                artifact_id=str(uuid4()),
                artifact_type=ArtifactType.CHART,
            ),
            _artifact(
                session_id=session_id,
                artifact_id=data_id_two,
                artifact_type=ArtifactType.DATATABLE,
            ),
        ]
    )
    python_execution_service = MagicMock()
    python_execution_service.execute_script_async = AsyncMock(
        return_value=_python_execution_result()
    )

    result = await execute_chat_session_python_script(
        project_id=project_id,
        chat_session_id=session_id,
        code="print('ok')",
        chat_session_service=chat_session_service,
        python_execution_service=python_execution_service,
        triggered_by=chat_session_actor(str(session_id)),
    )

    execute_kwargs = python_execution_service.execute_script_async.await_args.kwargs
    assert execute_kwargs["project_id"] == project_id
    assert execute_kwargs["code"] == "print('ok')"
    assert execute_kwargs["data_sources"] == {
        data_id_one: data_id_one,
        data_id_two: data_id_two,
    }
    assert execute_kwargs["chat_session_id"] == session_id
    assert execute_kwargs["default_namespace"] == "analytics"
    assert execute_kwargs["engine_type"] == "DuckDB"
    assert result.python_result.target_type == PythonExecutionTargetType.SESSION


@pytest.mark.asyncio
async def test_execute_chat_session_python_script_uses_data_service_for_api_path() -> None:
    project_id = str(uuid4())
    session_id = str(uuid4())
    data_id = str(uuid4())

    chat_session_data_service = MagicMock()
    chat_session_data_service.get_session_by_id_async = AsyncMock(
        return_value=_chat_session(session_id=session_id, project_id=project_id)
    )
    chat_session_data_service.get_session_artifacts_async = AsyncMock(
        return_value=[
            _artifact(
                session_id=session_id,
                artifact_id=data_id,
                artifact_type=ArtifactType.DATATABLE,
            )
        ]
    )
    python_execution_service = MagicMock()
    python_execution_service.execute_script_async = AsyncMock(
        return_value=_python_execution_result()
    )

    await execute_chat_session_python_script(
        project_id=project_id,
        chat_session_id=session_id,
        code="print('ok')",
        owner_id=str(uuid4()),
        chat_session_data_service=chat_session_data_service,
        python_execution_service=python_execution_service,
    )

    execute_kwargs = python_execution_service.execute_script_async.await_args.kwargs
    assert execute_kwargs["data_sources"] == {data_id: data_id}
    assert execute_kwargs["chat_session_id"] == session_id


@pytest.fixture(autouse=True)
def _clear_breaker_state():
    _infra_failure_streaks.clear()
    yield
    _infra_failure_streaks.clear()


def _fake_execution_service(
    outcome_factory,
) -> tuple[MagicMock, AsyncMock]:
    service = MagicMock()
    execute = AsyncMock(side_effect=outcome_factory)
    service.execute_script_async = execute
    return service, execute


def _session_service(project_id: str, session_id: str) -> MagicMock:
    service = MagicMock()
    service.get_session = AsyncMock(
        return_value=_chat_session(session_id=session_id, project_id=project_id)
    )
    service.list_artifacts = AsyncMock(return_value=[])
    return service


@pytest.mark.asyncio
async def test_infra_failures_trip_the_breaker_and_stop_dispatching_jobs() -> None:
    project_id = str(uuid4())
    session_id = str(uuid4())
    infra_message = "Kernel process exited early with code 1"

    def outcome(**_kwargs):
        return _infra_failure_execution_result(message=infra_message)

    service, execute = _fake_execution_service(outcome)
    session_service = _session_service(project_id, session_id)

    for _ in range(3):
        result = await execute_chat_session_python_script(
            project_id=project_id,
            chat_session_id=session_id,
            code="print('boom')",
            chat_session_service=session_service,
            python_execution_service=service,
        )
        assert result.infra_failure is True

    assert execute.await_count == 3

    tripped = await execute_chat_session_python_script(
        project_id=project_id,
        chat_session_id=session_id,
        code="print('boom')",
        chat_session_service=session_service,
        python_execution_service=service,
    )

    # No further job dispatched once the breaker is open.
    assert execute.await_count == 3
    assert tripped.python_result.success is False
    message = tripped.python_result.message
    assert "3 consecutive attempts" in message
    assert "Do not retry" in message
    assert infra_message in message


@pytest.mark.asyncio
async def test_success_or_user_error_reopens_the_breaker() -> None:
    project_id = str(uuid4())
    session_id = str(uuid4())
    outcomes = [
        _infra_failure_execution_result(message="Kernel process exited early with code 1"),
        _infra_failure_execution_result(message="Kernel process exited early with code 1"),
        _python_execution_result(),  # infrastructure healthy again
        _infra_failure_execution_result(message="Kernel process exited early with code 1"),
        _infra_failure_execution_result(message="Kernel process exited early with code 1"),
    ]
    service, execute = _fake_execution_service(lambda **_kwargs: outcomes.pop(0))
    session_service = _session_service(project_id, session_id)

    for _ in range(5):
        await execute_chat_session_python_script(
            project_id=project_id,
            chat_session_id=session_id,
            code="print('x')",
            chat_session_service=session_service,
            python_execution_service=service,
        )

    # The success in the middle reset the streak, so no breaker trip happened.
    assert execute.await_count == 5
    assert _infra_failure_streaks.get(f"{project_id}:{session_id}") == (
        2,
        "Kernel process exited early with code 1",
    )


@pytest.mark.asyncio
async def test_user_code_errors_do_not_count_toward_the_breaker(monkeypatch) -> None:
    project_id = str(uuid4())
    session_id = str(uuid4())
    monkeypatch.setenv("KONTEXT_PYTHON_MAX_CONSECUTIVE_KERNEL_FAILURES", "2")

    user_error = PythonExecutionServiceResult(
        execution_run=ExecutionRunModel.model_construct(
            id="run-user-1",
            kind=ExecutionRunKind.AGENT,
            status=ExecutionRunStatus.SUCCEEDED,
            created_at=datetime.now(UTC),
        ),
        python_result=PythonExecutionResult(
            success=False,
            message="NameError: name 'x' is not defined",
            error="NameError: name 'x' is not defined",
            target_type=PythonExecutionTargetType.SESSION,
            outputs=[],
        ),
        infra_failure=False,
    )
    outcomes = [
        _infra_failure_execution_result(message="Kernel died"),
        user_error,
        _infra_failure_execution_result(message="Kernel died"),
        user_error,
    ]
    service, execute = _fake_execution_service(lambda **_kwargs: outcomes.pop(0))
    session_service = _session_service(project_id, session_id)

    for _ in range(4):
        await execute_chat_session_python_script(
            project_id=project_id,
            chat_session_id=session_id,
            code="print('x')",
            chat_session_service=session_service,
            python_execution_service=service,
        )

    # Ordinary user-code failures reset the streak, so the breaker never
    # tripped and every call dispatched a job.
    assert execute.await_count == 4


@pytest.mark.asyncio
async def test_breaker_cap_is_env_configurable(monkeypatch) -> None:
    project_id = str(uuid4())
    session_id = str(uuid4())
    monkeypatch.setenv("KONTEXT_PYTHON_MAX_CONSECUTIVE_KERNEL_FAILURES", "1")

    service, execute = _fake_execution_service(
        lambda **_kwargs: _infra_failure_execution_result(message="Kernel died")
    )
    session_service = _session_service(project_id, session_id)

    first = await execute_chat_session_python_script(
        project_id=project_id,
        chat_session_id=session_id,
        code="print('x')",
        chat_session_service=session_service,
        python_execution_service=service,
    )
    assert first.infra_failure is True
    assert execute.await_count == 1

    second = await execute_chat_session_python_script(
        project_id=project_id,
        chat_session_id=session_id,
        code="print('x')",
        chat_session_service=session_service,
        python_execution_service=service,
    )
    assert execute.await_count == 1
    assert "Do not retry" in second.python_result.message


def test_breaker_stop_message_wording() -> None:
    message = breaker_stop_message(streak=3, last_error="Kernel died")
    assert "3 consecutive attempts" in message
    assert "Kernel died" in message
