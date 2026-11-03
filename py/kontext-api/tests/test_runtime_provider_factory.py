"""Tests for the API-owned bare (headers-only) runtime provider factory."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from kontext.api.services.runtime import (
    LOCAL_HEADERS_RUNTIME_FACTORY,
    LocalHeadersRuntimeFactory,
)
from kontext.auth import AuthManager


@pytest.mark.asyncio
async def test_local_headers_runtime_factory_refreshes_auth_and_returns_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auth tokens refresh exactly once before the provider is returned."""
    auth_manager = AuthManager.__new__(AuthManager)
    auth_manager.refresh_if_needed = AsyncMock()  # type: ignore[method-assign]
    monkeypatch.setattr(
        AuthManager,
        "from_headers",
        classmethod(lambda cls, headers: auth_manager),
    )

    provider = await LOCAL_HEADERS_RUNTIME_FACTORY.create_runtime_provider(
        project_id=str(uuid.uuid4()),
        headers={"Authorization": "Bearer test"},
    )

    assert provider is not None
    assert isinstance(LOCAL_HEADERS_RUNTIME_FACTORY, LocalHeadersRuntimeFactory)
    auth_manager.refresh_if_needed.assert_awaited_once()
