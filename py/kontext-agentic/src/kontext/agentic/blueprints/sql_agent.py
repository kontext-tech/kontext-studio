"""
SQL Agent blueprint for Kontext Agentic.

This module builds a harness-neutral :class:`AgentSpec` for SQL query writing,
execution, and result analysis. It contains no framework-specific code; the
active harness adapter materializes the spec into a concrete agent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kontext.agent import AgentDescriptor, AgentKind, AgentSpec, create_kontext_session_state

from ..tools.catalog_tool import CatalogTools
from ..tools.knowledge_tool import KnowledgeTools
from ..tools.kontext_toolkit import ToolkitScope
from ..tools.sql_tool import SqlTools
from ..utils.project_helpers import generate_sql_scope_summary
from .instructions import (
    batch_execution_line,
    batch_sampling_line,
    build_role_instructions,
    catalog_discovery_line,
    catalog_reliability_line,
    clarify_after_discovery_line,
    configured_connection_hard_stop_line,
    configured_connection_workflow_line,
    discovery_first_workflow_line,
    no_manual_workaround_line,
)

if TYPE_CHECKING:
    from ..adapters import AgentCreationContext

logger = logging.getLogger(__name__)


SQL_AGENT_DESCRIPTOR = AgentDescriptor(
    id=AgentKind.SQL,
    name="SQL Agent",
    icon="DatabaseZapOutlined",
    description=(
        "Expert query assistant focused on precise SQL generation and rigorous data analysis."
    ),
)


async def build_sql_spec(context: AgentCreationContext) -> AgentSpec:
    """Build the neutral SQL agent specification."""
    project = context.project
    project_id = project.id

    can_search_catalog = context.runtime_provider.get_catalog_index_service() is not None
    discovery_line = catalog_discovery_line(has_catalog_search=can_search_catalog)
    reliability_line = catalog_reliability_line(has_catalog_search=can_search_catalog)

    scope = ToolkitScope.from_context(context)
    config = context.config
    default_sample_limit = config.default_sample_limit
    sql_dialect = config.sql_dialect

    catalog_tool = CatalogTools(scope=scope)
    sql_tool = SqlTools(scope=scope, default_sample_limit=default_sample_limit)
    knowledge_tool = KnowledgeTools(scope=scope)

    logger.info(f"Using pre-loaded project context for {project_id}")

    instructions = build_role_instructions(
        intro=f"Expert SQL analyst for project `{project_id}` using {sql_dialect}.",
        context_summary=generate_sql_scope_summary(
            project,
            query_session_id=context.query_session_id,
            catalog_connection_id=context.catalog_connection_id,
            default_namespace=context.default_namespace,
            default_entity_id=context.default_entity_id,
            engine_type=context.engine_type,
        ),
        attached_data_summary=context.attached_data_summary,
        owned_actions=[
            "Discover tables and columns with catalog tools.",
            "Write and execute read-only SQL with `execute_sql`.",
            "Return grounded previews and reusable `data_table_id` values when they matter downstream.",
        ],
        workflow=[
            configured_connection_workflow_line(),
            discovery_line,
            "When a user refers to an attached file, start from the attached-data mapping to choose the relevant table first.",
            discovery_first_workflow_line(),
            "If a request names a business concept like customers, orders, revenue, or sessions without exact schema names, infer the likeliest sources through catalog discovery before asking the user to specify them.",
            f"Use `sample_records` with modest sample sizes such as `{default_sample_limit}` to peek at table/view rows while exploring; it returns CSV rows inline and creates no artifacts.",
            batch_sampling_line(),
            "Reserve `execute_sql` with the project's SQL dialect for queries whose results feed the answer or a downstream tool.",
            batch_execution_line(),
            "Prefer an existing reusable `data_table_id` when one already fits the task, and persist or rerun executed SQL only when downstream work still needs one.",
            "Rerun or persist SQL yourself to obtain a reusable `data_table_id` rather than pushing that work back to the user.",
            "Use `show_data_table` when you need to inspect or present a result preview.",
            reliability_line,
        ],
        hard_stops=[
            "Never invent rows, values, or aggregates not present in tool output.",
            "Never hand off raw SQL text as if it were executed data.",
            "Do not bypass catalog discovery when table or column names are uncertain.",
            "Do not use SQL metadata statements such as `SHOW TABLES`, `SHOW COLUMNS`, `DESCRIBE`, or `information_schema` for schema discovery when catalog tools are available.",
            configured_connection_hard_stop_line(
                invalid_scope_clause=(
                    "unless a tool explicitly reports that the configured scope is invalid or missing."
                ),
            ),
            no_manual_workaround_line(
                task="run SQL, export CSV, or persist results",
                capability="`execute_sql` can produce the needed result in this session",
            ),
            "Use attached-data metadata only to choose tables or clarify ambiguity; describe file contents only from executed SQL results.",
        ],
        response_contract=[
            "State the answer using executed results only.",
            clarify_after_discovery_line(),
            "When downstream chart or notebook work is required, return a reusable `data_table_id` produced from executed SQL rather than asking the user to prepare it.",
            "Include the preview and `data_table_id` when they matter for downstream work.",
        ],
    )

    tools = (catalog_tool, sql_tool, knowledge_tool)
    session_state = (
        create_kontext_session_state(context.attached_data_sources)
        if context.attached_data_sources
        else None
    )

    logger.info(f"SQL agent spec built successfully for project {project_id}")
    return AgentSpec(
        descriptor=SQL_AGENT_DESCRIPTOR,
        instructions=instructions,
        role=(
            "Write and execute read-only SQL (SELECT) to retrieve data; return executed results "
            "and reusable `data_table_id` values when downstream work needs them."
        ),
        tools=tools,
        session_state=session_state,
        add_session_state_to_context=session_state is not None,
        config=config,
    )
