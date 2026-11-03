"""
Notebook Agent blueprint for Kontext Agentic.

Builds a harness-neutral :class:`AgentSpec` for notebook operations. No
framework-specific code lives here.

Selective composition is flag-based (`allow_python`, `allow_charts`). Chart
and Python block-mutation tools share the notebook editor/lock and therefore
stay on `NotebookTools`; notebook Python execution is composed separately as
`NotebookPythonTools` because it does not touch the notebook editor.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from kontext.agent import AgentDescriptor, AgentKind, AgentSpec, FrameworkToolkit
from kontext.common.constants import AgentTaskProfile
from kontext.common.python_execution.policy import WHITELISTED_MODULES

from ..tools.kontext_toolkit import ToolkitScope
from ..tools.notebook_tool import NotebookTools
from ..tools.python_tool import NotebookPythonTools
from ..utils import AgentConfigBuilder
from ..utils.project_helpers import generate_project_summary
from .instructions import build_role_instructions, managed_python_environment_line

if TYPE_CHECKING:
    from ..adapters import AgentCreationContext

logger = logging.getLogger(__name__)


NOTEBOOK_AGENT_DESCRIPTOR = AgentDescriptor(
    id=AgentKind.NOTEBOOK,
    name="Notebook Agent",
    icon="NotebookOutlined",
    description=("Expert assistant for creating and managing computational notebooks."),
)


async def build_notebook_spec(
    context: AgentCreationContext, *, allow_python: bool = False, allow_charts: bool = True
) -> AgentSpec:
    """Build the neutral notebook agent specification.

    ``allow_python`` exposes python-block mutation/persistence tools, the
    notebook Python execution toolkit, and the Python workflow; ``allow_charts``
    exposes chart-creation tools and the chart workflow guidance.
    """
    project = context.project
    project_id = project.id
    runtime_provider = context.runtime_provider
    config = context.config
    agent_config = (
        AgentConfigBuilder.with_task_profile(
            config,
            runtime_provider=runtime_provider,
            task_profile=AgentTaskProfile.PYTHON_PLANNING,
            reasoning_effort=context.model.binding.reasoning_effort,
        )
        if allow_python
        else config
    )

    scope = ToolkitScope.from_context(context)
    # Shared by block mutation and execution so concurrent tool calls cannot
    # load/mutate/save the same notebook document at the same time.
    editor_lock = asyncio.Lock()
    notebook_tool = NotebookTools(
        scope=scope,
        allow_python_blocks=allow_python,
        allow_python_execution_persistence=allow_python,
        allow_charts=allow_charts,
        editor_lock=editor_lock,
    )
    tool_list: list[FrameworkToolkit] = [notebook_tool]
    if allow_python:
        # Execution is composed as its own toolkit: the notebook agent runs the
        # blocks it owns without gaining the standalone agent's session-scoped
        # Python execution or notebook structure tools.
        tool_list.append(NotebookPythonTools(scope=scope, editor_lock=editor_lock))

    logger.info(f"Using pre-loaded project context for {project_id}")
    project_context_summary = generate_project_summary(project)

    python_workflow: list[str] = []
    default_role = (
        "Create and update notebook artifacts (.notebook) with narrative, data tables, "
        "and embedded charts."
    )
    if allow_python:
        allowed_libraries = ", ".join(sorted(WHITELISTED_MODULES))
        default_role = (
            "Create and update notebook artifacts (.notebook) with narrative, data tables, "
            "embedded charts, and executed Python analysis blocks."
        )
        python_workflow = [
            "For machine-learning or complex-analysis requests, structure the notebook as a reproducible deliverable: data-table blocks for inputs with matching `data_id` context, stepwise Python analysis blocks whose code runs cleanly from a fresh kernel (own imports and inputs), and an evaluation or summary paragraph.",
            "Create or update the Python block, then execute it with `execute_python_code(notebook_id, block_id)` before finalizing; a block without execution state is not a finished deliverable.",
            "`notebook_id` is optional on notebook block tools: with exactly one notebook linked to this chat the server defaults to it (the result message names the resolved ID); pass `notebook_id` explicitly once more than one notebook is linked.",
            "Use `edit_python_code` for corrections to an existing Python block, then rerun it.",
            'If Python code uses `await kontext.load_data(...)`, ensure the notebook contains matching SQL or data table context first. Reference SQL block results by their alias (shown on the block, e.g. "df_1" or a renamed name like "sales_summary"); `data_id` values are also accepted but aliases keep code stable when SQL changes. An alias tracks the block\'s latest result across re-runs.',
            (
                "`execute_python_code` runs an existing block and records its execution state; a code "
                "override runs a draft without touching the notebook. Use `import_executed_python`/"
                "`persist_python_execution_state` only when attaching a specific managed run by ID."
            ),
            "`kontext.list_data_sources()` returns what `load_data` accepts: `data_sources['aliases']` are this notebook's SQL-block names (e.g. \"df_1\", \"sales_summary\") and `data_sources['data_ids']` are durable UUIDs; `await kontext.load_data(name)` then loads that table.",
            f"Supported libraries: {allowed_libraries}",
            managed_python_environment_line(),
        ]

    charts_workflow: list[str] = []
    if allow_charts:
        charts_workflow = [
            "Use `import_chart` for standalone chart reuse and `add_*_chart` for notebook-local visuals.",
            "For small changes to an existing notebook chart, update in place with `edit_chart_block(notebook_id, block_id, config)`; it keeps the block id and data reference (explicit `chartType` required) instead of delete-and-re-add.",
            "Prefer notebook-local charts unless the user explicitly asks for a standalone chart.",
            (
                "Chart tools render a data table as-is - they do not aggregate. When a chart request needs grouped "
                "or aggregated input (counts by country, averages per band), rely on the SQL-produced aggregated "
                "`data_table_id` for the chart input instead of drafting Python blocks."
            ),
        ]

    instructions = build_role_instructions(
        intro=f"You are Kontext, a Notebook Specialist for project `{project_id}`.",
        context_summary=project_context_summary,
        owned_actions=[
            "Create and update notebook structure and prose.",
            "Add data table blocks that reference external `data_table_id` values.",
            *(
                ["Create notebook-local charts or import existing `chart_id` artifacts."]
                if allow_charts
                else []
            ),
            *(
                ["Create, execute, and maintain notebook Python blocks and their execution state."]
                if allow_python
                else []
            ),
        ],
        workflow=[
            "Prefer updating an existing `notebook_id` over creating duplicates.",
            "Use `add_data_table` so the notebook stores a `data_ref` instead of copied SQL rows.",
            "Use `get_notebook_outline` to see a notebook's blocks cheaply, then `get_block`/`get_blocks` for only the blocks you need; avoid repeated `list_blocks` calls, which return full block payloads.",
            "Prefer in-place edits (`edit_block`, `edit_list_block`) for same-type changes; delete and re-add only when changing block type or removing content, because block IDs and Python execution state are identity-bearing.",
            "Use `delete_blocks(notebook_id, block_ids)` when removing several blocks instead of one `delete_block` call per block.",
            "Not every notebook needs Python - narrative, data tables, and charts are complete without Python blocks.",
            *charts_workflow,
            (
                "Edit list and summary list items with `edit_list_block(notebook_id, block_id, items, style)`; "
                "do not fall back to delete-and-re-add."
            ),
            *python_workflow,
        ],
        hard_stops=[
            (
                "Notebook Agent owns the notebook end-to-end, including running its Python blocks; "
                "do not route notebook block execution back to the coordinator or Python Agent."
            ),
            "Do not substitute session-scoped Python for notebook deliverable code; notebook deliverable code runs in notebook blocks.",
            "Never paste SQL preview rows into paragraph blocks, table blocks, or Python code when a `data_table_id` is available.",
            "Do not treat notebook Python as final until it carries execution state (verify with `get_block`/`get_blocks`); session-scoped script output alone is not notebook execution state.",
        ],
        response_contract=[
            "Confirm the `notebook_id` you created or updated.",
            *(
                ["Confirm each Python block's execution state and the `notebook_id` it belongs to."]
                if allow_python
                else []
            ),
        ],
    )

    logger.info(f"Notebook agent spec built successfully for project {project_id}")
    return AgentSpec(
        descriptor=NOTEBOOK_AGENT_DESCRIPTOR,
        instructions=instructions,
        role=default_role,
        tools=tuple(tool_list),
        config=agent_config,
    )
