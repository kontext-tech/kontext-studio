"""Tests for site-feature (deployment capability) gating.

Covers the server-side contract: the active runtime profile decides which
capability-gated routers are mounted, and ``require_site_feature`` refuses
requests when a feature is disabled.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from kontext.api.dependencies import require_site_feature
from kontext.api.main import create_app
from kontext.api.testing import iter_effective_api_routes
from kontext.common import LOCAL_DEFAULT_SITE_FEATURES, SiteFeature
from kontext.data.database import get_engine, get_session_factory
from kontext.runtime.profiles import (
    DISABLED_SITE_FEATURES_ENV_VAR,
    SITE_FEATURES_ENV_VAR,
    get_local_runtime_profile,
)

TEST_LAUNCH_TOKEN = "test-launch-token"


def _launch_headers() -> dict[str, str]:
    return {"X-Kontext-Launch-Token": TEST_LAUNCH_TOKEN}


def _clear_db_caches() -> None:
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@contextmanager
def _local_app(tmp_path, extra_env: dict[str, str] | None = None):
    database_url = f"sqlite:///{tmp_path / 'kontext.db'}"
    env = {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development", **(extra_env or {})}

    with (
        patch.dict(os.environ, env, clear=True),
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
            yield create_app()
        finally:
            _clear_db_caches()


def _get_access_token(client: TestClient) -> str:
    bootstrap = client.get("/host/auth/bootstrap", headers=_launch_headers()).json()
    if bootstrap.get("accessToken"):
        return bootstrap["accessToken"]["accessToken"]

    setup_response = client.post(
        "/setup",
        json={
            "firstName": "Local",
            "lastName": "Tester",
            "email": "feature-gating@example.com",
        },
        headers=_launch_headers(),
    )
    assert setup_response.status_code == 200
    return setup_response.json()["accessToken"]


def test_local_profile_advertises_local_default_features():
    profile = get_local_runtime_profile()

    assert profile.effective_site_features() == LOCAL_DEFAULT_SITE_FEATURES
    assert profile.has_feature(SiteFeature.LOCAL_MODE)
    assert profile.has_feature(SiteFeature.MODEL_CONNECTIONS)
    assert profile.has_feature(SiteFeature.PYTHON_ENVIRONMENT)


def test_site_config_advertises_effective_features():
    profile = get_local_runtime_profile()
    config = profile.get_site_config()

    assert set(config.features or []) == {feature.value for feature in LOCAL_DEFAULT_SITE_FEATURES}


def test_env_can_disable_a_feature():
    with patch.dict(
        os.environ,
        {DISABLED_SITE_FEATURES_ENV_VAR: SiteFeature.MODEL_CONNECTIONS.value},
    ):
        profile = get_local_runtime_profile()

        assert not profile.has_feature(SiteFeature.MODEL_CONNECTIONS)
        assert profile.has_feature(SiteFeature.PYTHON_ENVIRONMENT)


def test_env_can_enable_a_feature():
    with patch.dict(
        os.environ,
        {SITE_FEATURES_ENV_VAR: SiteFeature.NOTIFICATIONS.value},
    ):
        profile = get_local_runtime_profile()

        assert profile.has_feature(SiteFeature.NOTIFICATIONS)


def test_disable_wins_over_enable():
    with patch.dict(
        os.environ,
        {
            SITE_FEATURES_ENV_VAR: SiteFeature.MODEL_CONNECTIONS.value,
            DISABLED_SITE_FEATURES_ENV_VAR: SiteFeature.MODEL_CONNECTIONS.value,
        },
    ):
        profile = get_local_runtime_profile()

        assert not profile.has_feature(SiteFeature.MODEL_CONNECTIONS)


def test_unknown_feature_tokens_are_ignored():
    with patch.dict(
        os.environ,
        {SITE_FEATURES_ENV_VAR: "not-a-real-feature, model-connections"},
    ):
        profile = get_local_runtime_profile()

        assert profile.has_feature(SiteFeature.MODEL_CONNECTIONS)


# ── require_site_feature dependency ──────────────────────────────────────────


def _app_with_gated_route(features: list[SiteFeature], *, require_all: bool = False) -> FastAPI:
    app = FastAPI()

    @app.get("/gated")
    async def gated(_=require_site_feature(*features, require_all=require_all)) -> dict[str, bool]:
        return {"ok": True}

    return app


def test_require_site_feature_allows_when_enabled():
    app = _app_with_gated_route([SiteFeature.LOCAL_MODE])

    with patch.dict(os.environ, {"KONTEXT_LOCAL_MODE": "true"}, clear=True):
        response = TestClient(app).get("/gated")

    assert response.status_code == 200


def test_require_site_feature_returns_404_when_disabled():
    app = _app_with_gated_route([SiteFeature.MODEL_CONNECTIONS])

    with patch.dict(
        os.environ,
        {
            "KONTEXT_LOCAL_MODE": "true",
            DISABLED_SITE_FEATURES_ENV_VAR: SiteFeature.MODEL_CONNECTIONS.value,
        },
        clear=True,
    ):
        response = TestClient(app).get("/gated")

    assert response.status_code == 404


def test_require_site_feature_any_of_semantics():
    app = _app_with_gated_route([SiteFeature.MODEL_CONNECTIONS, SiteFeature.PYTHON_ENVIRONMENT])

    with patch.dict(
        os.environ,
        {
            "KONTEXT_LOCAL_MODE": "true",
            DISABLED_SITE_FEATURES_ENV_VAR: SiteFeature.MODEL_CONNECTIONS.value,
        },
        clear=True,
    ):
        response = TestClient(app).get("/gated")

    # Python environment is still enabled, so the route is reachable.
    assert response.status_code == 200


def test_require_site_feature_all_of_semantics():
    app = _app_with_gated_route(
        [SiteFeature.MODEL_CONNECTIONS, SiteFeature.PYTHON_ENVIRONMENT],
        require_all=True,
    )

    with patch.dict(
        os.environ,
        {
            "KONTEXT_LOCAL_MODE": "true",
            DISABLED_SITE_FEATURES_ENV_VAR: SiteFeature.MODEL_CONNECTIONS.value,
        },
        clear=True,
    ):
        response = TestClient(app).get("/gated")

    assert response.status_code == 404


# ── Router mounting ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/model-connections",
        "/account/python-environment",
    ],
)
def test_gated_routes_are_mounted_when_feature_enabled(tmp_path, path):
    with _local_app(tmp_path) as app:
        paths = {route.path for route in iter_effective_api_routes(app)}

    assert path in paths


@pytest.mark.parametrize(
    ("feature", "path"),
    [
        (SiteFeature.MODEL_CONNECTIONS, "/model-connections"),
        (SiteFeature.PYTHON_ENVIRONMENT, "/account/python-environment"),
    ],
)
def test_gated_routes_are_absent_when_feature_disabled(tmp_path, feature, path):
    with _local_app(tmp_path, {DISABLED_SITE_FEATURES_ENV_VAR: feature.value}) as app:
        paths = {route.path for route in iter_effective_api_routes(app)}

        assert path not in paths


def test_disabled_model_connections_returns_404(tmp_path):
    with (
        _local_app(
            tmp_path, {DISABLED_SITE_FEATURES_ENV_VAR: SiteFeature.MODEL_CONNECTIONS.value}
        ) as app,
        TestClient(app) as client,
    ):
        access_token = _get_access_token(client)
        response = client.get(
            "/model-connections",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 404
