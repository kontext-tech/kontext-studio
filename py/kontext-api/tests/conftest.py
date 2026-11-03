"""Shared fixtures for the API test suite."""

import pytest

from kontext.api.middleware.local_guard import allowed_hostnames

TEST_LAUNCH_TOKEN = "test-launch-token"


@pytest.fixture(autouse=True)
def _local_launch_token(monkeypatch):
    """Give the app a known launch token instead of the user's real one.

    Patching ``get_launch_token`` (not only the environment) keeps the token
    stable in tests that replace ``os.environ`` wholesale. Starlette's
    TestClient sends ``Host: testserver``, which is not trusted in production,
    so the guard's lookup is widened for tests only.
    """
    monkeypatch.setenv("KONTEXT_LOCAL_LAUNCH_TOKEN", TEST_LAUNCH_TOKEN)
    monkeypatch.setattr(
        "kontext.runtime.local.launch_token.get_launch_token",
        lambda: TEST_LAUNCH_TOKEN,
    )
    monkeypatch.setattr(
        "kontext.api.middleware.local_guard.allowed_hostnames",
        lambda: allowed_hostnames() | {"testserver"},
    )
