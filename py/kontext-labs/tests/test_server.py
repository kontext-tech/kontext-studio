"""Tests for the Kontext server factory."""

import pytest
from fastapi.testclient import TestClient

from kontext.api.testing import iter_effective_api_routes
from kontext.common import BadRequestError
from kontext.labs.async_cleanup import drain_async_finalizers
from kontext.labs.server import create_app


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
        app = create_app(dist_dir=str(tmp_path / "nonexistent"))

        with TestClient(app) as client:
            response = client.get("/host/auth/bootstrap")

        assert response.status_code == 200
        payload = response.json()
        assert payload["mode"] == "local"
        assert payload["authenticated"] is True
        assert payload["accessToken"] is not None

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
