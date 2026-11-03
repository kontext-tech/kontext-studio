from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import ANY, AsyncMock, MagicMock

from fastapi.testclient import TestClient

from kontext.api.dependencies import AuthContext
from kontext.api.main import app
from kontext.api.routers.chats import CHAT_SESSION_UPDATE_AUTH
from kontext.common.jobs.trigger_actor import chat_session_actor
from kontext.schema import (
    AccessLevel,
    ChatSessionModel,
    ProjectConfiguration,
    ProjectModel,
    PythonExecutionApprovalMode,
    PythonExecutionResult,
    PythonExecutionTargetType,
)


def _mock_auth(project_id: str, session_id: str) -> AuthContext:
    user_id = str(uuid.uuid4())
    project = ProjectModel(
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
    resource = ChatSessionModel(
        id=session_id,
        project_id=project_id,
        session_name="Session",
        date_created=datetime.now(UTC),
        python_execution_approval_mode=PythonExecutionApprovalMode.ALWAYSASK,
        is_deleted=False,
    )
    return AuthContext(
        user=MagicMock(id=user_id),
        project=project,
        resource=resource,
    )


def test_execute_python_script_route_uses_shared_session_python_coordinator(
    monkeypatch,
):
    project_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    auth_context = _mock_auth(project_id, session_id)
    execute_chat_session_python_script = AsyncMock(
        return_value=MagicMock(
            python_result=PythonExecutionResult(
                success=True,
                message="ok",
                execution_run_id="run-chat-1",
                target_type=PythonExecutionTargetType.SESSION,
                outputs=[],
            )
        )
    )
    monkeypatch.setattr(
        "kontext.api.services.chats.execute_chat_session_python_impl",
        execute_chat_session_python_script,
    )

    app.dependency_overrides[CHAT_SESSION_UPDATE_AUTH.dependency] = lambda: auth_context

    client = TestClient(app)
    response = client.post(
        f"/ai/chat/session/{session_id}/execute-python",
        params={"projectId": project_id},
        json={"code": "print('ok')"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["targetType"] == "session"
    await_args = execute_chat_session_python_script.await_args
    assert await_args is not None
    assert await_args.kwargs == {
        "project_id": project_id,
        "chat_session_id": session_id,
        "code": "print('ok')",
        "owner_id": auth_context.user_id,
        "triggered_by": chat_session_actor(session_id),
        "chat_session_data_service": ANY,
    }


def test_execute_python_script_route_translates_infra_failure(monkeypatch):
    """An unhandled infra error must become a structured 503, not a raw 500."""
    project_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    auth_context = _mock_auth(project_id, session_id)
    monkeypatch.setattr(
        "kontext.api.services.chats.execute_chat_session_python_impl",
        AsyncMock(side_effect=RuntimeError("worker unavailable")),
    )

    app.dependency_overrides[CHAT_SESSION_UPDATE_AUTH.dependency] = lambda: auth_context
    client = TestClient(app)
    response = client.post(
        f"/ai/chat/session/{session_id}/execute-python",
        params={"projectId": project_id},
        json={"code": "print('ok')"},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "Python execution failed" in response.json()["detail"]


def test_execute_python_script_route_translates_bad_request(monkeypatch):
    project_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    auth_context = _mock_auth(project_id, session_id)
    monkeypatch.setattr(
        "kontext.api.services.chats.execute_chat_session_python_impl",
        AsyncMock(side_effect=ValueError("Python code cannot be empty.")),
    )

    app.dependency_overrides[CHAT_SESSION_UPDATE_AUTH.dependency] = lambda: auth_context
    client = TestClient(app)
    response = client.post(
        f"/ai/chat/session/{session_id}/execute-python",
        params={"projectId": project_id},
        json={"code": "   "},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Python code cannot be empty."
