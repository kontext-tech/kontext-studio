import asyncio
import os
from unittest.mock import patch

from kontext.account import UserProfile, read_profile, write_profile
from kontext.api.services.host_local import (
    HostAuthBootstrapResponse,
    HostAuthMeResponse,
    build_host_auth_bootstrap_response,
    build_host_auth_me_response,
    get_host_config_service,
)
from kontext.data.database import get_engine, get_session_factory
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.runtime.local.config import get_local_site_config
from kontext.schema import SiteConfigResponse


def _clear_db_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def test_build_host_auth_bootstrap_response_for_hosted_mode_uses_canonical_shape():
    hosted_profile = type("HostedProfile", (), {"is_local": False})()

    with (
        patch(
            "kontext.api.services.host_local.get_runtime_profile",
            return_value=hosted_profile,
        ),
        patch.dict(
            os.environ,
            {
                "KONTEXT_PLATFORM_LOGIN_URL": "/platform/login",
                "KONTEXT_PLATFORM_LOGOUT_URL": "/platform/logout",
            },
            clear=True,
        ),
    ):
        response = build_host_auth_bootstrap_response()

    validated = HostAuthBootstrapResponse.model_validate(response.model_dump(by_alias=True))
    assert validated.mode == "hosted"
    assert validated.authenticated is False
    assert validated.login_url == "/platform/login"
    assert validated.logout_url == "/platform/logout"
    assert validated.access_token is None
    assert validated.user is None
    assert validated.project_roles == {}
    assert validated.permissions == []


def test_build_host_auth_me_response_uses_local_service_shape(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {
                "KONTEXT_LOCAL_MODE": "true",
                "ENVIRONMENT": "development",
                "PROJECT_DB_URL": database_url,
            },
            clear=True,
        ),
        patch(
            "kontext.runtime.local.config.get_local_database_url",
            return_value=database_url,
        ),
        patch(
            "kontext.runtime.local.auth.get_local_jwt_secret",
            return_value="test-local-secret",
        ),
    ):
        _clear_db_caches()
        try:
            initialize_local_mode()
            placeholder = read_profile()
            assert placeholder is not None
            write_profile(
                None,
                UserProfile(
                    id=placeholder.id,
                    first_name="Local",
                    last_name="Tester",
                    email="local-tester@example.com",
                ),
            )
            response = asyncio.run(build_host_auth_me_response(credentials=None))
        finally:
            _clear_db_caches()

    validated = HostAuthMeResponse.model_validate(response.model_dump(by_alias=True))
    assert validated.mode == "local"
    assert validated.authenticated is True
    assert validated.user is not None
    assert validated.user.email == "local-tester@example.com"
    assert validated.user.preferred_language_code == "en"
    assert "projects.read" in validated.permissions


def test_build_host_auth_bootstrap_response_requires_explicit_local_setup(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {
                "KONTEXT_LOCAL_MODE": "true",
                "ENVIRONMENT": "development",
                "PROJECT_DB_URL": database_url,
            },
            clear=True,
        ),
        patch(
            "kontext.runtime.local.config.get_local_database_url",
            return_value=database_url,
        ),
    ):
        _clear_db_caches()
        try:
            initialize_local_mode()
            response = build_host_auth_bootstrap_response()
        finally:
            _clear_db_caches()

    validated = HostAuthBootstrapResponse.model_validate(response.model_dump(by_alias=True))
    assert validated.mode == "local"
    assert validated.authenticated is False
    assert validated.login_url is None
    assert validated.access_token is None
    assert validated.user is None


def test_build_host_auth_bootstrap_response_can_auto_auth_default_console_profile(
    tmp_path,
):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {
                "KONTEXT_LOCAL_MODE": "true",
                "KONTEXT_LOCAL_CONSOLE_AUTO_AUTH": "true",
                "ENVIRONMENT": "development",
                "PROJECT_DB_URL": database_url,
            },
            clear=True,
        ),
        patch(
            "kontext.runtime.local.config.get_local_database_url",
            return_value=database_url,
        ),
        patch(
            "kontext.runtime.local.auth.get_local_jwt_secret",
            return_value="test-local-secret",
        ),
    ):
        _clear_db_caches()
        try:
            initialize_local_mode()
            response = build_host_auth_bootstrap_response()
        finally:
            _clear_db_caches()

    validated = HostAuthBootstrapResponse.model_validate(response.model_dump(by_alias=True))
    assert validated.mode == "local"
    assert validated.authenticated is True
    assert validated.access_token is not None
    assert validated.user is not None
    assert validated.user.email == "local@kontext.local"


def test_get_host_config_service_returns_site_config_response():
    expected = get_local_site_config()
    local_profile = type(
        "LocalProfile",
        (),
        {"is_local": True, "get_site_config": lambda self: expected},
    )()

    with (
        patch(
            "kontext.api.services.host_local.get_runtime_profile",
            return_value=local_profile,
        ),
    ):
        response = get_host_config_service()

    validated = SiteConfigResponse.model_validate(response.model_dump(by_alias=True))
    assert validated.default_project_code == expected.default_project_code
    assert validated.features == expected.features
    assert validated.setup_url == expected.setup_url
