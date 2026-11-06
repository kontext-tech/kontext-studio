import os
import sqlite3
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from kontext.account import _LocalProfileDB, read_profile
from kontext.api.main import create_app
from kontext.api.services.host_local import (
    HostAuthBootstrapResponse,
    HostAuthMeResponse,
)
from kontext.common.config import get_config
from kontext.data.database import (
    get_engine,
    get_session_factory,
    get_sync_db_session,
)
from kontext.data.models import ChatSession, Project, ProjectFile
from kontext.runtime.local.bootstrap import initialize_local_mode
from kontext.runtime.local.config import (
    LOCAL_PROJECT_ACCESS_LEVEL,
    LOCAL_PROJECT_CODE,
    configure_local_runtime,
    get_default_local_project_configuration,
    get_local_default_user_email,
    get_local_site_config,
)
from kontext.schema import (
    CultureInfoModel,
    FileFormatType,
    PaginatedListOfProjectModel,
    ProjectModel,
    PythonEnvironmentInfo,
    PythonPackageSource,
    SiteConfigResponse,
)


def _fake_python_environment_info(*, initialized: bool) -> PythonEnvironmentInfo:
    """A stand-in for the managed Python environment without touching disk."""
    return PythonEnvironmentInfo(
        available=True,
        initialized=initialized,
        display_label="Managed CPython Local (ml-default)",
        backend="managed_cpython_local",
        runtime_profile="ml-default",
        python_version="3.12",
        package_source=PythonPackageSource.CONFIGURED,
        packages=[],
    )


def _is_timezone_aware_iso_datetime(value: str | None) -> bool:
    if not value:
        return False

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.tzinfo is not None


TEST_LAUNCH_TOKEN = "test-launch-token"


def _launch_headers() -> dict[str, str]:
    return {"X-Kontext-Launch-Token": TEST_LAUNCH_TOKEN}


def _clear_db_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def _get_local_access_token(client: TestClient, email: str = "local-tester@example.com") -> str:
    bootstrap_response = client.get("/host/auth/bootstrap", headers=_launch_headers())
    bootstrap_payload = bootstrap_response.json()
    if bootstrap_payload.get("accessToken"):
        return bootstrap_payload["accessToken"]["accessToken"]

    setup_response = client.post(
        "/setup",
        json={
            "firstName": "Local",
            "lastName": "Tester",
            "email": email,
        },
        headers=_launch_headers(),
    )
    assert setup_response.status_code == 200
    return setup_response.json()["accessToken"]


def test_get_local_site_config_uses_local_features():
    config = get_local_site_config()

    assert config.default_project_code == "local"
    assert "local-mode" in (config.features or [])
    # Local mode mounts the model-connection and python-environment routers, so
    # it advertises them; the frontend and backend agree on the same set.
    assert "model-connections" in (config.features or [])
    assert "python-environment" in (config.features or [])
    assert config.setup_url is None


def test_default_local_project_configuration_has_expected_defaults():
    config = get_default_local_project_configuration()

    assert config.default_query_engine is not None
    assert config.default_query_engine.value == "DuckDB"
    assert config.features is not None
    assert len(config.allowed_file_types or []) > 0


def test_configure_local_runtime_provides_settings_and_processes_env():
    """The env-mutation contract is now minimal: settings own in-process
    values; only the cross-process pair is seeded into the environment."""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch(
            "kontext.runtime.local.auth.get_local_jwt_secret",
            return_value="test-local-secret",
        ),
    ):
        db_url = configure_local_runtime(log_level="debug", log_format="json")
        assert db_url.endswith("/.kontext/kontext.db")
        # Cross-process contract: spawned worker/runner processes inherit these.
        assert os.environ["KONTEXT_LOCAL_MODE"] == "true"
        assert os.environ["PROJECT_DB_URL"] == db_url
        # In-process values live in settings, not the environment.
        assert "JWT_SECRET_KEY" not in os.environ
        assert "JWT_ISSUER" not in os.environ
        assert "JWT_AUDIENCE" not in os.environ
        assert "LOG_LEVEL" not in os.environ
        assert "LOG_FORMAT" not in os.environ

        settings = get_config()
        assert settings.local_mode is True
        assert settings.project_db_url == db_url
        assert settings.jwt_secret_key == "test-local-secret"
        assert settings.jwt_issuer == "kontext-local"
        assert settings.jwt_audience == "kontext-platform"
        assert settings.log_level == "debug"
        assert settings.log_format == "json"
        assert LOCAL_PROJECT_ACCESS_LEVEL.value == "Private"


def test_configure_local_runtime_respects_preexisting_settings():
    """Explicit env values keep priority over the local defaults."""
    with (
        patch.dict(
            os.environ,
            {
                "JWT_ISSUER": "custom-issuer",
                "JWT_AUDIENCE": "custom-audience",
                "LOG_LEVEL": "warning",
            },
            clear=True,
        ),
        patch(
            "kontext.runtime.local.auth.get_local_jwt_secret",
            return_value="test-local-secret",
        ),
    ):
        configure_local_runtime()
        settings = get_config()
        assert settings.jwt_issuer == "custom-issuer"
        assert settings.jwt_audience == "custom-audience"
        assert settings.log_level == "warning"
        assert settings.jwt_secret_key == "test-local-secret"


def test_initialize_local_mode_seeds_local_admin_user(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(os.environ, {}, clear=True),
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
            profile = read_profile(email=get_local_default_user_email())
        finally:
            _clear_db_caches()

    assert profile is not None
    assert profile.email == get_local_default_user_email()
    assert profile.preferred_language_code == "en"


def test_local_mode_does_not_expose_legacy_auth_routes(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                login_response = client.post("/auth/login", json={})
                register_response = client.post("/auth/register", json={})
                forgot_response = client.post("/auth/forgot-password", json={})
                reset_response = client.post("/auth/reset-password", json={})
        finally:
            _clear_db_caches()

    assert login_response.status_code == 404
    assert register_response.status_code == 404
    assert forgot_response.status_code == 404
    assert reset_response.status_code == 404


def test_local_mode_exposes_runtime_account_endpoints_only(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            # Never create a real venv or pip-install the ML stack in tests:
            # it is slow, network-bound, and leaves child processes behind.
            with (
                patch(
                    "kontext.api.routers.python_environment.get_managed_python_environment_info",
                    return_value=_fake_python_environment_info(initialized=False),
                ),
                patch(
                    "kontext.api.routers.python_environment.prepare_managed_python_environment",
                    return_value=_fake_python_environment_info(initialized=True),
                ),
                TestClient(app) as client,
            ):
                access_token = _get_local_access_token(client)
                credentials_response = client.post(
                    "/account/credentials",
                    json={},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                python_get_response = client.get(
                    "/account/python-environment",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                python_prepare_response = client.post(
                    "/account/python-environment/prepare",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        finally:
            _clear_db_caches()

    assert credentials_response.status_code == 404
    assert python_get_response.status_code == 200
    assert python_get_response.json()["available"] is True
    assert python_get_response.json()["runtimeProfile"] == "ml-default"
    assert python_prepare_response.status_code == 200
    assert python_prepare_response.json()["available"] is True
    assert python_prepare_response.json()["initialized"] is True


def test_default_local_admin_owns_default_project_in_account_info(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                access_token = _get_local_access_token(client)

                with get_session_factory()() as session:
                    default_project = session.execute(
                        select(Project).where(
                            Project.project_code == LOCAL_PROJECT_CODE,
                            Project.is_deleted.is_(False),
                        )
                    ).scalar_one()

                account_response = client.get(
                    "/account/info",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        finally:
            _clear_db_caches()

    assert account_response.status_code == 200
    assert account_response.json()["id"] == str(default_project.owner_id)
    assert "projects.read" in account_response.json()["permissionClaims"]
    assert account_response.json()["projectRoles"][str(default_project.id)] == ["owner"]


def test_host_auth_bootstrap_and_me_use_local_dev_identity(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                setup_response = client.post(
                    "/setup",
                    json={
                        "firstName": "Local",
                        "lastName": "Tester",
                        "email": "local-tester@example.com",
                    },
                    headers=_launch_headers(),
                )
                bootstrap_response = client.get("/host/auth/bootstrap", headers=_launch_headers())
                bootstrap_payload = bootstrap_response.json()
                access_token = bootstrap_payload["accessToken"]["accessToken"]

                me_response = client.get(
                    "/host/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        finally:
            _clear_db_caches()

    assert setup_response.status_code == 200
    assert bootstrap_response.status_code == 200
    bootstrap_contract = HostAuthBootstrapResponse.model_validate(bootstrap_payload)
    assert bootstrap_contract.mode == "local"
    assert bootstrap_contract.authenticated is True
    assert bootstrap_contract.login_url is None
    assert bootstrap_contract.user is not None
    assert bootstrap_contract.user.email == "local-tester@example.com"
    assert bootstrap_contract.access_token is not None
    assert bootstrap_contract.access_token.token_type == "Bearer"

    assert me_response.status_code == 200
    me_payload = me_response.json()
    me_contract = HostAuthMeResponse.model_validate(me_payload)
    assert me_contract.mode == "local"
    assert me_contract.authenticated is True
    assert me_contract.user is not None
    assert me_contract.user.email == "local-tester@example.com"


def test_host_config_projects_and_culture_endpoints(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                access_token = _get_local_access_token(client)
                auth_headers = {"Authorization": f"Bearer {access_token}"}
                config_response = client.get("/host/config")
                projects_response = client.get("/host/projects", headers=auth_headers)
                cookie_projects_response = client.get("/host/projects")
                project_response = client.get(
                    f"/host/projects/code/{LOCAL_PROJECT_CODE}",
                    headers=auth_headers,
                )
                culture_response = client.get("/host/culture")
        finally:
            _clear_db_caches()

    assert config_response.status_code == 200
    config_contract = SiteConfigResponse.model_validate(config_response.json())
    assert config_contract.default_project_code == LOCAL_PROJECT_CODE

    assert projects_response.status_code == 200
    assert cookie_projects_response.status_code == 200
    projects_payload = PaginatedListOfProjectModel.model_validate(projects_response.json())
    assert any(project.project_code == LOCAL_PROJECT_CODE for project in projects_payload.items)

    assert project_response.status_code == 200
    project_contract = ProjectModel.model_validate(project_response.json())
    assert project_contract.project_code == LOCAL_PROJECT_CODE

    assert culture_response.status_code == 200
    culture_contracts = [
        CultureInfoModel.model_validate(culture) for culture in culture_response.json()
    ]
    assert [culture.code for culture in culture_contracts] == ["en", "zh"]


def test_setup_succeeds_with_legacy_local_profile_schema(tmp_path):
    db_path = tmp_path / "legacy-kontext.db"
    database_url = f"sqlite:///{db_path}"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE local_profile (
                id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT,
                email TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.commit()
    finally:
        conn.close()

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                response = client.post(
                    "/setup",
                    json={
                        "firstName": "Legacy",
                        "lastName": "User",
                        "email": "legacy-user@example.com",
                    },
                    headers={**_launch_headers(), "Origin": "http://localhost:8002"},
                )
        finally:
            _clear_db_caches()

    assert response.status_code == 200


def test_legacy_profile_without_password_hash_can_login_after_bootstrap(tmp_path):
    db_path = tmp_path / "legacy-login.db"
    database_url = f"sqlite:///{db_path}"

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE local_profile (
                id TEXT PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT,
                email TEXT NOT NULL UNIQUE,
                preferred_language_code TEXT NOT NULL DEFAULT 'en-US',
                email_confirmed BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            INSERT INTO local_profile (
                id,
                first_name,
                last_name,
                email,
                preferred_language_code,
                email_confirmed
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "00000000-0000-0000-0000-000000000123",
                "Legacy",
                "User",
                "legacy-user@example.com",
                "en-US",
                1,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                access_token = _get_local_access_token(client, email="legacy-user@example.com")
                me_response = client.get(
                    "/host/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        finally:
            _clear_db_caches()

    assert me_response.status_code == 200
    assert me_response.json()["user"]["preferredLanguageCode"] == "en"


def test_project_update_returns_timezone_aware_datetimes_in_local_mode(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                access_token = _get_local_access_token(client)

                with get_session_factory()() as session:
                    default_project = session.execute(
                        select(Project).where(
                            Project.project_code == LOCAL_PROJECT_CODE,
                            Project.is_deleted.is_(False),
                        )
                    ).scalar_one()

                update_response = client.put(
                    f"/project/{default_project.id}",
                    json={
                        "id": str(default_project.id),
                        "projectName": "Updated Local Project",
                        "projectDescription": "Updated from local-mode test",
                    },
                    headers={"Authorization": f"Bearer {access_token}"},
                )

                filtered_response = client.get("/project/filtered")
        finally:
            _clear_db_caches()

    assert update_response.status_code == 200
    assert filtered_response.status_code == 200

    updated_project = update_response.json()
    assert updated_project["projectName"] == "Updated Local Project"
    assert _is_timezone_aware_iso_datetime(updated_project["dateCreated"])
    assert _is_timezone_aware_iso_datetime(updated_project["dateModified"])

    project_items = filtered_response.json()["items"]
    listed_project = next(item for item in project_items if item["id"] == str(default_project.id))
    assert _is_timezone_aware_iso_datetime(listed_project["dateCreated"])
    assert _is_timezone_aware_iso_datetime(listed_project["dateModified"])


def test_local_setup_endpoints_create_profile_and_enable_host_bootstrap(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                status_response = client.get("/setup/status")
                bootstrap_before = client.get("/host/auth/bootstrap", headers=_launch_headers())
                setup_response = client.post(
                    "/setup",
                    json={
                        "firstName": "Local",
                        "lastName": "Tester",
                        "email": "local-tester@example.com",
                    },
                    headers=_launch_headers(),
                )
                bootstrap_after = client.get("/host/auth/bootstrap", headers=_launch_headers())
        finally:
            _clear_db_caches()

    assert status_response.status_code == 200
    assert status_response.json() == {"isSetupComplete": False}
    assert bootstrap_before.status_code == 200
    assert bootstrap_before.json()["authenticated"] is False
    assert bootstrap_before.json()["loginUrl"] is None
    assert bootstrap_before.json()["user"] is None
    assert bootstrap_before.json()["accessToken"] is None
    assert setup_response.status_code == 200
    assert "accessToken" in setup_response.json()
    assert bootstrap_after.status_code == 200
    assert bootstrap_after.json()["authenticated"] is True
    assert bootstrap_after.json()["user"]["email"] == "local-tester@example.com"


def test_local_setup_rejects_seeded_placeholder_identity(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                setup_response = client.post(
                    "/setup",
                    json={
                        "firstName": "Local",
                        "lastName": "Admin",
                        "email": get_local_default_user_email(),
                    },
                    headers=_launch_headers(),
                )
                status_response = client.get("/setup/status")
                bootstrap_response = client.get("/host/auth/bootstrap", headers=_launch_headers())
        finally:
            _clear_db_caches()

    assert setup_response.status_code == 409
    assert setup_response.json()["detail"] == (
        "Choose a non-default local profile to complete setup."
    )
    assert status_response.status_code == 200
    assert status_response.json() == {"isSetupComplete": False}
    assert bootstrap_response.status_code == 200
    assert bootstrap_response.json()["authenticated"] is False


def test_local_setup_does_not_overwrite_existing_workspace_content(tmp_path):
    """A late /setup call must not repurpose a profile once real content exists."""
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"
    existing_email = "owner@example.com"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                # First-time setup succeeds on a pristine workspace.
                first_setup = client.post(
                    "/setup",
                    json={
                        "firstName": "Real",
                        "lastName": "Owner",
                        "email": existing_email,
                    },
                    headers=_launch_headers(),
                )
                assert first_setup.status_code == 200

                # Simulate real usage before anyone runs setup again.
                with get_session_factory()() as session:
                    default_project = session.execute(
                        select(Project).where(
                            Project.project_code == LOCAL_PROJECT_CODE,
                            Project.is_deleted.is_(False),
                        )
                    ).scalar_one()
                with get_sync_db_session() as session:
                    session.add(
                        ChatSession(
                            id=uuid4(),
                            project_id=default_project.id,
                            session_name="Existing chat",
                            created_by=str(default_project.owner_id),
                            owner_id=default_project.owner_id,
                            is_deleted=False,
                        )
                    )
                    session.commit()

                # Reset the profile back to the seeded placeholder to model a
                # workspace whose placeholder identity is still present.
                with get_sync_db_session() as session:
                    profile = session.execute(select(_LocalProfileDB)).scalar_one()
                    profile.first_name = "Local"
                    profile.last_name = "Admin"
                    profile.email = get_local_default_user_email()
                    session.commit()

                second_setup = client.post(
                    "/setup",
                    json={
                        "firstName": "Attacker",
                        "lastName": "User",
                        "email": "attacker@example.com",
                    },
                    headers=_launch_headers(),
                )

                with get_sync_db_session() as session:
                    profile_after = session.execute(select(_LocalProfileDB)).scalar_one()
        finally:
            _clear_db_caches()

    assert second_setup.status_code == 409
    assert "already contains data" in second_setup.json()["detail"]
    # The profile was not repurposed.
    assert profile_after.email == get_local_default_user_email()


def test_setup_status_is_complete_when_workspace_has_content(tmp_path):
    """A used workspace (even with the placeholder profile) must not offer setup."""
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                with get_session_factory()() as session:
                    default_project = session.execute(
                        select(Project).where(
                            Project.project_code == LOCAL_PROJECT_CODE,
                            Project.is_deleted.is_(False),
                        )
                    ).scalar_one()
                with get_sync_db_session() as session:
                    session.add(
                        ChatSession(
                            id=uuid4(),
                            project_id=default_project.id,
                            session_name="Existing chat",
                            created_by=str(default_project.owner_id),
                            owner_id=default_project.owner_id,
                            is_deleted=False,
                        )
                    )
                    session.commit()

                status_response = client.get("/setup/status")
                bootstrap_response = client.get("/host/auth/bootstrap", headers=_launch_headers())
        finally:
            _clear_db_caches()

    assert status_response.status_code == 200
    assert status_response.json() == {"isSetupComplete": True}
    # A used workspace must remain usable even when its owner never renamed
    # the seeded placeholder profile; otherwise login and setup page-loop.
    assert bootstrap_response.status_code == 200
    bootstrap_payload = bootstrap_response.json()
    assert bootstrap_payload["authenticated"] is True
    assert bootstrap_payload["accessToken"] is not None
    assert bootstrap_payload["user"]["email"] == "local@kontext.local"


def test_local_file_list_normalizes_naive_created_timestamps(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"

    with (
        patch.dict(
            os.environ,
            {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
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
            app = create_app()
            with TestClient(app) as client:
                access_token = _get_local_access_token(client)

                with get_session_factory()() as session:
                    default_project = session.execute(
                        select(Project).where(
                            Project.project_code == LOCAL_PROJECT_CODE,
                            Project.is_deleted.is_(False),
                        )
                    ).scalar_one()

                with get_sync_db_session() as session:
                    session.add(
                        ProjectFile(
                            id=uuid4(),
                            name="local-test.csv",
                            uri="file:///tmp/local-test.csv",
                            file_type=FileFormatType.CSV.value,
                            content_type="text/csv",
                            size=128,
                            project_id=default_project.id,
                            owner_id=default_project.owner_id,
                            date_created=datetime(2026, 1, 2, 3, 4, 5),
                            is_deleted=False,
                        )
                    )
                    session.commit()

                files_response = client.get(
                    "/file",
                    params={"projectId": str(default_project.id)},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        finally:
            _clear_db_caches()

    assert files_response.status_code == 200

    listed_file = next(
        item for item in files_response.json()["items"] if item["name"] == "local-test.csv"
    )
    assert _is_timezone_aware_iso_datetime(listed_file["dateCreated"])
