"""Shared FastAPI application factory for every Kontext entrypoint.

`kontext-api` (hosted) and `kontext-labs` (local server) previously built their
own ``FastAPI`` instances, CORS policies, exception handlers, and router
registrations. The two copies drifted (different origins, methods, and exposed
headers). Everything that must be identical lives here; entrypoints only supply
their lifespan, app metadata, and whether the local platform routers apply.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .helpers import (
    register_exception_handlers,
    register_local_platform_routers,
    register_standard_api_routers,
)

logger = logging.getLogger(__name__)

#: Origins accepted by local development servers (Vite, preview, bundled app).
LOCAL_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:8002",
    "http://localhost:8003",
    "http://localhost:8006",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:8000",
)

#: Origins accepted when running hosted with no explicit configuration.
PRODUCTION_CORS_ORIGINS: tuple[str, ...] = (
    "https://app.kontext.tech",
    "https://kontext.tech",
)

CORS_METHODS: tuple[str, ...] = (
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
    "OPTIONS",
    "HEAD",
)

CORS_EXPOSE_HEADERS: tuple[str, ...] = (
    "Content-Length",
    "Content-Range",
    "X-Total-Count",
)


def resolve_cors_origins(*, is_dev: bool, configured: str) -> list[str]:
    """Resolve the CORS origin list from a comma-separated configuration value.

    An empty value or an explicit wildcard falls back to the named origins for
    the active mode, because ``allow_credentials=True`` cannot be combined with
    a bare ``*``.
    """
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    if not origins or "*" in origins:
        return list(LOCAL_CORS_ORIGINS if is_dev else PRODUCTION_CORS_ORIGINS)
    return origins


def configure_runtime_logging(service_name: str) -> None:
    """Seed harness logging and structured logging exactly once per entrypoint.

    Every Kontext entrypoint must call this before serving requests: the agent
    harness installs its own log handlers (or fails fast loudly when no harness
    is installed), and structured logging owns the root configuration.
    """
    from kontext.agent.harness import seed_harness_logger_env
    from kontext.common.logging import configure_structured_logging

    seed_harness_logger_env()
    configure_structured_logging(service_name=service_name)


def build_app(
    *,
    title: str,
    description: str,
    lifespan: Any,
    openapi_enabled: bool,
    include_error_details: bool,
    cors_origins: list[str],
    cors_allow_credentials: bool = True,
    include_local_platform_routers: bool = False,
) -> FastAPI:
    """Build the FastAPI application shared by hosted and local entrypoints."""
    app = FastAPI(
        title=title,
        description=description,
        version="1.0.0",
        lifespan=lifespan,
        separate_input_output_schemas=False,
        openapi_url="/openapi.json" if openapi_enabled else None,
        docs_url="/docs" if openapi_enabled else None,
        redoc_url="/redoc" if openapi_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_allow_credentials,
        allow_methods=list(CORS_METHODS),
        allow_headers=["*"],
        expose_headers=list(CORS_EXPOSE_HEADERS),
        max_age=600,
    )

    register_exception_handlers(
        app,
        logger=logger,
        include_error_details=include_error_details,
        cors_origins=cors_origins,
        cors_allow_credentials=cors_allow_credentials,
    )

    if include_local_platform_routers:
        register_local_platform_routers(app)
    register_standard_api_routers(app)

    return app
