"""Agno toolkit adapter behavior.

The wrapping contracts below (missing-argument structured failures, absence of
`RuntimeToolContext` warnings) belong to the harness adapter surface. They use a
local neutral tool, so the adapter distribution does not need any domain
toolkit from `kontext-agentic` to verify its own wrapping behavior.
"""

from __future__ import annotations

import inspect
import json
import logging

import pytest

from kontext.agent import RuntimeToolContext, get_tool_runtime_spec
from kontext.agent.tools import create_tool_registry, tool_meta
from kontext.harness.agno.toolkits import _wrap_callable_for_agno

_TEST_REGISTRY = create_tool_registry(namespace="test-agno-toolkits")


@tool_meta(display_name="Search Catalog", registry=_TEST_REGISTRY)
async def search_catalog(
    query: str, limit: int = 5, run_context: RuntimeToolContext | None = None
) -> str:
    """Search the semantic catalog index for relevant entities."""
    _ = (query, limit, run_context)
    return "{}"


def test_search_catalog_wrap_does_not_emit_runtime_tool_context_warnings(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        wrapped = _wrap_callable_for_agno(get_tool_runtime_spec(search_catalog))

    assert wrapped is not None
    assert "RuntimeToolContext" not in caplog.text


@pytest.mark.asyncio
async def test_search_catalog_missing_query_returns_structured_failure() -> None:
    wrapped = _wrap_callable_for_agno(get_tool_runtime_spec(search_catalog))
    entrypoint = getattr(wrapped, "entrypoint", wrapped)

    assert inspect.iscoroutinefunction(entrypoint)
    payload = json.loads(await entrypoint())

    assert payload["success"] is False
    assert payload["message"] == "Missing required arguments for search_catalog: query"
    assert payload["error"] == "Missing required arguments for search_catalog: query"
