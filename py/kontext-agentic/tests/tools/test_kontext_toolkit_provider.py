from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agentic.tools.kontext_toolkit import KontextToolkit


def test_toolkit_prefers_service_provider(sample_project):
    provider = MagicMock()
    file_service = object()
    query_session_service = object()
    project_service = object()

    provider.get_file_service.return_value = file_service
    provider.get_query_session_service.return_value = query_session_service
    provider.get_project_service.return_value = project_service

    toolkit = KontextToolkit(name="TestToolkit", project=sample_project, runtime_provider=provider)

    assert toolkit.get_file_service() is file_service
    assert toolkit.get_query_session_service() is query_session_service
    assert toolkit.get_project_service() is project_service
    provider.get_file_service.assert_called_once()
    provider.get_query_session_service.assert_called_once()
    provider.get_project_service.assert_called_once()


def test_toolkit_returns_none_when_provider_missing_service(sample_project):
    provider = MagicMock()
    provider.get_file_service.return_value = None
    provider.get_query_session_service.return_value = None
    provider.get_project_service.return_value = None

    toolkit = KontextToolkit(name="TestToolkit", project=sample_project, runtime_provider=provider)

    assert toolkit.get_file_service() is None
    assert toolkit.get_query_session_service() is None
    assert toolkit.get_project_service() is None
    provider.get_file_service.assert_called_once()
    provider.get_query_session_service.assert_called_once()
    provider.get_project_service.assert_called_once()


@pytest.mark.asyncio
async def test_hydrate_query_scope_fetches_chat_session_at_most_once(sample_project):
    provider = MagicMock()
    chat_session_service = MagicMock()
    chat_session_service.get_session = AsyncMock(return_value=None)
    provider.get_chat_session_service.return_value = chat_session_service

    toolkit = KontextToolkit(
        name="TestToolkit",
        project=sample_project,
        runtime_provider=provider,
        chat_session_id="550e8400-e29b-41d4-a716-446655440020",
    )

    await toolkit.hydrate_query_scope_from_chat_session()
    await toolkit.hydrate_query_scope_from_chat_session()
    await toolkit.hydrate_query_scope_from_chat_session()

    chat_session_service.get_session.assert_awaited_once()
