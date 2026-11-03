import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from kontext.api.dependencies import AuthContext
from kontext.api.main import app
from kontext.api.routers.chats import CHAT_SESSION_CREATE_AUTH, CHAT_SESSION_UPDATE_AUTH
from kontext.schema import (
    AccessLevel,
    ChatSessionModel,
    ProjectConfiguration,
    ProjectModel,
    PythonExecutionApprovalMode,
)


@pytest.fixture
def mock_jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test_secret_key_for_validation_tests")


@pytest.fixture
def client(mock_jwt_secret):
    return TestClient(app)


def test_create_chat_session_resolves_model_without_project_allowlist(client):
    project_id = str(uuid.uuid4())
    mock_project = ProjectModel(
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
    mock_auth = AuthContext(project=mock_project)

    # Override the specific authorization dependencies
    app.dependency_overrides[CHAT_SESSION_CREATE_AUTH.dependency] = lambda: mock_auth

    # Mock the service to avoid DB access
    with patch("kontext.chat.sessions.ChatSessionDataService") as MockService:
        mock_service_instance = MockService.return_value
        mock_service_instance.create_session_async = AsyncMock(
            return_value=ChatSessionModel(
                id=str(uuid.uuid4()),
                project_id=project_id,
                session_name="Test Session",
                model_selection_id="allowed-model-1",
                date_created=datetime(2023, 1, 1, tzinfo=UTC),
                python_execution_approval_mode=PythonExecutionApprovalMode.ALWAYSASK,
                is_deleted=False,
            )
        )
        mock_resolved_model = Mock()
        mock_resolved_model.model_dump.return_value = {
            "selection_id": "allowed-model-1",
            "canonical_model_id": "allowed-model-1",
            "adapter_type": "openai_compatible",
        }

        try:
            with patch(
                "kontext.chat.sessions.resolve_model_selection",
                new=AsyncMock(return_value=mock_resolved_model),
            ):
                response = client.post(
                    "/ai/chat/session",
                    json={
                        "sessionName": "Test Session",
                        "modelSelectionId": "resolved-model",
                        "projectId": project_id,
                        "pythonExecutionApprovalMode": "always_ask",
                    },
                )

                assert response.status_code == 201

        finally:
            app.dependency_overrides.clear()


def test_update_chat_session_forbidden_model(client):
    project_id = str(uuid.uuid4())
    mock_project = ProjectModel(
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
    mock_auth = AuthContext(project=mock_project)

    # Override the specific authorization dependencies
    app.dependency_overrides[CHAT_SESSION_UPDATE_AUTH.dependency] = lambda: mock_auth

    # Mock the service to avoid DB access
    with patch("kontext.chat.sessions.ChatSessionDataService"):
        session_id = uuid.uuid4()
        # Mock the session model that would be returned by the resource getter
        mock_session = ChatSessionModel(
            id=str(session_id),
            project_id=project_id,
            session_name="Test Session",
            model_selection_id="allowed-model-1",
            date_created=datetime.now(UTC),
            python_execution_approval_mode=PythonExecutionApprovalMode.ALWAYSASK,
            is_deleted=False,
        )
        mock_auth.resource = mock_session

        try:
            # Try to update a session with a forbidden model
            # Note: projectId is used because of camelCase configuration
            response = client.put(
                f"/ai/chat/session/{session_id}?projectId={project_id}",
                json={"modelId": "forbidden-model"},
            )

            # modelId is no longer allowed in update request schema;
            # expect validation error (422)
            assert response.status_code == 422
            assert any(
                (e.get("loc") and ("modelId" in e.get("loc") or "model_id" in e.get("loc")))
                for e in response.json()["detail"]
            )
        finally:
            app.dependency_overrides.clear()
