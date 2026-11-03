"""
Python Agent blueprint for Kontext Agentic.

Builds a harness-neutral :class:`AgentSpec` for Python code generation,
validation, and managed execution. No framework-specific code lives here.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from kontext.agent import AgentDescriptor, AgentKind, AgentSpec
from kontext.common.constants import AgentTaskProfile
from kontext.common.python_execution.policy import WHITELISTED_MODULES

from ..tools.catalog_tool import CatalogTools
from ..tools.kontext_toolkit import ToolkitScope
from ..tools.python_tool import PythonTools
from ..tools.sql_tool import SqlTools
from ..utils import AgentConfigBuilder
from ..utils.project_helpers import generate_project_summary
from .instructions import (
    batch_execution_line,
    build_role_instructions,
    catalog_discovery_line,
    catalog_reliability_line,
    clarify_after_discovery_line,
    discovery_first_workflow_line,
    managed_python_environment_line,
    reusable_handoff_line,
)

if TYPE_CHECKING:
    from ..adapters import AgentCreationContext

logger = logging.getLogger(__name__)


PYTHON_AGENT_DESCRIPTOR = AgentDescriptor(
    id=AgentKind.PYTHON,
    name="Python Agent",
    icon="CodeOutlined",
    description=(
        "Machine learning engineer and Python expert specialized in code "
        "generation, validation, and managed execution."
    ),
)


async def build_python_spec(
    context: AgentCreationContext, *, include_sql_tools: bool = True
) -> AgentSpec:
    """Build the neutral Python agent specification."""
    project = context.project
    project_id = project.id
    runtime_provider = context.runtime_provider
    config = context.config
    agent_config = AgentConfigBuilder.with_task_profile(
        config,
        runtime_provider=runtime_provider,
        task_profile=AgentTaskProfile.PYTHON_PLANNING,
        reasoning_effort=context.model.binding.reasoning_effort,
    )

    scope = ToolkitScope.from_context(context)
    catalog_tool = CatalogTools(scope=scope)
    sql_tool = SqlTools(scope=scope) if include_sql_tools else None
    python_tool = PythonTools(scope=scope, include_notebook_execution=False)

    can_search_catalog = runtime_provider.get_catalog_index_service() is not None
    discovery_line = catalog_discovery_line(has_catalog_search=can_search_catalog)
    reliability_line = catalog_reliability_line(has_catalog_search=can_search_catalog)

    logger.info(f"Using pre-loaded project context for {project_id}")
    project_context_summary = generate_project_summary(project)
    allowed_libraries = ", ".join(sorted(WHITELISTED_MODULES))
    default_sample_limit = config.default_sample_limit
    workflow = [
        discovery_line,
        "Use the simplest discovery or inspection tool that answers the current question.",
        "Prefer catalog tools over ad-hoc SQL metadata queries when discovering tables or columns.",
        batch_execution_line(),
        discovery_first_workflow_line(artifact="analysis or Python"),
    ]
    if include_sql_tools:
        workflow.extend(
            [
                f"Use SQL tools for grounded retrieval and validation, keeping exploration queries small with sample sizes such as `{default_sample_limit}`.",
                "When downstream notebook or artifact work needs reusable query output, persist the executed SQL result through the SQL tools so the handoff uses a reusable `data_table_id`.",
            ]
        )
    else:
        workflow.extend(
            [
                "Use existing `data_table_id` values from SQL Agent or session state.",
                "Do NOT call `execute_sql` again when a suitable `data_table_id` already exists.",
                "Treat SQL Agent results as the source of truth for data inputs.",
            ]
        )
    workflow.extend(
        [
            "For standalone analysis, execute the final code in managed Python and return the referenced `data_table_id` and `execution_run_id` values.",
            managed_python_environment_line(),
            (
                "Notebook Agent owns notebook block creation and execution; do not create or run "
                "notebook blocks. Use session-scoped execution for standalone or exploratory analysis."
            ),
            "Use session-scoped Python execution to explore and iterate; notebook-bound analysis belongs to Notebook Agent.",
            "Code you draft for a notebook must run end-to-end from a fresh kernel: include its own imports and load its own inputs. Exploratory scripts may build on earlier session state.",
            "Session-scoped execution can use any current `DataTable` artifact already linked to the active chat session.",
            '`kontext` helpers are injected in the execution sandbox — call `kontext.list_data_sources()` (returns `{"aliases": [...], "data_ids": [...]}`) to see loadable names before guessing, and `await kontext.load_data("<name>")` to load; no import is needed, though `import kontext` also works.',
            'Session-scoped scripts may use `await kontext.execute_sql("SELECT ...")` for transient read-only SQL within the active chat query context.',
            'Persist a deliverable DataFrame with `saved = kontext.save_table(df, "name")`; `saved["dataTableId"]` is a durable, session-linked data table. Works in session scripts and notebook blocks (stamped as `agent_python` vs `notebook_run`). Do not save intermediate scratch frames.',
            'Code you draft for a notebook must stay portable: load inputs with `await kontext.load_data("<data_id_or_block_alias>")` and avoid session-only helpers such as `execute_sql`; every referenced table must exist as a SQL/data table block first — prefer the block alias SQL blocks show (e.g. "df_1", "sales_summary"), with `data_id` also accepted.',
            "Fix validation or execution errors and rerun until the code succeeds.",
            reliability_line,
        ]
    )

    instructions = build_role_instructions(
        intro=f"Python analysis specialist for project `{project_id}`.",
        context_summary=project_context_summary,
        owned_actions=[
            "Discover relevant data sources and validate Python plans.",
            "Execute managed Python against explicit `data_table_id` inputs.",
            "Return grounded conclusions with referenced `data_table_id` values and `execution_run_id`.",
        ],
        workflow=workflow,
        hard_stops=[
            "Notebook Agent owns notebook creation, block structure, and block execution; do NOT create, edit, delete, or run notebook blocks.",
            "Notebook Agent runs its own blocks; do not ask it to create a block for you to execute.",
            "Python execution is serialized per session; never run two Python scripts in parallel. Combine the work into one script or run the scripts in sequence.",
            "Do not use SQL metadata statements such as `SHOW TABLES`, `SHOW COLUMNS`, `DESCRIBE`, or `information_schema` for schema discovery when catalog tools are available.",
            "Do not use session-only helpers (`kontext.execute_sql`, hidden chat-session SQL context, session-only `data_id` values) in code intended for a notebook.",
            "Never rebuild SQL results with hard-coded `pd.DataFrame(...)` literals from previews.",
            "Never paste preview rows or literal table payloads into notebook prose, table blocks, or Python code.",
            reusable_handoff_line(),
            f"Stay within supported libraries: {allowed_libraries}",
        ],
        response_contract=[
            clarify_after_discovery_line(),
            "Return `execution_run_id` and the referenced `data_table_id` / block IDs when execution succeeds.",
            "When the code is intended for a notebook, return the final code and the `data_id` values it loads so Notebook Agent can create and run the block.",
            "Summarize conclusions using executed outputs and tool-grounded data only.",
        ],
    )

    tool_list = [catalog_tool, python_tool]
    if sql_tool is not None:
        tool_list.insert(1, sql_tool)

    logger.info(f"Python agent spec built successfully for project {project_id}")
    return AgentSpec(
        descriptor=PYTHON_AGENT_DESCRIPTOR,
        instructions=instructions,
        role=(
            "Draft, validate, and execute standalone Python analysis; keep code portable "
            "when it is intended for a Notebook Agent deliverable, use SQL-grounded data "
            "references, and iterate until clean."
        ),
        tools=tuple(tool_list),
        config=agent_config,
    )
