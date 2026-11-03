"""Pytest plugin: deterministic Kontext settings in every test run.

Registered through the ``pytest11`` entry-point group in
``py/kontext-common/pyproject.toml``, so the autouse fixture below applies to
every pytest invocation in the workspace — including per-package runs
(``uv run --package kontext-api pytest py/kontext-api/tests``) where the
repo-root ``conftest.py`` is outside the pytest rootdir and never loads.

Two guarantees:

1. **Test isolation** — new settings instances ignore ``.env`` files and the
   TOML config source, so a developer's local ``.env.local`` can never leak
   into test behavior. Configuration in tests comes purely from the OS
   environment (``monkeypatch.setenv`` / ``patch.dict``).

2. **Singleton reset** — ``KontextConfig`` is a process-wide singleton read
   lazily by deep layers (data, auth, logging); it is cleared before and
   after each test so env seeds are observed on the first read within a test
   and never leak into the next one.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from kontext.common.config import enable_test_isolation, reset_config


@pytest.fixture(autouse=True)
def _kontext_settings_isolation() -> Iterator[None]:
    """Enable settings test-isolation and reset the singleton per test."""
    enable_test_isolation()
    reset_config()
    try:
        yield
    finally:
        reset_config()
