import os
import sys
from collections import defaultdict

# Ensure src is on the path for test discovery
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from kontext.api.main import app  # type: ignore
from kontext.api.testing import iter_effective_api_routes  # type: ignore


def _get_paths() -> set[str]:
    return {route.path for route in iter_effective_api_routes(app)}


def _get_route_methods() -> dict[str, set[str]]:
    methods_by_path: dict[str, set[str]] = defaultdict(set)
    for route in iter_effective_api_routes(app):
        methods_by_path[route.path].update(route.methods or set())
    return methods_by_path


def test_expected_routes_are_registered():
    paths = _get_paths()
    # This API is mounted at the root (no global /api prefix). See
    # kontext.api.main:create_app() for router mounting.
    api_prefix = ""
    # Health
    assert f"{api_prefix}/ping" in paths
    assert f"{api_prefix}/health" in paths
    # Data (query)
    assert f"{api_prefix}/query/execute" in paths
    assert f"{api_prefix}/query/execute-async" in paths
    assert f"{api_prefix}/session/init" in paths
    assert f"{api_prefix}/session/init-async" in paths
    assert f"{api_prefix}/runs" in paths
    assert f"{api_prefix}/runs/{{runId}}" in paths
    assert f"{api_prefix}/runs/{{runId}}/input" in paths
    assert f"{api_prefix}/runs/{{runId}}/cancel" in paths
    assert f"{api_prefix}/runs/{{runId}}/retry" in paths
    # AI
    assert f"{api_prefix}/ai/chat/stream" in paths
    assert f"{api_prefix}/ai/chat/upload-preparations" in paths
    assert f"{api_prefix}/ai/chat/upload-preparations/{{runId}}" in paths
    assert f"{api_prefix}/ai/chat/session/{{chatSessionId}}/attachment-context" in paths
    # Events
    assert f"{api_prefix}/event" in paths


def test_expected_methods_for_endpoints():
    route_methods = _get_route_methods()

    api_prefix = ""

    assert route_methods[f"{api_prefix}/ping"] == {"GET"}
    assert route_methods[f"{api_prefix}/health"] == {"GET"}
    assert "POST" in route_methods[f"{api_prefix}/query/execute"]
    assert "POST" in route_methods[f"{api_prefix}/query/execute-async"]
    assert "POST" in route_methods[f"{api_prefix}/session/init"]
    assert "POST" in route_methods[f"{api_prefix}/session/init-async"]
    assert "GET" in route_methods[f"{api_prefix}/runs"]
    assert "GET" in route_methods[f"{api_prefix}/runs/{{runId}}"]
    assert "POST" in route_methods[f"{api_prefix}/runs/{{runId}}/input"]
    assert "POST" in route_methods[f"{api_prefix}/runs/{{runId}}/cancel"]
    assert "POST" in route_methods[f"{api_prefix}/runs/{{runId}}/retry"]
    assert "POST" in route_methods[f"{api_prefix}/ai/chat/stream"]
    assert "POST" in route_methods[f"{api_prefix}/ai/chat/upload-preparations"]
    assert "GET" in route_methods[f"{api_prefix}/ai/chat/upload-preparations/{{runId}}"]
    assert (
        "POST"
        in route_methods[f"{api_prefix}/ai/chat/session/{{chatSessionId}}/attachment-context"]
    )
    assert "GET" in route_methods[f"{api_prefix}/event"]
