"""The hosted and local entrypoints must expose the same API contract."""

import os
from pathlib import Path
from unittest.mock import patch

from kontext.api.main import create_app as create_api_app
from kontext.api.testing import iter_effective_api_routes
from kontext.labs.server import create_app as create_labs_app

# The Kontext app adds this catch-all after the API routes to serve the SPA.
SPA_FALLBACK = "/{full_path:path}"


def _api_routes(app) -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in iter_effective_api_routes(app)
        for method in (route.methods or ())
        if route.path != SPA_FALLBACK
    }


def test_local_entrypoints_expose_the_same_routes(tmp_path: Path) -> None:
    with patch.dict(
        os.environ,
        {"KONTEXT_LOCAL_MODE": "true", "ENVIRONMENT": "development"},
        clear=True,
    ):
        api_app = create_api_app()
        labs_app = create_labs_app(dist_dir=str(tmp_path / "missing-dist"))

    assert _api_routes(api_app) == _api_routes(labs_app)
