"""The local refresh endpoint must fail closed without a valid token."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from kontext.api.main import create_app
from kontext.data.database import get_engine, get_session_factory


@contextmanager
def _client(tmp_path: Path) -> Iterator[TestClient]:
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
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        try:
            yield TestClient(create_app())
        finally:
            get_engine.cache_clear()
            get_session_factory.cache_clear()


def test_refresh_without_body_is_unauthorized(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post("/auth/refresh")

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token required."


def test_refresh_without_token_field_is_unauthorized(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post("/auth/refresh", json={})

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token required."


def test_refresh_with_invalid_token_is_unauthorized(tmp_path: Path) -> None:
    with _client(tmp_path) as client:
        response = client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token."
