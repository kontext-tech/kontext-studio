"""
Unit tests for authentication dependencies in kontext-api.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from kontext.api.dependencies.auth import (
    _all_local_permissions,
    extract_project_id,
    get_auth_context,
)
from kontext.auth import (
    ChatSessionPermissions,
    EventPermissions,
    FilePermissions,
    JobPermissions,
    JwtValidationError,
    ProjectPermissions,
    QuerySessionPermissions,
)


@pytest.mark.asyncio
async def test_get_auth_context_missing_secret():
    """Test that authentication fails if JWT_SECRET_KEY is missing."""
    request = MagicMock(spec=Request)
    request.headers = {"Authorization": "Bearer some-token"}

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(HTTPException) as excinfo:
            await get_auth_context(request)

        assert excinfo.value.status_code == 500
        assert "misconfigured" in excinfo.value.detail


@pytest.mark.asyncio
async def test_get_auth_context_missing_token():
    """Test that authentication fails if Authorization header is missing."""
    request = MagicMock(spec=Request)
    request.headers = {}

    with patch.dict(os.environ, {"JWT_SECRET_KEY": "a" * 32}, clear=True):
        with pytest.raises(HTTPException) as excinfo:
            await get_auth_context(request)

        assert excinfo.value.status_code == 401
        assert "provide a valid Bearer token" in excinfo.value.detail


@pytest.mark.asyncio
async def test_get_auth_context_invalid_token():
    """Test that authentication fails if token is invalid."""
    request = MagicMock(spec=Request)
    request.headers = {"Authorization": "Bearer invalid-token"}

    with (
        patch.dict(os.environ, {"JWT_SECRET_KEY": "a" * 32}, clear=True),
        patch("kontext.auth.JwtValidator.validate_token") as mock_validate,
    ):
        mock_validate.side_effect = JwtValidationError("Invalid signature")

        # get_auth_context now lets JwtValidationError propagate so the app-level
        # exception handler can return a consistent RFC7807 response.
        with pytest.raises(JwtValidationError) as excinfo:
            await get_auth_context(request)

        assert "Invalid signature" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_auth_context_valid_token():
    """Test that authentication succeeds with a valid token."""
    request = MagicMock(spec=Request)
    request.headers = {"Authorization": "Bearer valid-token"}

    # Mock claims
    mock_claims = MagicMock()
    mock_claims.user_id = "user-123"
    mock_claims.email = "user@example.com"
    mock_claims.display_name = "John Doe"
    mock_claims.user_type = "User"
    mock_claims.roles = ["Admin"]
    mock_claims.project_roles = {}
    mock_claims.permission_claims = ["projects.read"]

    with (
        patch.dict(os.environ, {"JWT_SECRET_KEY": "a" * 32}, clear=True),
        patch("kontext.auth.JwtValidator.validate_token", return_value=mock_claims),
        patch(
            "kontext.auth.authentication.jwt_utils.JwtUserExtractor.extract_user"
        ) as mock_extract,
    ):
        # We also need to mock JwtUserExtractor.extract_user
        # to avoid pydantic validation issues in tests
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_extract.return_value = mock_user

        auth_context = await get_auth_context(request)

        assert auth_context.user is not None
        assert auth_context.user.id == "user-123"
        assert auth_context.auth_manager is not None


def test_all_local_permissions_match_canonical_permission_constants():
    """Local mode should grant the same canonical permission names.

    This keeps local-mode auth aligned with the rest of the platform.
    """
    assert set(_all_local_permissions()) == {
        ChatSessionPermissions.CREATE,
        ChatSessionPermissions.READ,
        ChatSessionPermissions.UPDATE,
        ChatSessionPermissions.DELETE,
        QuerySessionPermissions.CREATE,
        QuerySessionPermissions.READ,
        QuerySessionPermissions.UPDATE,
        QuerySessionPermissions.DELETE,
        QuerySessionPermissions.EXECUTE,
        FilePermissions.CREATE,
        FilePermissions.READ,
        FilePermissions.UPDATE,
        FilePermissions.DELETE,
        JobPermissions.CREATE,
        JobPermissions.READ,
        JobPermissions.UPDATE,
        JobPermissions.DELETE,
        JobPermissions.EXECUTE,
        EventPermissions.CREATE,
        EventPermissions.READ,
        ProjectPermissions.READ,
        ProjectPermissions.UPDATE,
    }


@pytest.mark.asyncio
async def test_extract_project_id_from_request_body():
    """Request bodies should expose project.id for project-scoped authorization."""
    request = MagicMock(spec=Request)
    request.path_params = {}
    request.query_params = {}
    request.headers = {"content-type": "application/json"}
    request.cookies = {}
    request.method = "POST"
    request.form.side_effect = RuntimeError("not form data")
    request.json.return_value = {"project": {"id": "05de2fb9-085d-4315-bc88-08dea28ea66c"}}

    project_id = await extract_project_id(request)

    assert str(project_id) == "05de2fb9-085d-4315-bc88-08dea28ea66c"
