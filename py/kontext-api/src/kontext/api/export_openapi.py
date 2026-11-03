"""Offline OpenAPI exporter for the Data & AI API."""

from __future__ import annotations

import json
import sys
from typing import Any


def export_openapi_document() -> dict[str, Any]:
    """Build the FastAPI app in cloud mode and return its raw OpenAPI document.

    The cloud profile is passed explicitly so exporting never mutates the
    process environment (and stays correct when imported from another mode).
    """
    from kontext.api.main import create_app
    from kontext.runtime.profiles import get_cloud_runtime_profile

    app = create_app(runtime_profile=get_cloud_runtime_profile())
    return app.openapi()


def main() -> None:
    """CLI entry point that writes raw OpenAPI JSON to stdout."""
    json.dump(export_openapi_document(), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
