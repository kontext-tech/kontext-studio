"""Tests for CORS handling on unhandled 500s (ServerErrorMiddleware)."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kontext.api.helpers import register_exception_handlers


def _app_with_boom(*, cors_origins: list[str]) -> TestClient:
    app = FastAPI()
    register_exception_handlers(
        app,
        logger=logging.getLogger("test"),
        include_error_details=True,
        cors_origins=cors_origins,
        cors_allow_credentials=True,
    )

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("kaboom")

    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_500_includes_cors_headers_for_allowed_origin() -> None:
    client = _app_with_boom(cors_origins=["http://localhost:8002"])

    response = client.get("/boom", headers={"Origin": "http://localhost:8002"})

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:8002"
    assert response.headers["access-control-allow-credentials"] == "true"
    # One error shape everywhere: problem+json, internals gated by mode.
    assert response.headers["content-type"].startswith("application/problem+json")
    payload = response.json()
    assert payload["type"] == "InternalServerError"
    assert payload["detail"] == "kaboom"  # include_error_details=True in this app


def test_unhandled_500_omits_cors_headers_for_disallowed_origin() -> None:
    client = _app_with_boom(cors_origins=["http://localhost:8002"])

    response = client.get("/boom", headers={"Origin": "http://evil.example"})

    assert response.status_code == 500
    assert "access-control-allow-origin" not in response.headers
