from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import select

from kontext.common.jobs.trigger_actor import user_actor
from kontext.data import (
    ExecutionRunContextDataService,
    JobRunDataService,
    JobRunLogDataService,
)
from kontext.data.database import get_engine, get_session_factory, get_sync_db_session
from kontext.data.models import Project
from kontext.jobs.runs import ExecutionRunService
from kontext.jobs.workflows import (
    WorkflowJobStepDefinition,
    WorkflowOrchestrationService,
    WorkflowStartRequest,
)
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.schema import ExecutionRunKind, ExecutionRunStatus, JobRunStatus
from kontext.storage import clear_storage_provider_cache


def _clear_runtime_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    clear_storage_provider_cache()


@pytest.fixture()
def local_project_id(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_url = f"sqlite:///{tmp_path / 'kontext.db'}"
    monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KONTEXT_LOCAL_STORAGE_PATH", str(tmp_path / "storage"))

    with (
        patch(
            "kontext.runtime.local.config.get_local_database_url",
            return_value=db_url,
        ),
        patch(
            "kontext.runtime.local.auth.get_local_jwt_secret",
            return_value="test-local-secret",
        ),
    ):
        _clear_runtime_caches()
        try:
            initialize_local_mode()
            with get_sync_db_session() as session:
                project_id = session.execute(
                    select(Project.id).where(Project.project_code == "local")
                ).scalar_one()
            yield project_id
        finally:
            _clear_runtime_caches()


@pytest.mark.asyncio
async def test_workflow_orchestration_dispatches_dag_and_aggregates_logs(
    local_project_id,
):
    workflow_service = WorkflowOrchestrationService()
    root_run_id = await workflow_service.start_workflow_async(
        project_id=local_project_id,
        workflow=WorkflowStartRequest(
            workflow_key="test_dag",
            workflow_name="Test DAG",
            triggered_by=user_actor("test"),
            steps=[
                WorkflowJobStepDefinition(
                    key="extract",
                    name="Extract data",
                    job_type="python.jobs.TestExtractJob",
                    job_name="Test Extract",
                    job_description="Extracts data for the test workflow",
                    parameters={"file_id": "file-1"},
                    timeout_seconds=300,
                ),
                WorkflowJobStepDefinition(
                    key="index",
                    name="Index data",
                    job_type="python.jobs.TestIndexJob",
                    job_name="Test Index",
                    job_description="Indexes data after extraction",
                    parameters={"file_id": "file-1"},
                    depends_on=["extract"],
                    timeout_seconds=300,
                ),
            ],
        ),
        queue_client=None,
    )

    execution_service = ExecutionRunService()
    root_run = await execution_service.get_run_async(
        project_id=local_project_id,
        run_id=root_run_id,
    )
    assert root_run is not None
    assert root_run.kind == ExecutionRunKind.WORKFLOW
    assert root_run.status == ExecutionRunStatus.RUNNING
    assert root_run.workflow_key == "test_dag"
    assert root_run.is_workflow_root is True

    context_service = ExecutionRunContextDataService(local_project_id)
    contexts = await context_service.list_by_root_run_id_async(root_run_id)
    child_run_ids = [
        UUID(str(context.run_id))
        for context in contexts
        if UUID(str(context.run_id)) != root_run_id
    ]
    assert len(child_run_ids) == 1

    extract_run_id = child_run_ids[0]
    extract_run = await execution_service.get_run_async(
        project_id=local_project_id,
        run_id=extract_run_id,
    )
    assert extract_run is not None
    assert extract_run.root_run_id == str(root_run_id)
    assert extract_run.parent_run_id == str(root_run_id)
    assert extract_run.step_key == "extract"
    assert extract_run.is_workflow_root is False

    await JobRunLogDataService(local_project_id).add_log_async(
        job_run_id=extract_run_id,
        message="Extract step emitted a log line",
    )
    await JobRunDataService(local_project_id).update_status_async(
        extract_run_id,
        status=JobRunStatus.SUCCEEDED.value,
        error_message="",
        result_data='{"status":"ok"}',
    )
    await workflow_service.handle_run_status_change_async(
        project_id=local_project_id,
        run_id=extract_run_id,
        queue_client=None,
    )

    contexts = await context_service.list_by_root_run_id_async(root_run_id)
    child_run_ids = [
        UUID(str(context.run_id))
        for context in contexts
        if UUID(str(context.run_id)) != root_run_id
    ]
    assert len(child_run_ids) == 2

    index_run_id = next(run_id for run_id in child_run_ids if run_id != extract_run_id)
    index_run = await execution_service.get_run_async(
        project_id=local_project_id,
        run_id=index_run_id,
    )
    assert index_run is not None
    assert index_run.step_key == "index"
    assert index_run.root_run_id == str(root_run_id)

    await JobRunDataService(local_project_id).update_status_async(
        index_run_id,
        status=JobRunStatus.SUCCEEDED.value,
        error_message="",
        result_data='{"status":"ok"}',
    )
    await workflow_service.handle_run_status_change_async(
        project_id=local_project_id,
        run_id=index_run_id,
        queue_client=None,
    )

    completed_root_run = await execution_service.get_run_async(
        project_id=local_project_id,
        run_id=root_run_id,
    )
    assert completed_root_run is not None
    assert completed_root_run.status == ExecutionRunStatus.SUCCEEDED
    assert completed_root_run.progress == 100

    logs = await execution_service.get_logs_async(
        project_id=local_project_id,
        run_id=root_run_id,
        limit=100,
    )
    assert any(
        log.run_id == str(root_run_id)
        and log.source_run_id == str(extract_run_id)
        and log.step_key == "extract"
        and log.message == "Extract step emitted a log line"
        for log in logs
    )
