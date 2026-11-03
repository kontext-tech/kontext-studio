"""
Coordinator agent blueprint for Kontext Agentic.

Builds a harness-neutral :class:`AgentSpec` whose ``members`` are the specialist
agent specs (SQL, Chart, Notebook, Python). "Team" is a harness detail: Agno
materializes this spec as a ``Team``, while a hierarchical harness (e.g. Google
ADK) materializes it as an agent with sub-agents. No framework-specific code
lives here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kontext.agent import AgentDescriptor, AgentKind, AgentSpec, create_kontext_session_state

from ..tools.kontext_toolkit import ToolkitScope
from ..tools.project_tool import ProjectTools
from ..utils.project_helpers import generate_sql_scope_summary
from .chart_agent import build_chart_spec
from .instructions import (
    ambiguous_routing_line,
    build_role_instructions,
    clarify_after_discovery_line,
    complex_analysis_routing_line,
    configured_connection_hard_stop_line,
    configured_connection_workflow_line,
    inline_fast_path_line,
    no_manual_workaround_line,
    reusable_handoff_line,
    verify_claims_line,
)
from .notebook_agent import build_notebook_spec
from .python_agent import build_python_spec
from .sql_agent import build_sql_spec

if TYPE_CHECKING:
    from ..adapters import AgentCreationContext

logger = logging.getLogger(__name__)


COORDINATOR_AGENT_DESCRIPTOR = AgentDescriptor(
    id=AgentKind.COORDINATOR,
    name="Data Team",
    icon="SparklesOutlined",
    description=(
        "A collaborative team of specialist agents (SQL, Chart, Notebook, Python) led by a coordinator "
        "to solve complex multi-step data problems."
    ),
)


async def build_coordinator_spec(context: AgentCreationContext) -> AgentSpec:
    """Build the neutral coordinator spec with specialist member specs."""
    project = context.project
    project_id = project.id
    logger.info(f"Initializing specialist agent specs for team in project {project_id}")

    # Member roles are owned by each blueprint's default.
    sql_spec = await build_sql_spec(context)
    chart_spec = await build_chart_spec(context)
    notebook_spec = await build_notebook_spec(context, allow_python=True)
    python_spec = await build_python_spec(context, include_sql_tools=False)

    logger.info(f"Using pre-loaded project context for {project_id}")
    project_context_summary = generate_sql_scope_summary(
        project,
        query_session_id=context.query_session_id,
        catalog_connection_id=context.catalog_connection_id,
        default_namespace=context.default_namespace,
        default_entity_id=context.default_entity_id,
        engine_type=context.engine_type,
    )

    project_tool = ProjectTools(scope=ToolkitScope.from_context(context))
    owned_actions = [
        "Route data discovery and SQL execution to SQL Agent.",
        "Route standalone chart creation and updates to Chart Agent.",
        "Route machine learning and complex multi-step analysis deliverables to Notebook Agent.",
        "Route notebook creation, notebook updates, Python block execution, embedded charts, and artifact imports to Notebook Agent; Notebook Agent owns notebook mutation, notebook Python execution, and notebook-state updates.",
        "Route standalone Python analysis and managed Python execution to Python Agent; Python Agent does not mutate notebooks.",
    ]
    workflow_steps = [
        configured_connection_workflow_line(),
        "Data questions -> SQL Agent answers directly.",
        complex_analysis_routing_line(),
        inline_fast_path_line(),
        ambiguous_routing_line(),
        "If a user refers to attached files, use the attached-data mapping first and route the relevant table work to SQL Agent.",
        "For underspecified chart, notebook, or analysis requests that depend on query results and do not already have a usable data handle, route discovery to SQL Agent before asking the user for table or column names.",
        "Before chart, notebook, or downstream artifact work that depends on query results, ensure SQL Agent has provided an executed reusable data handle.",
        (
            "Charts render from an existing data table - chart tools cannot aggregate. For grouped or aggregated "
            "chart requests (counts, sums, averages per category), route SQL Agent first to persist an aggregated "
            "reusable `data_table_id` (e.g., a `GROUP BY` result), then route the chart to Chart Agent for a standalone "
            "`.chart` or to Notebook Agent with `add_*_chart` for a notebook."
        ),
        "Reserve Python for analysis that SQL cannot express: a grouped or aggregated chart/table request is SQL plus chart/data-table work, not a Python task.",
        "Notebook Agent executes its own Python blocks via `execute_python_code(notebook_id, block_id)`; verify with `inspect_notebook_python_state(notebook_id)` when the notebook is the deliverable.",
        "Notebook Agent owns notebook structure; use it to create or edit blocks, run Python blocks, or import/persist a specific managed run by ID when needed.",
        "Standalone Python work that is a quick validation, snippet check, or one-shot statistic may stay with Python Agent; anything matching the complex-analysis routing triggers must go to Notebook Agent as a notebook deliverable.",
        "Reuse existing durable artifacts when they already satisfy the request.",
        "Verify the responsible specialist completed the required execution step rather than only drafting a plan or query.",
        "Hand off exact IDs, column names, and execution references produced by tools between specialists.",
        reusable_handoff_line(),
    ]
    hard_stops = [
        "Keep each specialist within its ownership and route work rather than performing another specialist's tasks.",
        configured_connection_hard_stop_line(),
        (
            "Do not conclude while notebook Python blocks are still unexecuted: "
            "Notebook Agent must execute them or state that they are intentionally deferred."
        ),
        (
            "Do not complete notebook-bound analysis with session-scoped Python instead of "
            "notebook blocks; route notebook-bound analysis to Notebook Agent."
        ),
        "Never invent, fabricate, or hallucinate data not explicitly returned in tool results.",
        no_manual_workaround_line(),
        verify_claims_line(),
    ]

    instructions = build_role_instructions(
        intro=f"Coordinate specialists to deliver the requested output for project `{project_id}`.",
        context_summary=project_context_summary,
        attached_data_summary=context.attached_data_summary,
        owned_actions=owned_actions,
        workflow=workflow_steps,
        hard_stops=hard_stops,
        response_contract=[
            "Present the delivered artifacts, their identifiers, and the grounded answer; that is the complete report.",
            "For notebook-routed requests, present the `notebook_id` and the executed block outputs as the deliverable.",
            "Present conclusions only after the required specialist workflow has completed successfully.",
            "Attempt the SQL-to-artifact handoff end-to-end before asking the user for any manual workaround.",
            clarify_after_discovery_line(),
        ],
    )

    team_session_state = create_kontext_session_state(context.attached_data_sources)
    tools = (project_tool,)

    logger.info(f"Coordinator agent spec built successfully for project {project_id}")
    return AgentSpec(
        descriptor=COORDINATOR_AGENT_DESCRIPTOR,
        instructions=instructions,
        role="Team leader: decide deliverable, delegate to specialists (SQL/Chart/Notebook/Python).",
        tools=tools,
        members=(sql_spec, chart_spec, notebook_spec, python_spec),
        share_member_interactions=True,
        add_member_history=True,
        persist_member_responses=True,
        session_state=team_session_state,
        add_session_state_to_context=True,
        config=context.config,
    )
