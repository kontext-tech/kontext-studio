import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from kontext.api.dependencies import AuthContext
from kontext.api.main import app
from kontext.api.routers.chats import (
    CHAT_SESSION_UPDATE_AUTH,
    CHAT_UPLOAD_PREPARATION_AUTH,
)
from kontext.api.services.chats import (
    get_chat_upload_preparation_status_service,
    seed_chat_attachment_context_service,
)
from kontext.schema import (
    AccessLevel,
    CatalogColumn,
    CatalogEntityDetail,
    CatalogEntitySummary,
    CatalogEntityType,
    ChatSessionModel,
    ChatUploadPreparationStatus,
    ExecutionRunKind,
    ExecutionRunModel,
    ExecutionRunStatus,
    FileFormatType,
    JobRunStatus,
    ProjectConfiguration,
    ProjectModel,
    PythonExecutionApprovalMode,
    SeedChatAttachmentContextRequest,
    StartChatUploadPreparationResponse,
    UserType,
    UserWithRolesModel,
)


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
            max_file_bytes_size=1024,
            total_storage_allocation_bytes=4096,
            features=[],
        ),
    )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_for_chat_upload_tests")
    return TestClient(app)


def test_start_chat_upload_preparation_route_returns_started_workflow(
    client: TestClient,
):
    project_id = str(uuid.uuid4())
    auth_context = AuthContext(
        project=_mock_project(project_id),
        user=UserWithRolesModel(
            id=str(uuid.uuid4()),
            first_name="Test",
            last_name="User",
            user_type=UserType.USER,
            roles=[],
            permission_claims=[],
            project_roles={},
        ),
    )
    started_response = StartChatUploadPreparationResponse(
        run_id=str(uuid.uuid4()),
        internal_catalog_connection_id=str(uuid.uuid4()),
        accepted_files=[],
        upload_errors=[],
        success_count=0,
        failure_count=0,
    )

    app.dependency_overrides[CHAT_UPLOAD_PREPARATION_AUTH.dependency] = lambda: auth_context

    with patch(
        "kontext.api.routers.chats.start_chat_upload_preparation_service",
        new=AsyncMock(return_value=started_response),
    ) as start_service:
        try:
            response = client.post(
                f"/ai/chat/upload-preparations?projectId={project_id}&allowOverwrite=true",
                files=[("files", ("orders.csv", b"id,total\n1,10\n", "text/csv"))],
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    assert payload["runId"] == started_response.run_id
    assert payload["internalCatalogConnectionId"] == (
        started_response.internal_catalog_connection_id
    )
    assert start_service.await_count == 1
    assert start_service.await_args is not None
    assert start_service.await_args.kwargs["allow_overwrite"] is True


def test_seed_chat_attachment_context_route_returns_no_content(client: TestClient):
    project_id = str(uuid.uuid4())
    chat_session_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    auth_context = AuthContext(
        project=_mock_project(project_id),
        resource=ChatSessionModel(
            id=chat_session_id,
            project_id=project_id,
            session_name="Attached chat",
            date_created=datetime.now(UTC),
            python_execution_approval_mode=PythonExecutionApprovalMode.ALWAYSASK,
            is_deleted=False,
        ),
        user=UserWithRolesModel(
            id=str(uuid.uuid4()),
            first_name="Test",
            last_name="User",
            user_type=UserType.USER,
            roles=[],
            permission_claims=[],
            project_roles={},
        ),
    )

    app.dependency_overrides[CHAT_SESSION_UPDATE_AUTH.dependency] = lambda: auth_context

    with patch(
        "kontext.api.routers.chats.seed_chat_attachment_context_service",
        new=AsyncMock(return_value=None),
    ) as seed_service:
        try:
            response = client.post(
                f"/ai/chat/session/{chat_session_id}/attachment-context?projectId={project_id}",
                json={"uploadPreparationRunId": run_id},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 204
    assert seed_service.await_count == 1
    assert seed_service.await_args is not None
    assert seed_service.await_args.kwargs["chat_session_id"] == uuid.UUID(chat_session_id)
    assert seed_service.await_args.kwargs["project_id"] == uuid.UUID(project_id)
    assert seed_service.await_args.kwargs["request"].upload_preparation_run_id == run_id


@pytest.mark.asyncio
async def test_chat_upload_preparation_status_collects_ready_and_failed_files():
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()
    child_run_id = uuid.uuid4()
    internal_connection_id = str(uuid.uuid4())
    ready_file_id = str(uuid.uuid4())
    failed_file_id = str(uuid.uuid4())

    root_run = ExecutionRunModel(
        id=str(run_id),
        project_id=str(project_id),
        owner_id=None,
        kind=ExecutionRunKind.WORKFLOW,
        status=ExecutionRunStatus.FAILED,
        created_at=datetime.now(UTC),
        progress=100,
    )
    root_job_run = SimpleNamespace(parameters=json.dumps({}))
    child_run = SimpleNamespace(
        id=str(child_run_id),
        status=JobRunStatus.FAILED,
        progress=100,
        error_message="Lakehouse ingest completed with 1 failure(s)",
        result_data=json.dumps(
            {
                "success": False,
                "message": "Lakehouse ingest completed with 1 failure(s)",
                "data": {
                    "connection_id": internal_connection_id,
                    "successful_file_ids": [ready_file_id],
                    "failed_files": [
                        {
                            "id": failed_file_id,
                            "error": "Profiling returned no schema",
                        }
                    ],
                },
                "result_type": "PythonJobResult",
            }
        ),
    )
    workflow_state = SimpleNamespace(
        workflow_key="chat_upload_preparation",
        steps=[
            SimpleNamespace(
                key="lakehouse-ingest",
                name="Lakehouse ingest",
                status="failed",
                run_id=str(child_run_id),
                error_message="Lakehouse ingest completed with 1 failure(s)",
            )
        ],
    )

    with (
        patch(
            "kontext.api.services.chats.ExecutionRunService.get_run_async",
            new=AsyncMock(return_value=root_run),
        ),
        patch(
            "kontext.api.services.chats.JobRunDataService.get_run_by_id_async",
            new=AsyncMock(return_value=root_job_run),
        ),
        patch(
            "kontext.api.services.chats.ExecutionRunContextDataService.get_by_run_id_async",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    engine_metadata_json=json.dumps(
                        {
                            "chatUploadPreparation": {
                                "internalCatalogConnectionId": internal_connection_id,
                                "acceptedFiles": [
                                    {
                                        "fileId": ready_file_id,
                                        "filename": "orders.csv",
                                        "fileType": "CSV",
                                        "size": 14,
                                    },
                                    {
                                        "fileId": failed_file_id,
                                        "filename": "customers.csv",
                                        "fileType": "CSV",
                                        "size": 18,
                                    },
                                ],
                                "uploadErrors": [
                                    {
                                        "filename": "broken.csv",
                                        "error": "File is empty",
                                    }
                                ],
                            }
                        }
                    )
                )
            ),
        ),
        patch(
            "kontext.api.services.chats.extract_workflow_projection_metadata",
            return_value=SimpleNamespace(workflow_state=workflow_state),
        ),
        patch(
            "kontext.api.services.chats.ExecutionRunContextDataService.list_by_root_run_id_async",
            new=AsyncMock(
                return_value=[
                    SimpleNamespace(run_id=run_id),
                    SimpleNamespace(run_id=child_run_id),
                ]
            ),
        ),
        patch(
            "kontext.api.services.chats.JobRunDataService.get_runs_by_ids_async",
            new=AsyncMock(return_value=[child_run]),
        ),
    ):
        status = await get_chat_upload_preparation_status_service(
            project_id=project_id,
            run_id=run_id,
        )

    assert status.run_id == str(run_id)
    assert status.status == "failed"
    assert status.internal_catalog_connection_id == internal_connection_id
    assert status.ready_file_ids == [ready_file_id]
    assert len(status.failed_files) == 2
    assert {failure.filename for failure in status.failed_files} == {
        "broken.csv",
        "customers.csv",
    }
    assert status.steps[0].run_id == str(child_run_id)
    assert status.steps[0].status == "failed"


@pytest.mark.asyncio
async def test_chat_upload_preparation_status_keeps_success_with_ready_files():
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()
    child_run_id = uuid.uuid4()
    internal_connection_id = str(uuid.uuid4())
    ready_file_id = str(uuid.uuid4())

    root_run = ExecutionRunModel(
        id=str(run_id),
        project_id=str(project_id),
        owner_id=None,
        kind=ExecutionRunKind.WORKFLOW,
        status=ExecutionRunStatus.SUCCEEDED,
        created_at=datetime.now(UTC),
        progress=100,
    )
    root_job_run = SimpleNamespace(parameters=json.dumps({}))
    child_run = SimpleNamespace(
        id=str(child_run_id),
        status=JobRunStatus.SUCCEEDED,
        progress=100,
        error_message="Successfully ingested 1 file(s) into the lakehouse",
        result_data=json.dumps(
            {
                "success": True,
                "message": "Successfully ingested 1 file(s) into the lakehouse",
                "data": {
                    "connection_id": internal_connection_id,
                    "successful_file_ids": [ready_file_id],
                    "failed_files": [],
                },
                "result_type": "PythonJobResult",
            }
        ),
    )
    workflow_state = SimpleNamespace(
        workflow_key="chat_upload_preparation",
        steps=[
            SimpleNamespace(
                key="lakehouse-ingest",
                name="Lakehouse ingest",
                status="succeeded",
                run_id=str(child_run_id),
                error_message="Successfully ingested 1 file(s) into the lakehouse",
            )
        ],
    )

    with (
        patch(
            "kontext.api.services.chats.ExecutionRunService.get_run_async",
            new=AsyncMock(return_value=root_run),
        ),
        patch(
            "kontext.api.services.chats.JobRunDataService.get_run_by_id_async",
            new=AsyncMock(return_value=root_job_run),
        ),
        patch(
            "kontext.api.services.chats.ExecutionRunContextDataService.get_by_run_id_async",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    engine_metadata_json=json.dumps(
                        {
                            "chatUploadPreparation": {
                                "internalCatalogConnectionId": internal_connection_id,
                                "acceptedFiles": [
                                    {
                                        "fileId": ready_file_id,
                                        "filename": "orders.csv",
                                        "fileType": "CSV",
                                        "size": 14,
                                    }
                                ],
                                "uploadErrors": [],
                            }
                        }
                    )
                )
            ),
        ),
        patch(
            "kontext.api.services.chats.extract_workflow_projection_metadata",
            return_value=SimpleNamespace(workflow_state=workflow_state),
        ),
        patch(
            "kontext.api.services.chats.ExecutionRunContextDataService.list_by_root_run_id_async",
            new=AsyncMock(
                return_value=[
                    SimpleNamespace(run_id=run_id),
                    SimpleNamespace(run_id=child_run_id),
                ]
            ),
        ),
        patch(
            "kontext.api.services.chats.JobRunDataService.get_runs_by_ids_async",
            new=AsyncMock(return_value=[child_run]),
        ),
    ):
        status = await get_chat_upload_preparation_status_service(
            project_id=project_id,
            run_id=run_id,
        )

    assert status.run_id == str(run_id)
    assert status.status == "succeeded"
    assert status.internal_catalog_connection_id == internal_connection_id
    assert status.ready_file_ids == [ready_file_id]
    assert status.failed_files == []
    assert status.steps[0].run_id == str(child_run_id)
    assert status.steps[0].status == "succeeded"


@pytest.mark.asyncio
async def test_seed_chat_attachment_context_service_rejects_zero_ready_files():
    project_id = uuid.uuid4()
    chat_session_id = uuid.uuid4()
    request = SeedChatAttachmentContextRequest(upload_preparation_run_id=str(uuid.uuid4()))

    with (
        patch(
            "kontext.api.services.chats.get_chat_upload_preparation_status_service",
            new=AsyncMock(
                return_value=ChatUploadPreparationStatus(
                    run_id=request.upload_preparation_run_id,
                    status="failed",
                    progress=100,
                    internal_catalog_connection_id=str(uuid.uuid4()),
                    ready_file_ids=[],
                    failed_files=[],
                    steps=[],
                )
            ),
        ),
        pytest.raises(HTTPException) as exc_info,
    ):
        await seed_chat_attachment_context_service(
            chat_session_id=chat_session_id,
            project_id=project_id,
            request=request,
        )

    assert exc_info.value.status_code == 400
    assert "ready attached files" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_seed_chat_attachment_context_service_persists_multi_sheet_context():
    project_id = uuid.uuid4()
    chat_session_id = uuid.uuid4()
    run_id = uuid.uuid4()
    file_id = str(uuid.uuid4())
    connection_id = str(uuid.uuid4())
    request = SeedChatAttachmentContextRequest(upload_preparation_run_id=str(run_id))

    status = ChatUploadPreparationStatus(
        run_id=str(run_id),
        status="succeeded",
        progress=100,
        internal_catalog_connection_id=connection_id,
        ready_file_ids=[file_id],
        failed_files=[],
        steps=[],
    )
    entity_one = CatalogEntityDetail(
        entity=CatalogEntitySummary(
            id=str(uuid.uuid4()),
            connection_id=connection_id,
            namespace_name="bronze",
            entity_name="Financial_Sample_Products",
            entity_type=CatalogEntityType.TABLE,
            row_count=10,
            column_count=2,
        ),
        columns=[
            CatalogColumn(name="product_id"),
            CatalogColumn(name="name"),
        ],
    )
    entity_two = CatalogEntityDetail(
        entity=CatalogEntitySummary(
            id=str(uuid.uuid4()),
            connection_id=connection_id,
            namespace_name="bronze",
            entity_name="Financial_Sample_Orders",
            entity_type=CatalogEntityType.TABLE,
            row_count=20,
            column_count=2,
        ),
        columns=[
            CatalogColumn(name="order_id"),
            CatalogColumn(name="amount"),
        ],
    )

    with (
        patch(
            "kontext.api.services.chats.get_chat_upload_preparation_status_service",
            new=AsyncMock(return_value=status),
        ),
        patch(
            "kontext.api.services.chats.ExecutionRunContextDataService.get_by_run_id_async",
            new=AsyncMock(
                return_value=SimpleNamespace(
                    engine_metadata_json=json.dumps(
                        {
                            "chatUploadPreparation": {
                                "internalCatalogConnectionId": connection_id,
                                "acceptedFiles": [
                                    {
                                        "fileId": file_id,
                                        "filename": "Financial Sample.xlsx",
                                        "fileType": FileFormatType.EXCEL.value,
                                    }
                                ],
                            }
                        }
                    )
                )
            ),
        ),
        patch(
            "kontext.api.services.chats.CatalogManagementService.get_source_entities",
            new=AsyncMock(return_value=[entity_one, entity_two]),
        ),
        patch(
            "kontext.api.services.chats.ChatSessionDataService.upsert_attachment_context_async",
            new=AsyncMock(return_value=None),
        ) as upsert_context,
    ):
        await seed_chat_attachment_context_service(
            chat_session_id=chat_session_id,
            project_id=project_id,
            request=request,
        )

    assert upsert_context.await_count == 1
    assert upsert_context.await_args is not None
    assert upsert_context.await_args.args[0] == chat_session_id
    stored_context = upsert_context.await_args.args[1]
    assert stored_context.upload_preparation_run_id == str(run_id)
    assert stored_context.internal_catalog_connection_id == connection_id
    assert len(stored_context.files) == 1
    assert stored_context.files[0].file_name == "Financial Sample.xlsx"
    assert {table.entity_name for table in stored_context.tables} == {
        "Financial_Sample_Products",
        "Financial_Sample_Orders",
    }
