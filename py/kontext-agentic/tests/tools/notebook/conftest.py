"""Shared fixtures and stubs for notebook tool tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


class TestRuntimeContext:
    """RuntimeToolContext stub satisfying pydantic's any-schema hook."""

    def __init__(self, session_state: dict[str, Any] | None = None):
        self.session_state = session_state

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        return core_schema.any_schema()


@pytest.fixture
def mock_service_provider():
    """Fixture to create a mock service provider."""
    provider = MagicMock()
    provider.get_file_service.return_value = MagicMock()
    provider.get_query_session_service.return_value = MagicMock()
    return provider
