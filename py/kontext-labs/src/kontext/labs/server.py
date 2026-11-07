"""
Kontext - Local HTTP/WebSocket Server

Bootstraps a FastAPI application that:
  - Exposes the same API contract as the cloud API
    (all routers imported directly from kontext-api)
  - Serves the built React app statically so the browser UI
    connects to http://127.0.0.1:<port>
  - Falls back to index.html for unknown paths (SPA routing)
  - Manages a local SQLite database (~/.kontext/kontext.db) for structured state
  - Manages a local lake directory (~/.kontext/) for file-based storage

Usage:
    kontext serve [--port 8000] [--dist-dir /path/to/app/dist]
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from kontext.api.app_factory import (
    LOCAL_CORS_ORIGINS,
    build_app,
    configure_runtime_logging,
)
from kontext.labs.telemetry import configure_telemetry
from kontext.runtime.profiles import get_local_runtime_profile

from .async_cleanup import drain_async_finalizers

logger = logging.getLogger(__name__)


# Default dist directory: check for bundled package data first, then repo-relative
def _resolve_default_dist() -> Path:
    bundled = Path(__file__).parent / "_app_dist"
    if bundled.is_dir():
        return bundled
    return Path(__file__).parent.parent.parent.parent.parent.parent.parent / "app" / "dist"


_DEFAULT_DIST = _resolve_default_dist()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the local server."""
    from kontext.common.config import get_config

    cfg = get_config()
    runtime_profile = get_local_runtime_profile()

    configure_runtime_logging("kontext-studio")
    configure_telemetry(service_name="kontext-studio")

    logger.info("Starting Kontext local server...")

    try:
        db_url = runtime_profile.initialize(log_level=cfg.log_level, log_format=cfg.log_format)
        logger.info("Initialized local SQLite database at %s", db_url)
        logger.info("SQLite database ready.")
    except Exception as exc:
        logger.error("Failed to initialize SQLite database: %s", exc, exc_info=True)

    yield

    # The API process does not execute jobs; that runs in a separate worker
    # process (``kontext worker``) so a hung job cannot wedge the server.
    await drain_async_finalizers()

    logger.info("Kontext server stopped.")


def create_app(dist_dir: str | Path | None = None) -> FastAPI:
    """
    Create the local FastAPI application.

    Mounts all kontext-api routers (same contract as cloud) and
    serves the bundled React application from *dist_dir*.

    Args:
        dist_dir: Path to the Vite build output (``app/dist``).
                  Falls back to the ``KONTEXT_DIST_DIR`` env-var and
                  then to the repo-relative ``app/dist`` directory.
    """
    dist_path = Path(dist_dir or os.getenv("KONTEXT_DIST_DIR", "") or _DEFAULT_DIST).resolve()

    app = build_app(
        title="Kontext (Local)",
        description="Local Kontext runtime with Data & AI APIs and React frontend.",
        lifespan=lifespan,
        # Local mode always exposes the contract and interactive docs.
        openapi_enabled=True,
        include_error_details=True,
        cors_origins=list(LOCAL_CORS_ORIGINS),
        include_local_platform_routers=True,
        local_request_guard=True,
    )

    # ── Static React app ──────────────────────────────────────────────────────
    if dist_path.exists():
        assets_path = dist_path / "assets"
        if assets_path.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
        app.mount("/static", StaticFiles(directory=str(dist_path)), name="static")

        # Pre-read and patch index.html with runtime env overrides.
        # Injected at the END of <head> so it overrides the Vite build-time
        # window.ENV object with correct runtime values.
        _patched_html: str | None = None
        index_file = dist_path / "index.html"
        if index_file.exists():
            raw_html = index_file.read_text(encoding="utf-8")
            env_script = (
                "<script>"
                "window.ENV=window.ENV||{};"
                # Override build-time KONTEXT_LOCAL_MODE (was "false") to "true"
                'window.ENV.KONTEXT_LOCAL_MODE="true";'
                # Point all API calls to this same server (no separate .NET API)
                "window.ENV.PUBLIC_KONTEXT_API_URL=window.location.origin;"
                # Both key names are set: PUBLIC_KONTEXT_DA_API_URL (legacy)
                # and PUBLIC_KONTEXT_DATA_API_URL (envUtils.ts canonical key)
                "window.ENV.PUBLIC_KONTEXT_DA_API_URL=window.location.origin;"
                "window.ENV.PUBLIC_KONTEXT_DATA_API_URL=window.location.origin;"
                "</script>"
            )
            # Inject AFTER Vite's window.ENV script so our values win
            _patched_html = raw_html.replace("</head>", f"{env_script}</head>", 1)

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            """Serve a bundled file when one exists, else index.html for SPA routes.

            Vite copies `public/` verbatim, so logos and icons live at `/resources`
            and `/icons` rather than under `/assets`. Anything that is not a real
            file has to fall through to the app shell for React Router.
            """
            candidate = (dist_path / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(dist_path):
                return FileResponse(candidate)
            if _patched_html is not None:
                return HTMLResponse(content=_patched_html)
            return JSONResponse(
                status_code=503,
                content={
                    "detail": (
                        f"React app not found at {dist_path}. "
                        "Run `pnpm run build` in the `app/` directory first."
                    )
                },
            )

    return app
