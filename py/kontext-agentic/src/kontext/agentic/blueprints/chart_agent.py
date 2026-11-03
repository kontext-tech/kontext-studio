"""
Chart Agent blueprint for Kontext Agentic.

Builds a harness-neutral :class:`AgentSpec` for data visualization. No
framework-specific code lives here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kontext.agent import AgentDescriptor, AgentKind, AgentSpec

from ..tools.chart_tool import ChartTools
from ..tools.kontext_toolkit import ToolkitScope
from ..utils.project_helpers import generate_project_summary
from .instructions import (
    build_role_instructions,
    clarify_after_discovery_line,
    no_manual_workaround_line,
    verify_claims_line,
)

if TYPE_CHECKING:
    from ..adapters import AgentCreationContext

logger = logging.getLogger(__name__)


CHART_AGENT_DESCRIPTOR = AgentDescriptor(
    id=AgentKind.CHART,
    name="Chart Agent",
    icon="ChartNoAxesCombinedOutlined",
    description=(
        "Visualization expert specialized in transforming raw complex data into insightful, interactive charts."
    ),
)


async def build_chart_spec(context: AgentCreationContext) -> AgentSpec:
    """Build the neutral chart agent specification."""
    project = context.project
    project_id = project.id
    logger.info(f"Using pre-loaded project context for {project_id}")
    project_context_summary = generate_project_summary(project)

    chart_tool = ChartTools(scope=ToolkitScope.from_context(context))

    instructions = build_role_instructions(
        intro=f"Visualization specialist for project `{project_id}`.",
        context_summary=project_context_summary,
        owned_actions=[
            "Create new chart artifacts from a provided data handle.",
            "Update existing charts with valid chart configs.",
            "Validate requested chart fields against the resolved data-table schema before charting.",
        ],
        workflow=[
            "Accept either a durable `data_table_id` or a session-resolvable data handle from the coordinator.",
            "Use `create_*_chart` for new charts and `update_chart` for existing charts; prefer update for small changes because delete-and-recreate changes the `chart_id` and breaks references.",
            "If the request depends on SQL results but no usable data handle was provided, ask the coordinator for an executed reusable result from SQL Agent instead of asking the user for schema details first.",
            "Keep field names aligned with the resolved schema before creating or updating the chart.",
            "Confirm the resulting `chart_id` in the final response.",
        ],
        hard_stops=[
            no_manual_workaround_line(
                task="run SQL, export CSV, or persist query results",
                capability="the coordinator can obtain reusable results through SQL Agent",
            ),
            verify_claims_line(),
            "Do not invent field names, data values, or schema details.",
        ],
        response_contract=[
            "Return the created or updated `chart_id` and the fields used.",
            "If a usable data handle is missing, ask only for the coordinator handoff you need rather than pushing the work back to the user.",
            clarify_after_discovery_line(),
        ],
    )

    tools = (chart_tool,)

    logger.info(f"Chart agent spec built successfully for project {project_id}")
    return AgentSpec(
        descriptor=CHART_AGENT_DESCRIPTOR,
        instructions=instructions,
        role=(
            "Create and update chart artifacts (.chart) from a provided reusable `data_table_id` or "
            "session-resolvable data handle; validate columns before charting."
        ),
        tools=tools,
        config=context.config,
    )
