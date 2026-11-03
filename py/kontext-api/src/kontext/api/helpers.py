"""
Helper classes and utilities for the Kontext API.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kontext.auth import JwtValidationError
from kontext.common import KontextError
from kontext.execution.polling import (
    JobRunPollingResult as JobRunPollingResult,
)
from kontext.execution.polling import (
    poll_job_run_completion as poll_job_run_completion,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(
    app: FastAPI,
    *,
    logger: logging.Logger,
    include_error_details: bool,
    cors_origins: list[str] | None = None,
    cors_allow_credentials: bool = True,
) -> None:
    """Register the standard API exception handlers.

    ``cors_origins`` (when provided) lets the catch-all 500 handler attach CORS
    headers itself. Starlette's ``ServerErrorMiddleware`` -- which serves the
    ``Exception`` handler -- sits *outside* ``CORSMiddleware``, so an unhandled
    500 would otherwise reach the browser without ``Access-Control-Allow-Origin``
    and surface as a misleading CORS error instead of the real failure.
    """

    def _cors_headers_for(request: Request) -> dict[str, str]:
        origin = request.headers.get("origin")
        if not origin or not cors_origins:
            return {}
        if "*" not in cors_origins and origin not in cors_origins:
            return {}
        headers = {
            "Access-Control-Allow-Origin": origin if "*" not in cors_origins else "*",
            "Vary": "Origin",
        }
        if cors_allow_credentials and "*" not in cors_origins:
            headers["Access-Control-Allow-Credentials"] = "true"
        return headers

    @app.exception_handler(JwtValidationError)
    async def jwt_validation_exception_handler(
        request: Request, exc: JwtValidationError
    ) -> JSONResponse:
        message = str(exc)
        problem_type = (
            "UnsupportedTokenVersion" if "Unsupported token version" in message else "Unauthorized"
        )
        return JSONResponse(
            status_code=401,
            content={
                "type": problem_type,
                "title": "Unauthorized",
                "status": 401,
                "detail": message or "Authentication required",
            },
            media_type="application/problem+json",
        )

    @app.exception_handler(KontextError)
    async def kontext_exception_handler(request: Request, exc: KontextError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": exc.problem_type or exc.__class__.__name__,
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
            },
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        # One error shape across the API: problem+json. Internal details are
        # only exposed when the app was built with include_error_details=True
        # (local mode / development).
        return JSONResponse(
            status_code=500,
            content={
                "type": "InternalServerError",
                "title": "Internal Server Error",
                "status": 500,
                "detail": (str(exc) if include_error_details else "An unexpected error occurred."),
            },
            media_type="application/problem+json",
            headers=_cors_headers_for(request),
        )


def register_local_platform_routers(app: FastAPI) -> None:
    """Register the local platform contract routers.

    Capability-gated surfaces (model connections, python environment) are
    mounted only when the active runtime profile advertises the matching
    :class:`~kontext.common.SiteFeature`. A disabled surface is then genuinely
    absent from the API (404), not merely hidden in the frontend.
    """
    from kontext.common import SiteFeature
    from kontext.runtime.profiles import get_runtime_profile

    from .routers import (
        account,
        auth,
        config,
        culture,
        host,
        model_connections,
        projects,
        python_environment,
        setup,
    )

    profile = get_runtime_profile()

    app.include_router(host.router)
    app.include_router(auth.router, tags=["Auth"])
    app.include_router(account.router, tags=["Account"])
    app.include_router(config.router, tags=["Config"])
    app.include_router(culture.router, tags=["Culture"])
    if profile.has_feature(SiteFeature.MODEL_CONNECTIONS):
        app.include_router(model_connections.router, tags=["ModelConnections"])
    if profile.has_feature(SiteFeature.PYTHON_ENVIRONMENT):
        app.include_router(python_environment.router, tags=["Account"])
    app.include_router(projects.router)
    app.include_router(setup.router)


def register_standard_api_routers(app: FastAPI) -> None:
    """Register the API routers shared by hosted and local entrypoints."""
    from .routers import (
        catalog,
        chats,
        events,
        files,
        health,
        job_runs,
        jobs,
        okf,
        project,
        query,
        query_sessions,
        runs,
    )

    app.include_router(health.router, tags=["Health"])
    app.include_router(catalog.router, prefix="/catalog", tags=["Catalog"])
    app.include_router(okf.router, prefix="/catalog/okf", tags=["Catalog"])
    app.include_router(query.router, prefix="/query", tags=["Data"])
    app.include_router(query_sessions.router, prefix="/session", tags=["Data"])
    app.include_router(files.router, prefix="/file", tags=["Files"])
    app.include_router(project.router, prefix="/project", tags=["Projects"])
    app.include_router(events.router, prefix="/event", tags=["Events"])
    app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])
    app.include_router(job_runs.router, prefix="/job-runs", tags=["Jobs"])
    app.include_router(runs.router, prefix="/runs", tags=["Runs"])
    app.include_router(chats.router, prefix="/ai", tags=["AI"])
