"""Regression tests for the Agno tool-call budget (`AgentConfig.tool_call_limit`).

Forwarding tests pin that the neutral config knobs reach the Agno `Agent`.
Enforcement of the budget itself is pinned by the neutral conformance suite
(`test_conformance.py`, `assert_tool_call_limit_contract`), which runs
end-to-end with a scripted model on every harness test run.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from kontext.common.contracts import AgentConfig, ModelRuntime, ResolvedModelConfig
from kontext.harness.agno import materialize
from kontext.harness.agno.storage import NeutralBackedDb


def _sample_config(**overrides: Any) -> AgentConfig:
    values: dict[str, Any] = {"summary": False}
    values.update(overrides)
    return AgentConfig(**values)


def _model_runtime() -> ModelRuntime:
    return ModelRuntime(
        binding=ResolvedModelConfig(
            canonical_model_id="scripted/model",
            source_type="user_managed",
            adapter_type="scripted",
            connection_kind="scripted",
            display_name="Scripted",
            provider_model_name="model",
        )
    )


def test_create_agno_agent_forwards_tool_call_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setattr(materialize, "create_model", lambda **_: object())
    monkeypatch.setattr(
        materialize, "Agent", lambda **kwargs: captured.update(kwargs) or MagicMock()
    )

    materialize.create_agno_agent(
        agent_id="agent-1",
        name="Agent",
        tools=[],
        instructions="test",
        config=_sample_config(tool_call_limit=7),
        db=NeutralBackedDb(None),
        model=_model_runtime(),
    )

    assert captured["tool_call_limit"] == 7


def test_create_agno_agent_forwards_max_tool_calls_from_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """History depth and history tool-call budget must be independent knobs."""
    captured: dict[str, Any] = {}

    monkeypatch.setattr(materialize, "create_model", lambda **_: object())
    monkeypatch.setattr(
        materialize, "Agent", lambda **kwargs: captured.update(kwargs) or MagicMock()
    )

    materialize.create_agno_agent(
        agent_id="agent-1",
        name="Agent",
        tools=[],
        instructions="test",
        config=_sample_config(num_history_runs=5, max_tool_calls_from_history=11),
        db=NeutralBackedDb(None),
        model=_model_runtime(),
    )

    assert captured["num_history_runs"] == 5
    assert captured["max_tool_calls_from_history"] == 11
