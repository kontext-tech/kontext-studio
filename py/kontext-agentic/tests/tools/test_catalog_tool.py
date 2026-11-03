"""Tests for catalog discovery tooling."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.agent import get_tool_runtime_spec
from kontext.agent.tools import get_declared_tool_meta
from kontext.agentic.tools.catalog_tool import CatalogTools
from kontext.schema import (
    CatalogEntityStatsBatchResult,
    ChatSessionModel,
    DiscoveryResult,
)


def test_search_catalog_has_strict_runtime_metadata(
    mock_service_provider,
    sample_project,
):
    toolkit = CatalogTools(
        project=sample_project,
        runtime_provider=mock_service_provider,
    )

    spec = get_tool_runtime_spec(toolkit.search_catalog)

    assert spec.strict is True
    assert spec.description is not None
    assert "query" in spec.description
    assert "SHOW TABLES" in spec.description


def test_catalog_tools_prioritize_search_when_available(
    mock_service_provider,
    sample_project,
):
    toolkit = CatalogTools(
        project=sample_project,
        runtime_provider=mock_service_provider,
    )

    tool_names = [tool.__name__ for tool in toolkit._tools]

    assert tool_names[0] == "search_catalog"


def test_batch_catalog_tools_declare_typed_result_classes():
    """Batch/discovery tools must declare their generated result models."""

    batch_meta = get_declared_tool_meta(CatalogTools.inspect_entities_columns)
    discovery_meta = get_declared_tool_meta(CatalogTools.discover)
    assert batch_meta is not None
    assert discovery_meta is not None
    assert batch_meta.result_class is CatalogEntityStatsBatchResult
    assert discovery_meta.result_class is DiscoveryResult


def test_search_catalog_declares_runtime_spec(
    mock_service_provider,
    sample_project,
):
    """Declared ToolMeta surface reaches the neutral spec; adapter wrapping behavior is covered by harness tests."""
    toolkit = CatalogTools(
        project=sample_project,
        runtime_provider=mock_service_provider,
    )

    spec = get_tool_runtime_spec(toolkit.search_catalog)
    assert spec.strict is True
    assert spec.description is not None


@pytest.mark.asyncio
async def test_catalog_tools_prefer_chat_default_connection(
    mock_service_provider,
    sample_project,
):
    chat_session_service = MagicMock()
    chat_session_service.get_session = AsyncMock(
        return_value=ChatSessionModel.model_construct(
            id="550e8400-e29b-41d4-a716-446655440020",
            project_id=sample_project.id,
            session_name="Chat Session",
            date_created=datetime.now(UTC),
            python_execution_approval_mode="auto",
            is_deleted=False,
            default_catalog_connection_id="550e8400-e29b-41d4-a716-446655440021",
            default_namespace="crm",
            engine_type="sqlserver",
        )
    )
    mock_service_provider.get_chat_session_service.return_value = chat_session_service

    toolkit = CatalogTools(
        project=sample_project,
        runtime_provider=mock_service_provider,
        chat_session_id="550e8400-e29b-41d4-a716-446655440020",
    )
    toolkit.catalog_data_service = MagicMock()
    toolkit.catalog_data_service.list_connections_async = AsyncMock()
    toolkit.catalog_data_service.list_namespaces_async = AsyncMock(return_value=[])

    await toolkit.list_namespaces()

    toolkit.catalog_data_service.list_connections_async.assert_not_awaited()
    toolkit.catalog_data_service.list_namespaces_async.assert_awaited_once_with(
        "550e8400-e29b-41d4-a716-446655440021"
    )


def _catalog_toolkit_with_entities(mock_service_provider, sample_project):
    toolkit = CatalogTools(project=sample_project, runtime_provider=mock_service_provider)
    toolkit.catalog_connection_id = "550e8400-e29b-41d4-a716-446655440021"
    toolkit.catalog_data_service = MagicMock()
    toolkit.catalog_data_service.list_entities_async = AsyncMock(
        return_value=[
            SimpleNamespace(id="entity-orders", entity_name="orders"),
            SimpleNamespace(id="entity-customers", entity_name="customers"),
        ]
    )
    toolkit.catalog_data_service.get_entity_detail_async = AsyncMock(
        return_value=SimpleNamespace(
            columns=[
                SimpleNamespace(
                    name="id",
                    data_type="INTEGER",
                    nullable=False,
                    ordinal_position=1,
                    description=None,
                )
            ]
        )
    )
    return toolkit


@pytest.mark.asyncio
async def test_inspect_entities_columns_uses_one_listing_and_reports_missing(
    mock_service_provider, sample_project
):
    toolkit = _catalog_toolkit_with_entities(mock_service_provider, sample_project)

    payload = json.loads(
        await toolkit.inspect_entities_columns(
            ["orders", "customers", "missing"], namespace_name="crm"
        )
    )

    assert payload["entitiesCount"] == 3
    assert payload["failedCount"] == 1
    assert payload["success"] is False
    assert payload["type"] == "catalog_entity_stats_batch"
    # One listing per namespace, not one per requested entity.
    data_service = cast(MagicMock, toolkit.catalog_data_service)
    data_service.list_entities_async.assert_awaited_once()
    assert data_service.get_entity_detail_async.await_count == 2

    by_name = {entity["objectName"]: entity for entity in payload["entities"]}
    assert by_name["orders"]["success"] is True
    assert by_name["orders"]["type"] == "catalog_entity_stats"
    assert by_name["orders"]["statsCount"] == 1
    assert by_name["orders"]["columnStats"][0]["columnName"] == "id"
    assert by_name["customers"]["success"] is True
    assert by_name["missing"]["success"] is False


@pytest.mark.asyncio
async def test_inspect_entities_columns_caches_namespace_listing_across_calls(
    mock_service_provider, sample_project
):
    toolkit = _catalog_toolkit_with_entities(mock_service_provider, sample_project)

    await toolkit.inspect_entities_columns(["orders"], namespace_name="crm")
    await toolkit.inspect_entities_columns(["crm.customers"])

    # The second call reuses the cached namespace listing.
    cast(MagicMock, toolkit.catalog_data_service).list_entities_async.assert_awaited_once()


@pytest.mark.asyncio
async def test_inspect_entities_columns_truncates_long_descriptions(
    mock_service_provider, sample_project
):
    toolkit = _catalog_toolkit_with_entities(mock_service_provider, sample_project)
    long_description = "x" * 1000
    toolkit.catalog_data_service.get_entity_detail_async = AsyncMock(
        return_value=SimpleNamespace(
            columns=[
                SimpleNamespace(
                    name="id",
                    data_type="INTEGER",
                    nullable=False,
                    ordinal_position=1,
                    description=long_description,
                )
            ]
        )
    )

    payload = json.loads(await toolkit.inspect_entities_columns(["orders"], namespace_name="crm"))

    description = payload["entities"][0]["columnStats"][0]["samples"][0]["description"]
    assert description.endswith("...")
    assert len(description) < len(long_description)


@pytest.mark.asyncio
async def test_discover_degrades_gracefully_when_sources_unavailable(
    mock_service_provider, sample_project
):
    mock_service_provider.get_catalog_index_service.return_value = None
    mock_service_provider.get_knowledge_service.return_value = None

    toolkit = CatalogTools(project=sample_project, runtime_provider=mock_service_provider)
    toolkit.catalog_connection_id = "550e8400-e29b-41d4-a716-446655440021"

    payload = json.loads(await toolkit.discover(query="orders"))

    assert payload["type"] == "discovery"
    assert payload["success"] is False
    assert payload["tables"] == []
    assert payload["concepts"] == []
    assert "tables" in payload["errors"]
    assert "knowledge" in payload["errors"]
