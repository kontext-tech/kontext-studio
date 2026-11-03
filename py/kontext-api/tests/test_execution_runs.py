import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from kontext.api.dependencies import AuthContext
from kontext.api.dependencies.jobs import get_queue_client
from kontext.api.main import app
from kontext.api.routers.query import QUERY_EXECUTE_AUTH
from kontext.api.routers.query_sessions import SESSION_EXECUTE_AUTH
from kontext.api.routers.runs import RUN_READ_AUTH, RUN_WRITE_AUTH
from kontext.api.services.execution_runs import ResolvedExecutionRunInput
from kontext.common.jobs.trigger_actor import user_actor
from kontext.execution.lifecycle import ExecutionLifecycleService
from kontext.execution.runs import (
    infer_execution_run_kind,
    map_job_run_status,
    project_execution_run,
)
from kontext.schema import (
    AccessLevel,
    EventData,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    JobModel,
    JobRetryStrategy,
    JobRunModel,
    JobRunStatus,
    PaginatedListOfExecutionRunModel,
    ProjectConfiguration,
    ProjectModel,
    RunEvent,
    RunPausedEventData,
    SimpleRunEvent,
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_for_execution_run_tests")
    return TestClient(app)


def _mock_project(project_id: str) -> ProjectModel:
    return ProjectModel(
        access_level=AccessLevel.PRIVATE,
        date_created=datetime.now(UTC),
        id=project_id,
        project_name="Test Project",
        project_code="TEST",
        owner_id=str(uuid.uuid4()),
        is_deleted=False,
        configuration=ProjectConfiguration(
            allowed_file_types=[],
            max_file_bytes_size=0,
            total_storage_allocation_bytes=0,
            features=[],
        ),
    )


def _mock_job(*, project_id: str, name: str, job_type: str) -> JobModel:
    return JobModel(
        id=str(uuid.uuid4()),
        name=name,
        type=job_type,
        description=None,
        schedule=None,
        parameters=None,
        timeout=300,
        is_enabled=True,
        retry_strategy=JobRetryStrategy.NONE,
        retry_limit=0,
        project_id=project_id,
        project_name="Test Project",
        owner_id=str(uuid.uuid4()),
        date_created=datetime.now(UTC),
        date_modified=None,
        last_run_status=None,
        last_run_date=None,
        next_run_date=None,
        total_runs=0,
        successful_runs=0,
        failed_runs=0,
        in_progress_runs=0,
        total_run_duration_seconds=None,
    )


def test_execution_run_projection_maps_query_job():
    run = JobRunModel(
        id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        owner_id=str(uuid.uuid4()),
        status=JobRunStatus.DISPATCHED,
        attempt_count=0,
        created_at=datetime.now(UTC),
        job=_mock_job(
            project_id=str(uuid.uuid4()),
            name="Execute Query",
            job_type="python.jobs.ExecuteQueryJob",
        ),
    )

    projected = project_execution_run(run)

    assert infer_execution_run_kind(run).value == "query"
    assert map_job_run_status(JobRunStatus.DISPATCHED) == ExecutionRunStatus.STARTING
    assert projected.kind.value == "query"
    assert projected.status == ExecutionRunStatus.STARTING


def test_execution_run_projection_infers_notebook_waiting_input():
    run = JobRunModel(
        id=str(uuid.uuid4()),
        job_id=str(uuid.uuid4()),
        project_id=str(uuid.uuid4()),
        owner_id=str(uuid.uuid4()),
        status=JobRunStatus.RUNNING,
        attempt_count=0,
        created_at=datetime.now(UTC),
        result_data=('{"status":"waiting_input","is_paused":true,"needs_external_execution":true}'),
        job=_mock_job(
            project_id=str(uuid.uuid4()),
            name="Execute Notebook",
            job_type="python.jobs.ExecutePythonScriptJob",
        ),
    )

    projected = project_execution_run(run)

    assert infer_execution_run_kind(run).value == "notebook"
    assert map_job_run_status(JobRunStatus.RUNNING, job_run=run) == (
        ExecutionRunStatus.WAITINGINPUT
    )
    assert projected.kind.value == "notebook"
    assert projected.status == ExecutionRunStatus.WAITINGINPUT


def test_get_run_endpoint_projects_job_run(client: TestClient):
    project_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    mock_auth = AuthContext(project=_mock_project(project_id))

    app.dependency_overrides[RUN_READ_AUTH.dependency] = lambda: mock_auth

    with (
        patch(
            "kontext.execution.runs.JobRunDataService.get_run_by_id_async",
            new=AsyncMock(
                return_value=JobRunModel(
                    id=run_id,
                    job_id=str(uuid.uuid4()),
                    project_id=project_id,
                    owner_id=str(uuid.uuid4()),
                    status=JobRunStatus.RUNNING,
                    attempt_count=0,
                    created_at=datetime.now(UTC),
                    job=_mock_job(
                        project_id=project_id,
                        name="Initialize Session",
                        job_type="python.jobs.InitializeSessionJob",
                    ),
                )
            ),
        ),
        patch(
            "kontext.execution.runs.ExecutionRunContextDataService.get_by_run_id_async",
            new=AsyncMock(return_value=None),
        ),
    ):
        try:
            response = client.get(f"/runs/{run_id}?projectId={project_id}")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == run_id
    assert payload["kind"] == "session_init"
    assert payload["status"] == "running"


def test_list_runs_returns_paginated_execution_runs(client: TestClient):
    project_id = str(uuid.uuid4())
    mock_auth = AuthContext(project=_mock_project(project_id))

    page = PaginatedListOfExecutionRunModel(
        items=[
            ExecutionRunModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                owner_id=str(uuid.uuid4()),
                kind=ExecutionRunKind.QUERY,
                status=ExecutionRunStatus.QUEUED,
                created_at=datetime.now(UTC),
            )
        ],
        total_count=1,
        page_index=1,
        page_size=20,
        total_pages=1,
    )

    app.dependency_overrides[RUN_READ_AUTH.dependency] = lambda: mock_auth
    with patch(
        "kontext.api.routers.runs.ExecutionRunService.list_runs_async",
        new=AsyncMock(return_value=page),
    ):
        try:
            response = client.get(f"/runs?projectId={project_id}")
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["totalCount"] == 1
    assert payload["items"][0]["kind"] == "query"


def test_cancel_run_endpoint_returns_cancelled_run(client: TestClient):
    project_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    mock_auth = AuthContext(
        project=_mock_project(project_id),
        user=MagicMock(id=user_id),
    )

    cancelled = ExecutionRunModel(
        id=run_id,
        project_id=project_id,
        owner_id=str(uuid.uuid4()),
        kind=ExecutionRunKind.QUERY,
        status=ExecutionRunStatus.CANCELLED,
        created_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        error_message="Cancelled by user",
    )

    app.dependency_overrides[RUN_WRITE_AUTH.dependency] = lambda: mock_auth
    with patch(
        "kontext.api.routers.runs.ExecutionRunService.cancel_run_async",
        new=AsyncMock(return_value=cancelled),
    ) as cancel_run_async:
        try:
            response = client.post(
                f"/runs/{run_id}/cancel?projectId={project_id}",
                json={"reason": "User requested cancellation"},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    cancel_run_async.assert_awaited_once()
    await_args = cancel_run_async.await_args
    assert await_args is not None
    assert await_args.kwargs["requested_by"] == user_actor(str(user_id))


def test_submit_run_input_endpoint_accepts_agent_waiting_input_run(client: TestClient):
    project_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    mock_auth = AuthContext(
        project=_mock_project(project_id),
        user=MagicMock(id=owner_id),
    )

    waiting_run = ExecutionRunModel(
        id=run_id,
        project_id=project_id,
        owner_id=owner_id,
        kind=ExecutionRunKind.AGENT,
        status=ExecutionRunStatus.WAITINGINPUT,
        created_at=datetime.now(UTC),
    )

    app.dependency_overrides[RUN_WRITE_AUTH.dependency] = lambda: mock_auth
    with (
        patch(
            "kontext.api.routers.runs.validate_run_input_request_async",
            new=AsyncMock(
                return_value=ResolvedExecutionRunInput(
                    run=waiting_run,
                    chat_session_id=uuid.UUID(session_id),
                    paused_run_id=None,
                )
            ),
        ),
        patch(
            "kontext.api.routers.runs.resume_execution_run_input_async",
            new=AsyncMock(),
        ) as resume_mock,
        patch(
            "kontext.api.routers.runs.ExecutionRunService.get_run_async",
            new=AsyncMock(return_value=waiting_run),
        ),
    ):
        try:
            response = client.post(
                f"/runs/{run_id}/input?projectId={project_id}",
                json={
                    "chatSessionId": session_id,
                    "toolOutputs": [
                        {
                            "toolCallId": str(uuid.uuid4()),
                            "toolName": "python",
                            "result": "ok",
                        }
                    ],
                },
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "waiting_input"
    assert resume_mock.await_count == 1


def test_submit_run_input_endpoint_uses_persisted_run_context_without_chat_session_id(
    client: TestClient,
):
    project_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    mock_auth = AuthContext(
        project=_mock_project(project_id),
        user=MagicMock(id=owner_id),
    )

    waiting_run = ExecutionRunModel(
        id=run_id,
        project_id=project_id,
        owner_id=owner_id,
        kind=ExecutionRunKind.AGENT,
        status=ExecutionRunStatus.WAITINGINPUT,
        created_at=datetime.now(UTC),
    )

    app.dependency_overrides[RUN_WRITE_AUTH.dependency] = lambda: mock_auth
    with (
        patch(
            "kontext.api.routers.runs.validate_run_input_request_async",
            new=AsyncMock(
                return_value=ResolvedExecutionRunInput(
                    run=waiting_run,
                    chat_session_id=uuid.UUID(session_id),
                    paused_run_id="paused-run-1",
                )
            ),
        ),
        patch(
            "kontext.api.routers.runs.resume_execution_run_input_async",
            new=AsyncMock(),
        ) as resume_mock,
        patch(
            "kontext.api.routers.runs.ExecutionRunService.get_run_async",
            new=AsyncMock(return_value=waiting_run),
        ),
    ):
        try:
            response = client.post(
                f"/runs/{run_id}/input?projectId={project_id}",
                json={
                    "toolOutputs": [
                        {
                            "toolCallId": str(uuid.uuid4()),
                            "toolName": "python",
                            "result": "ok",
                        }
                    ],
                },
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 202
    assert resume_mock.await_count == 1
    assert resume_mock.await_args is not None
    _, kwargs = resume_mock.await_args
    assert str(kwargs["chat_session_id"]) == session_id
    assert kwargs["paused_run_id"] == "paused-run-1"


def test_submit_run_input_endpoint_rejects_invalid_run_state(client: TestClient):
    project_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    mock_auth = AuthContext(
        project=_mock_project(project_id),
        user=MagicMock(id=owner_id),
    )

    app.dependency_overrides[RUN_WRITE_AUTH.dependency] = lambda: mock_auth
    with patch(
        "kontext.api.routers.runs.validate_run_input_request_async",
        new=AsyncMock(side_effect=HTTPException(status_code=409, detail="not waiting")),
    ):
        try:
            response = client.post(
                f"/runs/{run_id}/input?projectId={project_id}",
                json={
                    "chatSessionId": str(uuid.uuid4()),
                    "toolOutputs": [
                        {
                            "toolCallId": str(uuid.uuid4()),
                            "toolName": "python",
                            "result": "ok",
                        }
                    ],
                },
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_validate_run_input_request_resolves_persisted_context():
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    session_id = uuid.uuid4()

    waiting_run = ExecutionRunModel(
        id=str(run_id),
        project_id=str(project_id),
        owner_id=str(owner_id),
        kind=ExecutionRunKind.AGENT,
        status=ExecutionRunStatus.WAITINGINPUT,
        created_at=datetime.now(UTC),
    )
    session = MagicMock(owner_id=owner_id)
    run_context = MagicMock(
        chat_session_id=session_id,
        agent_runtime_run_id="paused-run-2",
    )

    service = ExecutionLifecycleService()
    with (
        patch(
            "kontext.execution.lifecycle.ExecutionRunService.get_run_async",
            new=AsyncMock(return_value=waiting_run),
        ),
        patch(
            "kontext.execution.lifecycle.ExecutionRunContextDataService.get_by_run_id_async",
            new=AsyncMock(return_value=run_context),
        ),
    ):
        resolved = await service.validate_run_input_request_async(
            project_id=project_id,
            run_id=run_id,
            request=MagicMock(chat_session_id=None, tool_outputs=[MagicMock()]),
            user_id=owner_id,
            get_chat_session=AsyncMock(return_value=session),
        )

    assert resolved.run == waiting_run
    assert resolved.chat_session_id == session_id
    assert resolved.paused_run_id == "paused-run-2"


@pytest.mark.asyncio
async def test_persist_agent_execution_event_enriches_pause_with_platform_run_id():
    project_id = uuid.uuid4()
    platform_run_id = uuid.uuid4()
    chat_session_id = uuid.uuid4()

    event = SimpleRunEvent(
        event_type=RunEvent.RUNPAUSED,
        content="Run paused for external execution",
        event_data=EventData(
            RunPausedEventData(
                run_id="agent-run-1",
                tool_calls=[],
            )
        ),
    )

    service = ExecutionLifecycleService()
    with (
        patch(
            "kontext.execution.lifecycle.JobRunDataService.update_status_async",
            new=AsyncMock(),
        ),
        patch(
            "kontext.execution.lifecycle.JobRunLogDataService.add_log_async",
            new=AsyncMock(),
        ),
        patch(
            "kontext.execution.lifecycle.ExecutionRunContextDataService.upsert_context_async",
            new=AsyncMock(),
        ),
    ):
        persisted = await service.persist_agent_execution_event_async(
            project_id=project_id,
            platform_run_id=platform_run_id,
            chat_session_id=chat_session_id,
            event=event,
        )

    assert persisted.event_data is not None
    pause_data = persisted.event_data.root
    assert isinstance(pause_data, RunPausedEventData)
    assert pause_data.platform_run_id == str(platform_run_id)


def test_retry_run_endpoint_returns_new_execution_run(client: TestClient):
    project_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    retry_run_id = str(uuid.uuid4())
    mock_auth = AuthContext(
        project=_mock_project(project_id),
        user=MagicMock(id=str(uuid.uuid4())),
    )

    retried = ExecutionRunModel(
        id=retry_run_id,
        project_id=project_id,
        owner_id=str(uuid.uuid4()),
        kind=ExecutionRunKind.JOB,
        status=ExecutionRunStatus.QUEUED,
        created_at=datetime.now(UTC),
    )

    app.dependency_overrides[RUN_WRITE_AUTH.dependency] = lambda: mock_auth
    app.dependency_overrides[get_queue_client] = lambda: MagicMock()
    with patch(
        "kontext.api.routers.runs.ExecutionRunService.retry_run_async",
        new=AsyncMock(return_value=retried),
    ):
        try:
            response = client.post(
                f"/runs/{run_id}/retry?projectId={project_id}",
                json={"reason": "Retry after fixing configuration"},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["id"] == retry_run_id
    assert response.json()["status"] == "queued"


def test_execute_query_async_returns_execution_run(client: TestClient):
    project_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())

    mock_auth = AuthContext(
        project=_mock_project(project_id),
        user=MagicMock(id=owner_id),
    )

    execution_run = ExecutionRunModel(
        id=run_id,
        project_id=project_id,
        owner_id=owner_id,
        kind=ExecutionRunKind.QUERY,
        status=ExecutionRunStatus.QUEUED,
        created_at=datetime.now(UTC),
    )

    app.dependency_overrides[QUERY_EXECUTE_AUTH.dependency] = lambda: mock_auth

    with patch(
        "kontext.api.routers.query.execute_query_async_service",
        new=AsyncMock(return_value=execution_run),
    ):
        app.dependency_overrides[QUERY_EXECUTE_AUTH.dependency] = lambda: mock_auth
        app.dependency_overrides[get_queue_client] = lambda: MagicMock()
        try:
            response = client.post(
                "/query/execute-async",
                json={
                    "projectId": project_id,
                    "sessionId": session_id,
                    "sqlQuery": "select 1",
                },
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 202
    payload = response.json()
    assert payload["id"] == run_id
    assert payload["kind"] == "query"
    assert payload["status"] == "queued"


def test_initialize_session_async_returns_execution_run(client: TestClient):
    project_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())

    mock_auth = AuthContext(
        project=_mock_project(project_id),
        user=MagicMock(id=owner_id),
    )

    execution_run = ExecutionRunModel(
        id=run_id,
        project_id=project_id,
        owner_id=owner_id,
        kind=ExecutionRunKind.SESSIONINIT,
        status=ExecutionRunStatus.QUEUED,
        created_at=datetime.now(UTC),
    )

    with patch(
        "kontext.api.routers.query_sessions.initialize_session_async_service",
        new=AsyncMock(return_value=execution_run),
    ):
        app.dependency_overrides[SESSION_EXECUTE_AUTH.dependency] = lambda: mock_auth
        app.dependency_overrides[get_queue_client] = lambda: MagicMock()
        try:
            response = client.post(
                "/session/init-async",
                json={
                    "projectId": project_id,
                    "sessionId": session_id,
                    "persistent": True,
                },
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 202
    payload = response.json()
    assert payload["id"] == run_id
    assert payload["kind"] == "session_init"
    assert payload["status"] == "queued"


def test_run_write_auth_requires_job_update_only():
    """Cancelling/retrying/submitting input for a run is a job-run operation.

    The write dependency must not be satisfiable by a query-session permission:
    query sessions are closed/deleted through their own endpoints, not via the
    run-cancel/retry surface.
    """
    from kontext.auth import JobPermissions, QuerySessionPermissions

    permissions = [
        cell
        for cell in RUN_WRITE_AUTH.dependency.__closure__
        if isinstance(cell.cell_contents, list)
    ]
    assert len(permissions) == 1
    required = permissions[0].cell_contents

    assert required == [JobPermissions.UPDATE]
    assert QuerySessionPermissions.UPDATE not in required
