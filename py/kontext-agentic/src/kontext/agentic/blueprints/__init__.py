"""Kontext agentic layer blueprints (harness-neutral AgentSpec builders).

Importing this package registers every domain blueprint (kind -> AgentSpec
builder) with the framework registry. It is harness-neutral: no framework
SDK is imported here, so it is safe to load regardless of the active harness.

Today chat only ever resolves the COORDINATOR blueprint (the root agent for
every chat session); member kinds (SQL/CHART/NOTEBOOK/PYTHON) are composed by
the coordinator blueprint directly. They are still registered so a future
per-kind entrypoint (e.g. a focused single-agent endpoint) can resolve them
through this registry without further changes.
"""

from __future__ import annotations

from kontext.agent import AgentKind
from kontext.agentic.adapters import register_agent_blueprint

from .chart_agent import build_chart_spec
from .notebook_agent import build_notebook_spec
from .python_agent import build_python_spec
from .sql_agent import build_sql_spec
from .team import build_coordinator_spec

# The root chat agent: COORDINATOR ("team") composes the specialist blueprints.
register_agent_blueprint(AgentKind.COORDINATOR, build_coordinator_spec)
# Registered for future per-kind selection; nothing resolves them today.
register_agent_blueprint(AgentKind.SQL, build_sql_spec)
register_agent_blueprint(AgentKind.CHART, build_chart_spec)
register_agent_blueprint(AgentKind.NOTEBOOK, build_notebook_spec)
register_agent_blueprint(AgentKind.PYTHON, build_python_spec)

__all__ = [
    "build_chart_spec",
    "build_coordinator_spec",
    "build_notebook_spec",
    "build_python_spec",
    "build_sql_spec",
]
