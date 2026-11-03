"""Unit tests for the transport-to-domain mapping helpers."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from kontext.api.dependencies import AccessScope, AuthContext
from kontext.api.transport_adapters import (
    build_chat_access_context,
    build_query_access_context,
    domain_error_to_http,
)
from kontext.schema import (
    AccessLevel,
    ProjectConfiguration,
    ProjectModel,
    QueryEngineType,
    QuerySessionModel,
    QuerySessionStatus,
    UserType,
    UserWithRolesModel,
)

PROJECT_ID = uuid4()
USER_ID = uuid4()


def _project() -> ProjectModel:
    return ProjectModel(
        id=str(PROJECT_ID),
        project_name="p",
        project_code="p",
        access_level=AccessLevel.PRIVATE,
        configuration=ProjectConfiguration(
            allowed_file_types=[],
            max_file_bytes_size=1,
            total_storage_allocation_bytes=1,
            features=[],
        ),
        owner_id=str(USER_ID),
    )


def _user() -> UserWithRolesModel:
    return UserWithRolesModel(
        id=str(USER_ID),
        first_name="Test",
        last_name="User",
        user_type=UserType.USER,
    )


def _auth_context(*, with_project: bool = True, with_user: bool = True) -> AuthContext:
    return AuthContext(
        user=_user() if with_user else None,
        project=_project() if with_project else None,
    )


def test_build_query_access_context_maps_project_scope() -> None:
    context = build_query_access_context(_auth_context())

    assert context.project_id == PROJECT_ID
    assert context.user_id == USER_ID
    assert context.project_scope is True  # PROJECT scope is project-wide
    assert context.effective_owner_id is None


def test_build_query_access_context_marks_owner_scope() -> None:
    context = build_query_access_context(
        AuthContext(user=_user(), project=_project(), scope=AccessScope.OWNER)
    )

    assert context.project_scope is False
    assert context.effective_owner_id == USER_ID


def test_build_query_access_context_carries_resource() -> None:
    resource = uuid4()

    context = build_query_access_context(
        _auth_context(),
        resource=QuerySessionModel(
            id=str(resource),
            session_name="s",
            project_id=str(PROJECT_ID),
            owner_id=str(USER_ID),
            status=QuerySessionStatus.ACTIVE,
            engine_type=QueryEngineType.DUCKDB,
        ),
    )

    assert context.resource is not None
    assert context.resource.id == str(resource)


def test_build_chat_access_context_maps_user_and_resource() -> None:
    context = build_chat_access_context(_auth_context())

    assert context.project_id == PROJECT_ID
    assert context.user_id == USER_ID
    assert context.project is not None
    assert context.auth_manager is None


@pytest.mark.parametrize(
    ("builder_name",),
    [("build_query_access_context",), ("build_chat_access_context",)],
)
def test_builders_require_project_context(builder_name: str) -> None:
    builder = {
        "build_query_access_context": build_query_access_context,
        "build_chat_access_context": build_chat_access_context,
    }[builder_name]

    with pytest.raises(HTTPException) as exc_info:
        builder(_auth_context(with_project=False))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Project context required"


def test_domain_error_to_http_translates_status_and_detail() -> None:
    exc = SimpleNamespace(status_code=409, detail="conflict")

    translated = domain_error_to_http(exc)

    assert translated.status_code == 409
    assert translated.detail == "conflict"
