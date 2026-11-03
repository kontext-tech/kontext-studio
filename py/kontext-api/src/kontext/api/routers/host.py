"""Kontext host-api endpoints for local and hosted runtimes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from kontext.account import UserProfile
from kontext.project import (
    get_filtered_projects_service,
    get_project_by_code_service,
)
from kontext.schema import (
    CultureInfoModel,
    PaginatedListOfProjectModel,
    ProjectModel,
    SiteConfigResponse,
)

from ..dependencies import (
    FILTER_QUERY,
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_CODE_PATH,
)
from ..dependencies.local_auth import (
    get_current_user,
    set_local_session_cookie,
)
from ..dependencies.local_launch import require_local_launch_token
from ..services.culture_local import get_cultures_service
from ..services.host_local import (
    HostAuthBootstrapResponse,
    HostAuthMeResponse,
    build_host_auth_bootstrap_response,
    build_host_auth_me_response,
    ensure_local_project_state_service,
    get_host_config_service,
)

router = APIRouter(prefix="/host", tags=["Host"])

_LAUNCH_DEP = Depends(require_local_launch_token)
_USER_DEP = Depends(get_current_user)


@router.get("/auth/bootstrap", response_model=HostAuthBootstrapResponse)
def bootstrap(
    response: Response,
    _: None = _LAUNCH_DEP,
) -> HostAuthBootstrapResponse:
    payload = build_host_auth_bootstrap_response()
    set_local_session_cookie(response, payload.access_token)
    return payload


@router.get("/auth/me", response_model=HostAuthMeResponse)
def me(_user: UserProfile = _USER_DEP) -> HostAuthMeResponse:
    return build_host_auth_me_response(_user)


@router.post("/auth/refresh", response_model=HostAuthBootstrapResponse)
def refresh(
    response: Response,
    _: None = _LAUNCH_DEP,
) -> HostAuthBootstrapResponse:
    payload = build_host_auth_bootstrap_response()
    set_local_session_cookie(response, payload.access_token)
    return payload


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> None:
    set_local_session_cookie(response, None)


@router.get("/config", response_model=SiteConfigResponse)
def config() -> SiteConfigResponse:
    return get_host_config_service()


@router.get("/projects", response_model=PaginatedListOfProjectModel)
def projects(
    page_index: PAGE_INDEX_QUERY = 1,
    page_size: PAGE_SIZE_QUERY = 20,
    filter: FILTER_QUERY = None,
    _user: UserProfile = _USER_DEP,
) -> PaginatedListOfProjectModel:
    ensure_local_project_state_service()
    return get_filtered_projects_service(
        page_index=page_index,
        page_size=page_size,
        filter_string=filter,
    )


@router.get("/projects/code/{projectCode}", response_model=ProjectModel)
def project_by_code(
    project_code: Annotated[str, PROJECT_CODE_PATH],
    _user: UserProfile = _USER_DEP,
) -> ProjectModel:
    ensure_local_project_state_service()
    return get_project_by_code_service(project_code)


@router.get("/culture", response_model=list[CultureInfoModel])
def culture() -> list[CultureInfoModel]:
    return get_cultures_service()
