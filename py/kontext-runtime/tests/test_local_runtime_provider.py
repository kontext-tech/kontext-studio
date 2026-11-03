from __future__ import annotations

from unittest.mock import MagicMock

from kontext.runtime.providers.local import LocalRuntimeProvider


def test_get_query_session_service_returns_explicit_override() -> None:
    query_session_service = MagicMock()

    provider = LocalRuntimeProvider(
        "550e8400-e29b-41d4-a716-446655440000",
        query_session_service=query_session_service,
    )

    service = provider.get_query_session_service()

    assert service is query_session_service


def test_get_query_session_service_falls_back_to_local_service() -> None:
    provider = LocalRuntimeProvider("550e8400-e29b-41d4-a716-446655440000")

    service = provider.get_query_session_service()

    assert service is not None
