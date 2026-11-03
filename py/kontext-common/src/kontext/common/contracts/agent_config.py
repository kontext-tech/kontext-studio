"""Agent runtime behaviour configuration.

This is deliberately **not** a wire model. It carries the per-run knobs that
shape how an agent behaves (history, summarisation, tool budgets), while model
identity lives in the resolved :class:`~kontext.common.contracts.ResolvedModelConfig`
binding. Keeping the two apart stops a behaviour config from becoming a second
source of truth for which model to call.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from kontext.schema import ModelReasoningEffort


class AgentConfig(BaseModel):
    """Harness-neutral behaviour knobs for an agent run."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)

    reasoning_effort: ModelReasoningEffort | None = None
    markdown: bool = True
    tool_call_limit: int | None = 50
    default_sample_limit: int = 3
    sql_dialect: str = "DuckDB"
    add_history_to_context: bool = True
    num_history_runs: int = 3
    max_tool_calls_from_history: int | None = 3
    telemetry: bool = False
    summary: bool = True
    debug_mode: bool = False


__all__ = ["AgentConfig"]
