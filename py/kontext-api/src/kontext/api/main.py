"""
Kontext API - Unified FastAPI Application

Main application entry point for Data and AI APIs.
Provides query execution, session management, and AI chat services
in a single containerized FastAPI application.

Local mode (KONTEXT_LOCAL_MODE=true)
-------------------------------------
When the API is started with ``KONTEXT_LOCAL_MODE=true``, it operates
using SQLite for data storage (so no PostgreSQL needed):
- The identity router and standard routers operate transparently.
- The `database_url` is forced to `sqlite:///{HOME}/.kontext/kontext.db`.
- Database schema is automatically initialized.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kontext.runtime.profiles import RuntimeProfile, get_runtime_profile

from .app_factory import build_app, configure_runtime_logging, resolve_cors_origins

logger = logging.getLogger(__name__)

# Environment variable names for configuration
ENV_CORS_ALLOWED_ORIGINS = "CORS_ALLOWED_ORIGINS"
"""Comma-separated list of allowed CORS origins (e.g., 'https://app.kontext.tech,https://kontext.tech').
Falls back to '*' (allow all) for local development if not set."""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    service_name = os.getenv("SERVICE_NAME", "kontext-api")
    runtime_profile = get_runtime_profile()

    configure_runtime_logging(service_name)
    logger.info(f"Starting {service_name}...")

    try:
        logger.info(
            "Runtime profile %s: identity=%s, relational=%s, storage=%s, execution=%s",
            runtime_profile.name,
            runtime_profile.identity_backend,
            runtime_profile.relational_backend,
            runtime_profile.storage_backend,
            runtime_profile.execution_backend,
        )
        runtime_profile.initialize()
        logger.info("Runtime initialization complete")
    except Exception:
        # Fail fast: an unterminated startup would serve requests against an
        # uninitialized runtime (e.g. no migrations, missing seeding) and turn
        # a configuration error into confusing per-request failures.
        logger.error("Failed to initialize runtime profile", exc_info=True)
        raise

    yield

    logger.info("Shutting down Kontext API...")


def create_app(runtime_profile: RuntimeProfile | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Pass an explicit ``runtime_profile`` to override environment detection —
    the offline OpenAPI exporter builds the cloud contract this way instead of
    mutating process state.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    runtime_profile = runtime_profile or get_runtime_profile()
    is_dev = env == "development" or runtime_profile.is_local

    logger.info(
        "Creating FastAPI app (ENVIRONMENT=%s, profile=%s)",
        env,
        runtime_profile.name,
    )

    # Mounting local platform routers requires the process environment to
    # describe local mode before those routers resolve their dependencies.
    if runtime_profile.exposes_local_platform_routers:
        runtime_profile.configure_process_environment()

    app = build_app(
        title="Kontext API",
        description=(
            "API providing data analytics and AI chat. "
            "Supports query execution, session management, "
            "and project-scoped AI interactions."
        ),
        lifespan=lifespan,
        openapi_enabled=is_dev,
        include_error_details=is_dev,
        cors_origins=resolve_cors_origins(
            is_dev=is_dev,
            configured=os.getenv(ENV_CORS_ALLOWED_ORIGINS, ""),
        ),
        include_local_platform_routers=runtime_profile.exposes_local_platform_routers,
        local_request_guard=runtime_profile.is_local,
    )

    logger.info("Kontext API application created successfully")
    return app


# Create the application instance
app = create_app()


def main():
    """CLI entry point for running the API server."""
    import uvicorn

    default_host = "127.0.0.1" if get_runtime_profile().is_local else "0.0.0.0"
    host = os.getenv("HOST", default_host)
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("ENVIRONMENT", "Development") == "Development"

    from kontext.runtime.local.hosts import configure_allowed_hosts, is_loopback_host

    if get_runtime_profile().is_local:
        configure_allowed_hosts(host)
        if not is_loopback_host(host):
            logger.warning(
                "Bound to non-loopback host %s; only this machine's interface "
                "addresses pass Host validation.",
                host,
            )

    logger.info(f"Starting Kontext API on {host}:{port} (reload={reload})")

    uvicorn.run("kontext.api.main:app", host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    main()
