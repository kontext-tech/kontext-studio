from __future__ import annotations

import json

import pytest

from kontext.agent import AgentKind, FrameworkToolkit, InMemorySessionPersistence
from kontext.agentic.adapters import AgentCreationContext
from kontext.agentic.blueprints.chart_agent import build_chart_spec
from kontext.agentic.blueprints.notebook_agent import build_notebook_spec
from kontext.agentic.blueprints.python_agent import build_python_spec
from kontext.agentic.blueprints.sql_agent import build_sql_spec
from kontext.agentic.blueprints.team import build_coordinator_spec
from kontext.agentic.tools.notebook_tool import NotebookTools
from kontext.agentic.tools.python_tool import NotebookPythonTools
from kontext.agentic.utils import AgentConfigBuilder
from kontext.common.contracts import AgentConfig, ModelRuntime, ResolvedModelConfig
from kontext.schema import (
    AttachedDataSource,
    AttachedDataTable,
    FileFormatType,
)


def _sample_config() -> AgentConfig:
    return AgentConfig(default_sample_limit=3, sql_dialect="DuckDB")


def _model_runtime() -> ModelRuntime:
    return ModelRuntime(
        binding=ResolvedModelConfig(
            canonical_model_id="openai/gpt-4.1-mini",
            source_type="user_managed",
            adapter_type="openai_native",
            connection_kind="openai",
            display_name="Test",
            provider_model_name="gpt-4.1-mini",
        )
    )


def _context(sample_project, mock_service_provider, **overrides) -> AgentCreationContext:
    values = {
        "config": _sample_config(),
        "project": sample_project,
        "runtime_provider": mock_service_provider,
        "model": _model_runtime(),
        "session_persistence": InMemorySessionPersistence(),
        "session_id": "session-id",
        "user_id": "user-id",
        "query_session_id": "query-session-id",
    }
    values.update(overrides)
    return AgentCreationContext(**values)


def _tool_names(spec) -> list[str]:
    names: list[str] = []
    for tool in spec.tools:
        if isinstance(tool, FrameworkToolkit):
            names.append(type(tool).__name__)
        else:
            names.append(getattr(tool, "__name__", type(tool).__name__))
    return names


def _instructions(spec) -> str:
    return spec.instructions


@pytest.mark.asyncio
async def test_sql_spec_has_neutral_identity(sample_project, mock_service_provider) -> None:
    spec = await build_sql_spec(_context(sample_project, mock_service_provider))

    assert spec.descriptor.id is AgentKind.SQL
    assert not spec.members
    assert _tool_names(spec) == ["CatalogTools", "SqlTools", "KnowledgeTools"]


@pytest.mark.asyncio
async def test_coordinator_spec_composes_specialists_by_members(
    sample_project, mock_service_provider, monkeypatch
) -> None:
    monkeypatch.setattr(
        AgentConfigBuilder, "with_task_profile", staticmethod(lambda config, **_kwargs: config)
    )
    attached_data_sources = [
        AttachedDataSource(
            file_id="11111111-1111-4111-8111-111111111111",
            file_name="Financial Sample.xlsx",
            file_type=FileFormatType.EXCEL,
            tables=[
                AttachedDataTable(
                    entity_id="22222222-2222-4222-8222-222222222222",
                    namespace_name="bronze",
                    entity_name="Financial_Sample_Sheet1",
                    row_count=700,
                    column_names=["Segment", "Country", "Product"],
                )
            ],
        )
    ]

    spec = await build_coordinator_spec(
        _context(
            sample_project,
            mock_service_provider,
            attached_data_sources=attached_data_sources,
        )
    )

    assert spec.descriptor.id is AgentKind.COORDINATOR
    assert spec.members
    assert [member.descriptor.id for member in spec.members] == [
        AgentKind.SQL,
        AgentKind.CHART,
        AgentKind.NOTEBOOK,
        AgentKind.PYTHON,
    ]
    assert spec.share_member_interactions is True
    assert spec.add_member_history is True
    assert spec.persist_member_responses is True

    instructions = _instructions(spec)
    assert "Notebook Agent owns notebook mutation, notebook Python execution" in instructions
    assert "Before chart, notebook, or downstream artifact work" in instructions
    assert (
        "For underspecified chart, notebook, or analysis requests that depend on query results"
        in instructions
    )
    assert (
        "Route notebook creation, notebook updates, Python block execution, embedded charts, and artifact imports"
        in instructions
    )
    assert (
        "Notebook Agent executes its own Python blocks via `execute_python_code(notebook_id, block_id)`"
        in instructions
    )
    assert "`inspect_notebook_python_state(notebook_id)`" in instructions
    assert "Reserve Python for analysis that SQL cannot express" in instructions
    assert "For grouped or aggregated chart requests" in instructions
    assert (
        "Present the delivered artifacts, their identifiers, and the grounded answer"
        in instructions
    )
    assert "Prefer reusable IDs and data references over pasted previews" in instructions
    assert "Do not ask the user to manually run SQL, export CSV" in instructions
    assert (
        "Ask a clarifying question only after discovery leaves multiple plausible sources"
        in instructions
    )
    assert (
        "Do not claim platform limitations unless a tool in this run returned that error"
        in instructions
    )
    assert _tool_names(spec) == ["ProjectTools"]


@pytest.mark.asyncio
async def test_coordinator_routes_complex_analysis_to_notebooks(
    sample_project, mock_service_provider, monkeypatch
) -> None:
    monkeypatch.setattr(
        AgentConfigBuilder, "with_task_profile", staticmethod(lambda config, **_kwargs: config)
    )
    spec = await build_coordinator_spec(_context(sample_project, mock_service_provider))
    instructions = _instructions(spec)

    assert (
        "Route these requests to Notebook Agent as the deliverable: machine learning"
        in instructions
    )
    assert "neither becomes a notebook" in instructions
    assert (
        "If a request could be one query or multi-step analysis, prefer Notebook Agent"
        in instructions
    )
    assert (
        "anything matching the complex-analysis routing triggers must go to Notebook Agent"
        in instructions
    )
    assert "Do not complete notebook-bound analysis with session-scoped Python" in instructions
    assert (
        "present the `notebook_id` and the executed block outputs as the deliverable"
        in instructions
    )


@pytest.mark.asyncio
async def test_sql_spec_instructions_require_durable_reruns_for_downstream_handoffs(
    sample_project, mock_service_provider
) -> None:
    spec = await build_sql_spec(_context(sample_project, mock_service_provider))
    instructions = _instructions(spec)

    assert (
        "Prefer an existing reusable `data_table_id` when one already fits the task" in instructions
    )
    assert (
        "If a request names a business concept like customers, orders, revenue, or sessions"
        in instructions
    )
    assert (
        'Prefer `search_catalog(query="...")` first for table and column discovery' in instructions
    )
    assert "Rerun or persist SQL yourself to obtain a reusable `data_table_id`" in instructions
    assert "Do not ask the user to manually run SQL, export CSV, or persist results" in instructions
    assert (
        "Ask a clarifying question only after discovery leaves multiple plausible sources"
        in instructions
    )
    assert "Do not use SQL metadata statements such as `SHOW TABLES`" in instructions
    assert "return a reusable `data_table_id` produced from executed SQL" in instructions


@pytest.mark.asyncio
async def test_sql_spec_instructions_expose_active_catalog_scope(
    sample_project, mock_service_provider
) -> None:
    spec = await build_sql_spec(
        _context(
            sample_project,
            mock_service_provider,
            catalog_connection_id="550e8400-e29b-41d4-a716-446655440000",
            default_namespace="sales",
            default_entity_id="550e8400-e29b-41d4-a716-446655440001",
            engine_type="sqlserver",
        )
    )
    instructions = _instructions(spec)

    assert "Active SQL Scope:" in instructions
    assert '"defaultCatalogConnectionId": "550e8400-e29b-41d4-a716-446655440000"' in instructions
    assert "treat that connection as already configured for this chat" in instructions
    assert "Do not ask the user for a connection ID" in instructions


@pytest.mark.asyncio
async def test_chart_spec_instructions_keep_sql_persistence_internal(
    sample_project, mock_service_provider
) -> None:
    spec = await build_chart_spec(_context(sample_project, mock_service_provider))
    instructions = _instructions(spec)

    assert "session-resolvable data handle" in instructions
    assert "executed reusable result from SQL Agent" in instructions
    assert "instead of asking the user for schema details first" in instructions
    assert (
        "Ask a clarifying question only after discovery leaves multiple plausible sources"
        in instructions
    )
    assert (
        "Do not ask the user to manually run SQL, export CSV, or persist query results"
        in instructions
    )
    assert (
        "Do not claim platform limitations unless a tool in this run returned that error"
        in instructions
    )


@pytest.mark.asyncio
async def test_python_spec_can_disable_sql_tools(
    sample_project, mock_service_provider, monkeypatch
) -> None:
    monkeypatch.setattr(
        AgentConfigBuilder, "with_task_profile", staticmethod(lambda config, **_kwargs: config)
    )

    spec = await build_python_spec(
        _context(sample_project, mock_service_provider),
        include_sql_tools=False,
    )
    instructions = _instructions(spec)

    assert _tool_names(spec) == ["CatalogTools", "PythonTools"]
    assert "Do NOT call `execute_sql` again" in instructions
    assert "Never rebuild SQL results with hard-coded `pd.DataFrame(...)` literals" in instructions
    assert "For standalone analysis, execute the final code" in instructions
    assert "Notebook Agent owns notebook block creation and execution" in instructions
    assert "Notebook Agent runs its own blocks" in instructions
    assert "notebook-bound analysis belongs to Notebook Agent" in instructions
    assert "Do not use session-only helpers" in instructions
    assert (
        'Prefer `search_catalog(query="...")` first for table and column discovery' in instructions
    )
    assert "Code you draft for a notebook must run end-to-end from a fresh kernel" in instructions
    assert "Session-scoped scripts may use `await kontext.execute_sql(" in instructions
    assert "Code you draft for a notebook must stay portable" in instructions
    assert "every referenced table must exist as a SQL/data table block first" in instructions
    assert "do not ask it to create a block for you to execute" in instructions
    assert "Python execution is serialized per session" in instructions
    assert "never run two Python scripts in parallel" in instructions
    assert "Do not use SQL metadata statements such as `SHOW TABLES`" in instructions
    assert "do NOT create, edit, delete, or run notebook blocks" in instructions

    python_toolkit = next(tool for tool in spec.tools if tool.__class__.__name__ == "PythonTools")
    tool_names = [tool.__name__ for tool in python_toolkit.get_tool_callables()]
    assert "execute_python_code" not in tool_names
    assert "execute_python_script" in tool_names


@pytest.mark.asyncio
async def test_notebook_spec_python_instructions_require_handoff_and_persistence(
    sample_project, mock_service_provider, monkeypatch
) -> None:
    monkeypatch.setattr(
        AgentConfigBuilder, "with_task_profile", staticmethod(lambda config, **_kwargs: config)
    )

    spec = await build_notebook_spec(
        _context(sample_project, mock_service_provider),
        allow_python=True,
    )
    instructions = _instructions(spec)

    assert (
        "Create or update the Python block, then execute it with "
        "`execute_python_code(notebook_id, block_id)` before finalizing" in instructions
    )
    assert (
        "`execute_python_code` runs an existing block and records its execution state"
        in instructions
    )
    assert "matching SQL or data table context" in instructions
    assert (
        "Notebook Agent owns the notebook end-to-end, including running its Python blocks"
        in instructions
    )
    assert "Do not substitute session-scoped Python for notebook deliverable code" in instructions
    assert "Confirm each Python block's execution state" in instructions
    assert (
        "rely on the SQL-produced aggregated `data_table_id` for the chart input instead of drafting "
        "Python blocks" in instructions
    )
    assert (
        "Edit list and summary list items with `edit_list_block(notebook_id, block_id, items, style)`"
        in instructions
    )
    assert "session-scoped script output alone is not notebook execution state" in instructions

    callable_names = _spec_callable_names(spec)
    assert "execute_python_code" in callable_names
    assert "add_python" in callable_names
    assert "execute_python_script" not in callable_names


@pytest.mark.asyncio
async def test_notebook_spec_without_python_omits_python_capability(
    sample_project, mock_service_provider
) -> None:
    """allow_python=False must gate both the tools and their prompt guidance."""
    spec = await build_notebook_spec(_context(sample_project, mock_service_provider))
    instructions = _instructions(spec)

    assert "execute_python_code" not in instructions
    assert "add_python" not in _spec_callable_names(spec)
    assert "execute_python_code" not in _spec_callable_names(spec)


@pytest.mark.asyncio
async def test_notebook_spec_can_disable_charts(sample_project, mock_service_provider) -> None:
    """Chart tools are selectively composable; CRUD and data-table tools stay."""
    enabled = await build_notebook_spec(_context(sample_project, mock_service_provider))
    disabled = await build_notebook_spec(
        _context(sample_project, mock_service_provider),
        allow_charts=False,
    )

    enabled_names = _spec_callable_names(enabled)
    disabled_names = _spec_callable_names(disabled)

    assert "add_line_chart" in enabled_names
    assert "import_chart" in enabled_names
    for chart_tool in ("add_line_chart", "add_bar_chart", "add_stock_chart", "import_chart"):
        assert chart_tool not in disabled_names
    # Only the chart tools are gated: block content and CRUD stay exposed.
    for block_tool in ("add_paragraph", "add_data_table", "delete_blocks", "get_notebook"):
        assert block_tool in disabled_names

    disabled_instructions = _instructions(disabled)
    assert "Use `import_chart` for standalone chart reuse" not in disabled_instructions


def _spec_callable_names(spec) -> list[str]:
    names: list[str] = []
    for tool in spec.tools:
        if isinstance(tool, FrameworkToolkit):
            names.extend(callable_.__name__ for callable_ in tool.get_tool_callables())
    return names


@pytest.mark.asyncio
async def test_notebook_spec_shares_editor_lock_between_mutation_and_execution(
    sample_project, mock_service_provider, monkeypatch
) -> None:
    """Block edits and execution must serialize on the same notebook document."""
    monkeypatch.setattr(
        AgentConfigBuilder, "with_task_profile", staticmethod(lambda config, **_kwargs: config)
    )
    spec = await build_notebook_spec(
        _context(sample_project, mock_service_provider),
        allow_python=True,
    )

    notebook_tools = next(tool for tool in spec.tools if isinstance(tool, NotebookTools))
    python_tools = next(tool for tool in spec.tools if isinstance(tool, NotebookPythonTools))
    assert notebook_tools._editor_lock is python_tools._editor_lock


@pytest.mark.asyncio
async def test_agent_tool_schemas_stay_within_budget(
    sample_project, mock_service_provider, monkeypatch
) -> None:
    """Guard the prompt surface against silent schema re-bloat.

    Tool schemas dominate each agent turn far more than instructions; the
    budgets below are the regression line after replacing the typed block-edit
    and chart-update unions with server-validated flat payloads.
    """
    from kontext.agent import render_tool_schema

    monkeypatch.setattr(
        AgentConfigBuilder, "with_task_profile", staticmethod(lambda config, **_kwargs: config)
    )
    ctx = _context(sample_project, mock_service_provider)
    specs = {
        "coordinator": await build_coordinator_spec(ctx),
        "sql": await build_sql_spec(ctx),
        "chart": await build_chart_spec(ctx),
        "notebook": await build_notebook_spec(ctx, allow_python=True),
        "python": await build_python_spec(ctx, include_sql_tools=False),
    }
    budgets = {
        "coordinator": 2_000,
        "sql": 12_000,
        "chart": 15_000,
        "notebook": 30_000,
        "python": 5_000,
    }

    for name, spec in specs.items():
        total = 0
        for tool in spec.tools:
            if not isinstance(tool, FrameworkToolkit):
                continue
            for callable_ in tool.get_tool_callables():
                total += len(json.dumps(render_tool_schema(callable_, strict=False), default=str))
        assert total <= budgets[name], f"{name} tool schema grew to {total} chars"
