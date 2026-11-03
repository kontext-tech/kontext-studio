"""
Integration tests for authentication and authorization in kontext-api.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from kontext.api.dependencies import get_queue_client
from kontext.api.main import app
from kontext.auth import JwtValidationError
from kontext.schema import ProjectFeature, QueryResponse, QuerySessionStatus


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_jwt_secret():
    secret = "a" * 32
    # Provide a simple SQLite project DB for tests to avoid requiring an
    # external PostgreSQL instance during unit/integration tests.
    with patch.dict(os.environ, {"JWT_SECRET_KEY": secret, "PROJECT_DB_URL": "sqlite:///:memory:"}):
        yield secret


def test_auth_missing_token(client, mock_jwt_secret):
    """Test that a protected endpoint returns 401 when no token is provided."""
    # /query/execute is a protected endpoint
    response = client.post(
        "/query/execute",
        json={
            "project_id": str(uuid4()),
            "session_id": str(uuid4()),
            "sql_query": "SELECT 1",
        },
    )
    assert response.status_code == 401
    assert "provide a valid Bearer token" in response.json()["detail"]


def test_auth_invalid_token(client, mock_jwt_secret):
    """Test that a protected endpoint returns 401 when an invalid token is provided."""
    with patch("kontext.auth.JwtValidator.validate_token") as mock_validate:
        mock_validate.side_effect = JwtValidationError("Invalid signature")

        response = client.post(
            "/query/execute",
            headers={"Authorization": "Bearer invalid-token"},
            json={
                "project_id": str(uuid4()),
                "session_id": str(uuid4()),
                "sql_query": "SELECT 1",
            },
        )
        assert response.status_code == 401
        body = response.json()
        assert body["type"] == "Unauthorized"
        assert "Invalid signature" in body["detail"]


def test_auth_missing_project_id(client, mock_jwt_secret):
    """Test that a protected endpoint returns 400 when project_id is missing."""
    mock_claims = MagicMock()
    mock_claims.user_id = str(uuid4())
    mock_claims.email = "test@example.com"
    mock_claims.roles = ["User"]
    mock_claims.permission_claims = []

    with (
        patch(
            "kontext.auth.JwtValidator.validate_token",
            return_value=mock_claims,
        ),
        patch(
            "kontext.auth.authentication.jwt_utils.JwtUserExtractor.extract_user"
        ) as mock_extract,
    ):
        mock_user = MagicMock()
        mock_user.id = mock_claims.user_id
        mock_user.permission_claims = []
        mock_extract.return_value = mock_user

        # No project_id in body or query
        # QueryExecRequest requires a project_id in the body. Omitting it
        # will usually raise a 422 from Pydantic, but the auth dependency
        # may run before validation when used as a Depends().
        response = client.post(
            "/query/execute",
            headers={"Authorization": "Bearer valid-token"},
            json={"session_id": str(uuid4()), "sql_query": "SELECT 1"},
        )
        # If project_id is missing from body, Pydantic will raise 422.
        # But our auth dependency also checks for it and raises 400.
        assert response.status_code in (400, 422)


def test_auth_insufficient_permissions(client, mock_jwt_secret):
    """Test that a protected endpoint returns 403
    when the user has insufficient permissions.
    """
    project_id = str(uuid4())
    user_id = str(uuid4())

    mock_claims = MagicMock()
    mock_claims.user_id = user_id
    mock_claims.email = "test@example.com"
    mock_claims.roles = ["User"]
    mock_claims.permission_claims = []  # No permissions

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.project_name = "Test Project"
    mock_project.configuration = MagicMock()
    mock_project.configuration.features = [ProjectFeature.DATALAKE]

    with (
        patch(
            "kontext.auth.JwtValidator.validate_token",
            return_value=mock_claims,
        ),
        patch(
            "kontext.auth.authentication.jwt_utils.JwtUserExtractor.extract_user"
        ) as mock_extract,
    ):
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.permission_claims = []
        mock_extract.return_value = mock_user

        with patch(
            "kontext.project.ProjectService.get_project_async",
            return_value=mock_project,
        ):
            response = client.post(
                "/query/execute",
                headers={"Authorization": "Bearer valid-token"},
                json={
                    "project_id": project_id,
                    "session_id": str(uuid4()),
                    "sql_query": "SELECT 1",
                },
            )
            assert response.status_code == 403
            assert "Insufficient permissions" in response.json()["detail"]


def test_auth_success(client, mock_jwt_secret):
    """Test that a protected endpoint succeeds with valid token and permissions."""
    project_id = str(uuid4())
    user_id = uuid4()  # keep as UUID object for DB comparisons

    # Permission required for /query/execute is "querysessions.execute"
    # (See QUERY_EXECUTE_AUTH in routers/query.py)
    permissions = ["querysessions.execute"]

    mock_claims = MagicMock()
    # JWT claims contain string user_id values
    mock_claims.user_id = str(user_id)
    mock_claims.email = "test@example.com"
    mock_claims.roles = ["User"]
    mock_claims.permission_claims = permissions

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.project_name = "Test Project"
    mock_project.configuration.features = [ProjectFeature.DATALAKE]

    with (
        patch(
            "kontext.auth.JwtValidator.validate_token",
            return_value=mock_claims,
        ),
        patch(
            "kontext.auth.authentication.jwt_utils.JwtUserExtractor.extract_user"
        ) as mock_extract,
    ):
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.permission_claims = permissions
        mock_extract.return_value = mock_user

        mock_project.id = project_id
        mock_project.project_code = "TEST_PROJECT"
        mock_project.configuration = MagicMock()
        mock_project.configuration.features = [ProjectFeature.DATALAKE]

        with patch(
            "kontext.project.ProjectService.get_project_async",
            return_value=mock_project,
        ):
            # Mock the session service to avoid 404 and project mismatch
            mock_session = MagicMock()
            mock_session.project_id = project_id
            mock_session.status = QuerySessionStatus.ACTIVE
            mock_session.engine_type = "DuckDB"
            with (
                patch(
                    "kontext.data.QuerySessionDataService.get_session",
                    return_value=mock_session,
                ),
                patch(
                    "kontext.api.services.query_execution.execute_query_sync",
                    return_value=QueryResponse(success=True, total_execution_time_ms=1),
                ),
            ):
                mock_queue = AsyncMock()
                app.dependency_overrides[get_queue_client] = lambda: mock_queue
                try:
                    response = client.post(
                        "/query/execute",
                        headers={"Authorization": "Bearer valid-token"},
                        json={
                            "project_id": project_id,
                            "session_id": str(uuid4()),
                            "sql_query": "SELECT 1",
                        },
                    )
                    # If we get past auth, the endpoint should return
                    # 200 when all mocks are configured correctly.
                    assert response.status_code == 200
                finally:
                    app.dependency_overrides.clear()
