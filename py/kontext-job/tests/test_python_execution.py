from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from kontext.common.jobs.trigger_actor import chat_session_actor, notebook_actor
from kontext.jobs.python_execution import (
    PythonExecutionService,
    PythonExecutionTargetType,
    _job_run_infra_failure,
    _python_result_from_job_run,
    _python_service_result_from_job_run,
)
from kontext.schema import (
    JobRunModel,
    JobRunStatus,
    JobTriggerType,
)


@pytest.mark.asyncio
async def test_python_execution_service_uses_owner_scoped_job_and_projects_owner(
    monkeypatch,
) -> None:
    project_id = uuid4()
    owner_id = uuid4()

    poll = AsyncMock(return_value=SimpleNamespace(status=JobRunStatus.SUCCEEDED))
    monkeypatch.setattr(
        "kontext.jobs.python_execution.poll_job_run_completion",
        poll,
    )

    get_or_create = AsyncMock(return_value=MagicMock(id=uuid4(), owner_id=str(owner_id)))
    create_run = AsyncMock(return_value=MagicMock(id=uuid4()))
    refreshed_run = JobRunModel.model_construct(
        id=str(uuid4()),
        job_id=str(uuid4()),
        job_trigger_id=str(uuid4()),
        project_id=str(project_id),
        project_name="Project",
        owner_id=str(owner_id),
        status=JobRunStatus.SUCCEEDED,
        progress=100,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        parameters='{"code": "print(\\"ok\\")"}',
        execution_id="exec-1",
        worker="worker",
        attempt_count=0,
        result_type="json",
        result_data='{"data": {"success": true, "message": "ok", "outputs": []}}',
        error_message=None,
        error_stack=None,
        created_at=datetime.now(UTC),
        job=SimpleNamespace(
            name="Execute Notebook Python",
            type="python.jobs.ExecuteNotebookPythonJob",
        ),
        job_trigger=SimpleNamespace(trigger_type=JobTriggerType.INTERACTIVE),
    )
    get_run = AsyncMock(return_value=refreshed_run)

    monkeypatch.setattr(
        "kontext.jobs.python_execution.JobDataService",
        lambda _project_id: MagicMock(get_or_create_job_for_owner_async=get_or_create),
    )
    monkeypatch.setattr(
        "kontext.jobs.python_execution.JobRunDataService",
        lambda _project_id: MagicMock(
            create_run_async=create_run,
            get_run_by_id_async=get_run,
        ),
    )

    service = PythonExecutionService()
    result = await service.execute_notebook_code_async(
        project_id=project_id,
        notebook_id=str(uuid4()),
        block_id=str(uuid4()),
        code="print('ok')",
        data_sources={},
        owner_id=owner_id,
        triggered_by=notebook_actor("test"),
    )

    assert result.execution_run.owner_id == str(owner_id)
    assert result.code == 'print("ok")'
    get_or_create.assert_awaited_once()
    await_args = get_or_create.await_args
    assert await_args is not None
    assert await_args.kwargs["owner_id"] == owner_id
    # The run is enqueued for the worker and awaited, not executed inline.
    poll.assert_awaited_once()


@pytest.mark.asyncio
async def test_python_execution_service_forwards_client_run_id(monkeypatch) -> None:
    """A client-supplied run id must be used, enabling deterministic cancel."""
    project_id = uuid4()
    owner_id = uuid4()
    client_run_id = uuid4()

    monkeypatch.setattr(
        "kontext.jobs.python_execution.poll_job_run_completion",
        AsyncMock(return_value=SimpleNamespace(status=JobRunStatus.SUCCEEDED)),
    )

    get_or_create = AsyncMock(return_value=MagicMock(id=uuid4(), owner_id=str(owner_id)))
    create_run = AsyncMock(return_value=MagicMock(id=client_run_id))
    refreshed_run = JobRunModel.model_construct(
        id=str(client_run_id),
        job_id=str(uuid4()),
        job_trigger_id=str(uuid4()),
        project_id=str(project_id),
        project_name="Project",
        owner_id=str(owner_id),
        status=JobRunStatus.SUCCEEDED,
        progress=100,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        parameters='{"code": "print(\\"ok\\")"}',
        execution_id="exec-1",
        worker="worker",
        attempt_count=0,
        result_type="json",
        result_data='{"data": {"success": true, "message": "ok", "outputs": []}}',
        error_message=None,
        error_stack=None,
        created_at=datetime.now(UTC),
        job=SimpleNamespace(
            name="Execute Notebook Python",
            type="python.jobs.ExecuteNotebookPythonJob",
        ),
        job_trigger=SimpleNamespace(trigger_type=JobTriggerType.INTERACTIVE),
    )
    get_run = AsyncMock(return_value=refreshed_run)

    monkeypatch.setattr(
        "kontext.jobs.python_execution.JobDataService",
        lambda _project_id: MagicMock(get_or_create_job_for_owner_async=get_or_create),
    )
    monkeypatch.setattr(
        "kontext.jobs.python_execution.JobRunDataService",
        lambda _project_id: MagicMock(
            create_run_async=create_run,
            get_run_by_id_async=get_run,
        ),
    )

    service = PythonExecutionService()
    await service.execute_notebook_code_async(
        project_id=project_id,
        notebook_id=str(uuid4()),
        block_id=str(uuid4()),
        code="print('ok')",
        data_sources={},
        owner_id=owner_id,
        triggered_by=notebook_actor("test"),
        run_id=client_run_id,
    )

    create_run.assert_awaited_once()
    assert create_run.await_args is not None
    assert create_run.await_args.kwargs["run_id"] == client_run_id


@pytest.mark.asyncio
async def test_python_execution_service_executes_session_scoped_script_job(
    monkeypatch,
) -> None:
    project_id = uuid4()
    owner_id = uuid4()

    monkeypatch.setattr(
        "kontext.jobs.python_execution.poll_job_run_completion",
        AsyncMock(return_value=SimpleNamespace(status=JobRunStatus.SUCCEEDED)),
    )

    get_or_create = AsyncMock(return_value=MagicMock(id=uuid4(), owner_id=str(owner_id)))
    create_run = AsyncMock(return_value=MagicMock(id=uuid4()))
    refreshed_run = JobRunModel.model_construct(
        id=str(uuid4()),
        job_id=str(uuid4()),
        job_trigger_id=str(uuid4()),
        project_id=str(project_id),
        project_name="Project",
        owner_id=str(owner_id),
        status=JobRunStatus.SUCCEEDED,
        progress=100,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        parameters='{"code": "print(\\"ok\\")"}',
        execution_id="exec-2",
        worker="worker",
        attempt_count=0,
        result_type="json",
        result_data=(
            '{"data": {"success": true, "message": "ok", "targetType": "session", "outputs": []}}'
        ),
        error_message=None,
        error_stack=None,
        created_at=datetime.now(UTC),
        job=SimpleNamespace(
            name="Execute Python Script",
            type="python.jobs.ExecutePythonScriptJob",
        ),
        job_trigger=SimpleNamespace(trigger_type=JobTriggerType.INTERACTIVE),
    )
    get_run = AsyncMock(return_value=refreshed_run)

    monkeypatch.setattr(
        "kontext.jobs.python_execution.JobDataService",
        lambda _project_id: MagicMock(get_or_create_job_for_owner_async=get_or_create),
    )
    monkeypatch.setattr(
        "kontext.jobs.python_execution.JobRunDataService",
        lambda _project_id: MagicMock(
            create_run_async=create_run,
            get_run_by_id_async=get_run,
        ),
    )

    service = PythonExecutionService()
    result = await service.execute_script_async(
        project_id=project_id,
        code="print('ok')",
        data_sources={},
        query_session_id=str(uuid4()),
        catalog_connection_id=str(uuid4()),
        default_namespace="analytics",
        default_entity_id=str(uuid4()),
        engine_type="DuckDB",
        owner_id=owner_id,
        triggered_by=chat_session_actor("test"),
    )

    assert result.execution_run.owner_id == str(owner_id)
    assert result.code == 'print("ok")'
    assert result.python_result.target_type == "session"
    get_or_create.assert_awaited_once()
    await_args = get_or_create.await_args
    assert await_args is not None
    assert await_args.kwargs["job_type"] == "python.jobs.ExecutePythonScriptJob"
    create_run_args = create_run.await_args
    assert create_run_args is not None
    parameters = json.loads(create_run_args.kwargs["parameters"])
    assert parameters["defaultNamespace"] == "analytics"
    assert parameters["engineType"] == "DuckDB"
    assert "querySessionId" in parameters


@pytest.mark.asyncio
async def test_python_execution_service_get_result_resolves_code_and_target_type(
    monkeypatch,
) -> None:
    project_id = uuid4()
    run_id = uuid4()
    refreshed_run = JobRunModel.model_construct(
        id=str(run_id),
        job_id=str(uuid4()),
        job_trigger_id=str(uuid4()),
        project_id=str(project_id),
        project_name="Project",
        owner_id=str(uuid4()),
        status=JobRunStatus.FAILED,
        progress=100,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        parameters='{"code": "print(\\"stored\\")"}',
        execution_id="exec-3",
        worker="worker",
        attempt_count=1,
        result_type="json",
        result_data=None,
        error_message="boom",
        error_stack=None,
        created_at=datetime.now(UTC),
        job=SimpleNamespace(
            name="Execute Python Script",
            type="python.jobs.ExecutePythonScriptJob",
        ),
        job_trigger=SimpleNamespace(trigger_type=JobTriggerType.INTERACTIVE),
    )
    get_run = AsyncMock(return_value=refreshed_run)

    monkeypatch.setattr(
        "kontext.jobs.python_execution.JobRunDataService",
        lambda _project_id: MagicMock(get_run_by_id_async=get_run),
    )

    service = PythonExecutionService()
    result = await service.get_execution_result_async(
        project_id=project_id,
        run_id=run_id,
    )

    assert result.code == 'print("stored")'
    assert result.python_result.target_type == "session"
    assert result.python_result.error == "boom"


def _job_run(
    *,
    status: str,
    result_data: str | None,
    error_message: str | None,
    job_type: str = "python.jobs.ExecutePythonScriptJob",
) -> JobRunModel:
    return JobRunModel.model_construct(
        id=str(uuid4()),
        project_id=str(uuid4()),
        status=status,
        result_data=result_data,
        error_message=error_message,
        job=SimpleNamespace(type=job_type, name="Execute Python"),
        created_at=datetime.now(UTC),
    )


class TestJobRunInfraFailureClassification:
    def test_generic_exception_payload_is_infra_failure(self) -> None:
        job_run = _job_run(
            status="Failed",
            result_data=(
                '{"success": false, "message": "Kernel process exited early with code 1", '
                '"data": {"exception_type": "RuntimeError"}, "error_code": "RuntimeError", '
                '"result_type": "PythonJobResult"}'
            ),
            error_message="Kernel process exited early with code 1",
        )

        assert _job_run_infra_failure(job_run) is True

        python_result = _python_result_from_job_run(job_run)
        assert python_result.success is False
        assert python_result.message == "Kernel process exited early with code 1"
        assert python_result.target_type == PythonExecutionTargetType.SESSION

    def test_execution_failure_payload_is_not_infra_failure(self) -> None:
        job_run = _job_run(
            status="Succeeded",
            result_data=(
                '{"success": true, "message": "ok", "data": {"type": "python_execution", '
                '"success": false, "message": "user error", "targetType": "session", '
                '"outputs": []}, "result_type": "PythonJobResult"}'
            ),
            error_message=None,
        )

        assert _job_run_infra_failure(job_run) is False

        python_result = _python_result_from_job_run(job_run)
        assert python_result.success is False
        assert python_result.message == "user error"

    def test_missing_result_on_failed_run_is_infra_failure(self) -> None:
        job_run = _job_run(
            status="Failed",
            result_data=None,
            error_message="Python execution run did not complete in time",
        )

        assert _job_run_infra_failure(job_run) is True
        python_result = _python_result_from_job_run(job_run)
        assert python_result.success is False
        assert "did not complete in time" in python_result.message

    def test_service_result_carries_infra_flag(self) -> None:
        job_run = _job_run(
            status="Failed",
            result_data='{"success": false, "data": {"exception_type": "RuntimeError"}}',
            error_message="Kernel process exited early with code 1",
        )

        service_result = _python_service_result_from_job_run(job_run)
        assert service_result.infra_failure is True
        assert service_result.python_result.success is False


class TestExecutionRunIdStamping:
    """The envelope must expose the real execution-run id for downstream reuse."""

    def test_success_payload_carries_job_run_id(self) -> None:
        job_run = _job_run(
            status="Succeeded",
            result_data=(
                '{"success": true, "message": "ok", "data": {"type": "python_execution", '
                '"success": true, "message": "ok", "targetType": "session", "outputs": []}, '
                '"result_type": "PythonJobResult"}'
            ),
            error_message=None,
        )

        python_result = _python_result_from_job_run(job_run)
        assert python_result.execution_run_id == str(job_run.id)

    def test_infra_failure_payload_still_carries_job_run_id(self) -> None:
        job_run = _job_run(
            status="Failed",
            result_data='{"success": false, "data": {"exception_type": "RuntimeError"}}',
            error_message="Kernel process exited early with code 1",
        )

        python_result = _python_result_from_job_run(job_run)
        assert python_result.execution_run_id == str(job_run.id)
