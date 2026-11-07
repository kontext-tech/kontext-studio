"""Tests for the Kontext server factory."""

import pytest
from fastapi.testclient import TestClient

from kontext.api.testing import iter_effective_api_routes
from kontext.common import BadRequestError
from kontext.data.database import get_engine, get_session_factory
from kontext.labs.async_cleanup import drain_async_finalizers
from kontext.labs.server import create_app

TEST_LAUNCH_TOKEN = "test-launch-token"


def _launch_headers() -> dict[str, str]:
    return {"X-Kontext-Launch-Token": TEST_LAUNCH_TOKEN}


def _use_temp_database(monkeypatch, tmp_path) -> None:
    """Keep the lifespan from initializing the user's real workspace."""
    monkeypatch.setattr(
        "kontext.runtime.local.config.get_local_database_url",
        lambda: f"sqlite:///{tmp_path / 'kontext.db'}",
    )
    get_engine.cache_clear()
    get_session_factory.cache_clear()


class TestCreateApp:
    def test_create_app_returns_fastapi(self, tmp_path):
        """create_app should return a FastAPI instance even without dist."""
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))
        assert app is not None
        assert app.title == "Kontext (Local)"

    def test_create_app_registers_routers(self, tmp_path):
        """create_app should register the expected routers."""
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))
        paths = {route.path for route in iter_effective_api_routes(app)}
        # Core API routes should be present
        assert "/health" in paths
        assert "/host/auth/bootstrap" in paths

    def test_create_app_cors_middleware(self, tmp_path):
        """create_app should include CORS middleware."""
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))
        # CORSMiddleware is added via add_middleware
        assert len(app.user_middleware) > 0

    def test_host_auth_bootstrap_is_available(self, monkeypatch, tmp_path):
        """Local Kontext server should expose the host bootstrap contract."""
        monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
        _use_temp_database(monkeypatch, tmp_path)
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))
        headers = _launch_headers()

        try:
            with TestClient(app) as client:
                setup_response = client.post(
                    "/setup",
                    json={
                        "firstName": "Local",
                        "lastName": "Tester",
                        "email": "bootstrap-tester@example.com",
                    },
                    headers=headers,
                )
                assert setup_response.status_code == 200

                response = client.get("/host/auth/bootstrap", headers=headers)
                me_response = client.get("/host/auth/me")
        finally:
            get_engine.cache_clear()
            get_session_factory.cache_clear()

        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "local"
        assert payload["authenticated"] is True
        assert payload["accessToken"] is not None
        # The session cookie authenticates browser-native requests that cannot
        # attach an Authorization header.
        assert me_response.status_code == 200

    def test_launch_gate_survives_false_local_mode(self, monkeypatch, tmp_path):
        """A contradictory env must not remove the gate from the local app."""
        monkeypatch.setenv("KONTEXT_LOCAL_MODE", "false")
        _use_temp_database(monkeypatch, tmp_path)
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/setup",
                    json={
                        "firstName": "No",
                        "lastName": "Token",
                        "email": "no-token@example.com",
                    },
                )
        finally:
            get_engine.cache_clear()
            get_session_factory.cache_clear()

        assert response.status_code == 401
        assert "launch token" in response.json()["detail"].lower()

    def test_host_auth_bootstrap_requires_launch_token(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
        _use_temp_database(monkeypatch, tmp_path)
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))

        try:
            with TestClient(app) as client:
                response = client.get("/host/auth/bootstrap")
        finally:
            get_engine.cache_clear()
            get_session_factory.cache_clear()

        assert response.status_code == 401
        assert "launch token" in response.json()["detail"].lower()

    def test_local_request_guard_rejects_foreign_host(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
        _use_temp_database(monkeypatch, tmp_path)
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))

        try:
            with TestClient(app) as client:
                response = client.get(
                    "/host/auth/bootstrap",
                    headers={**_launch_headers(), "Host": "evil.example"},
                )
        finally:
            get_engine.cache_clear()
            get_session_factory.cache_clear()

        assert response.status_code == 403

    def test_local_request_guard_rejects_foreign_origin(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
        _use_temp_database(monkeypatch, tmp_path)
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))

        try:
            with TestClient(app) as client:
                response = client.post(
                    "/setup",
                    json={
                        "firstName": "Local",
                        "lastName": "Tester",
                        "email": "origin-tester@example.com",
                    },
                    headers={**_launch_headers(), "Origin": "https://evil.example"},
                )
        finally:
            get_engine.cache_clear()
            get_session_factory.cache_clear()

        assert response.status_code == 403

    def test_serves_bundled_assets_outside_assets_dir(self, monkeypatch, tmp_path):
        """Vite's `public/` files (logos, icons) must be served, not the app shell."""
        monkeypatch.setenv("KONTEXT_LOCAL_MODE", "true")
        _use_temp_database(monkeypatch, tmp_path)
        dist = tmp_path / "dist"
        (dist / "resources").mkdir(parents=True)
        (dist / "resources" / "logo.svg").write_text("<svg id='logo'/>", encoding="utf-8")
        (dist / "index.html").write_text("<html>app shell</html>", encoding="utf-8")
        app = create_app(dist_dir=str(dist))

        try:
            with TestClient(app) as client:
                asset = client.get("/resources/logo.svg", headers=_launch_headers())
                spa_route = client.get("/projects/123", headers=_launch_headers())
        finally:
            get_engine.cache_clear()
            get_session_factory.cache_clear()

        assert asset.status_code == 200
        assert "logo" in asset.text
        assert asset.headers["content-type"].startswith("image/svg")
        assert spa_route.status_code == 200
        assert "app shell" in spa_route.text

    def test_create_app_registers_problem_detail_handler(self, tmp_path):
        """Local Kontext server should reuse the API problem-detail handlers."""
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))

        @app.get("/_test/problem")
        async def _raise_problem():
            raise BadRequestError("problem detail test")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_test/problem")

        assert response.status_code == 400
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json() == {
            "type": "BadRequestError",
            "title": "Bad Request",
            "status": 400,
            "detail": "problem detail test",
        }


@pytest.mark.asyncio
async def test_drain_async_finalizers_completes():
    await drain_async_finalizers(cycles=1)
