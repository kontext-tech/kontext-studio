"""Shared instruction builders for agentic roles."""

from __future__ import annotations

import sys
from textwrap import dedent

from kontext.common.python_execution.policy import (
    DISTRIBUTION_TO_IMPORT_NAME,
    MANAGED_VENV_PACKAGES,
)


def dedupe_lines(*groups: list[str]) -> list[str]:
    """Return non-empty instruction lines with stable de-duplication."""
    seen: set[str] = set()
    result: list[str] = []
    for group in groups:
        for raw_line in group:
            line = raw_line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            result.append(line)
    return result


def configured_connection_workflow_line(*, audience: str = "this chat") -> str:
    """Shared guidance for chat-scoped default SQL connection handling."""
    return (
        "If `defaultCatalogConnectionId` appears in context, treat that connection "
        f"as already configured for {audience} and use it without asking the user "
        "for connection details first."
    )


def configured_connection_hard_stop_line(
    *,
    invalid_scope_clause: str = (
        "unless a tool explicitly reports that the configured scope is invalid or unavailable."
    ),
) -> str:
    """Shared hard stop for redundant connection questions."""
    return (
        "Do not ask the user for a connection ID, database name, or engine when "
        "the chat context already provides `defaultCatalogConnectionId` "
        f"{invalid_scope_clause}"
    )


def discovery_first_workflow_line(*, artifact: str = "analysis") -> str:
    """Shared guidance to prefer tool-driven discovery over premature questions."""
    return (
        f"For underspecified {artifact} requests, try catalog discovery and a first "
        "grounded SQL result before asking the user for table or column names."
    )


def clarify_after_discovery_line() -> str:
    """Shared guidance for when clarification is actually warranted."""
    return (
        "Ask a clarifying question only after discovery leaves multiple plausible "
        "sources or the required fields still cannot be resolved."
    )


def no_manual_workaround_line(
    *,
    task: str = "run SQL, export CSV, or stage intermediate files",
    capability: str = "our in-session tools can produce the needed result",
) -> str:
    """Shared guidance to avoid pushing tool-available work back to the user."""
    return f"Do not ask the user to manually {task} when {capability}."


def reusable_handoff_line() -> str:
    """Shared guidance for cross-agent handoff quality."""
    return "Prefer reusable IDs and data references over pasted previews for handoff."


def verify_claims_line(*, subject: str = "platform limitations") -> str:
    """Shared guidance so reported limitations get verified before being used.

    Members sometimes generalize their own toolset bounds ("persistence is not
    available to me") into platform-wide claims; a relayed claim that no tool
    contradicted once wrong costs the whole team its deliverable.
    """
    return (
        f"Do not claim {subject} unless a tool in this run returned that error; "
        "when a member reports a limitation, verify it with the relevant "
        "inspect or validation tool before treating it as a constraint or "
        "relaying it onward."
    )


def catalog_discovery_line(*, has_catalog_search: bool) -> str:
    """Tool-driven schema discovery guidance based on available catalog capabilities."""
    if has_catalog_search:
        return (
            'Prefer `search_catalog(query="...")` first for table and column discovery, '
            "then use `inspect_entity_columns` or listing tools to confirm the exact schema you need. "
            "Use `inspect_entities_columns(entities=[...])` to confirm several tables in one call, "
            'and `discover(query="...")` to search tables, curated knowledge, and documents together.'
        )
    return (
        "Use `list_namespaces`, `list_entities`, and `inspect_entity_columns` for table and column discovery. "
        "Use `inspect_entities_columns(entities=[...])` to inspect several tables in one call."
    )


def managed_python_environment_line() -> str:
    """State the pinned managed Python environment so agents report versions directly.

    The packages mirror ``MANAGED_VENV_PACKAGES`` (test-pinned against the
    managed venv), so this doubles as the sanctioned answer to version
    questions that ``sys``/``importlib`` cannot satisfy in-cell.
    """
    import_name_version = ", ".join(
        f"{DISTRIBUTION_TO_IMPORT_NAME.get(spec.split('==', 1)[0], spec.split('==', 1)[0])}"
        f" {spec.split('==', 1)[1]}"
        for spec in MANAGED_VENV_PACKAGES
    )
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return (
        f"Managed Python environment: CPython {python_version} with {import_name_version}. "
        "Report versions from this line, or capture them in-cell with `platform.python_version()` "
        "and package dunder reads (e.g. `pandas.__version__`); `sys` and `importlib` imports "
        "stay sandbox-blocked, so never spend rounds trying them."
    )


def catalog_reliability_line(*, has_catalog_search: bool) -> str:
    """Recovery guidance after failed discovery or SQL execution."""
    if has_catalog_search:
        return (
            "If a query fails, use `search_catalog` or `inspect_entity_columns` "
            "to find the correct naming or column details."
        )
    return "If a query fails, use `list_entities` or `inspect_entity_columns` to find the correct naming or column details."


def batch_execution_line() -> str:
    """Shared guidance to prefer one batch tool call over repeated single calls."""
    return (
        "When you already know several statements or IDs to process, prefer the batch "
        "tool (`execute_sql_batch`, `validate_sql_batch`, `inspect_entities_columns`, "
        "`get_charts`, `get_notebooks`, `get_blocks`, `discover`) over repeating the "
        "single-item tool once per item."
    )


def batch_sampling_line() -> str:
    """Shared guidance to sample several candidate tables in one call."""
    return (
        "When profiling several candidate tables or views, sample them with one "
        "`sample_records_batch` call instead of running `sample_records` per table."
    )


def complex_analysis_routing_line() -> str:
    """Shared guidance for notebook-first routing of ML and complex analysis."""
    return (
        "Route these requests to Notebook Agent as the deliverable: machine learning "
        "(training, evaluation, prediction, feature engineering), statistical analysis "
        "beyond a single aggregate (hypothesis tests, distributions, correlation or "
        "cohort studies), and multi-step dependent analysis (clean-and-transform chains, "
        "iterative modeling). Reproducibility requests ('report', 'model', or 'rerun for "
        "me') always qualify."
    )


def inline_fast_path_line() -> str:
    """Shared guidance to keep simple requests on the fast inline path."""
    return (
        "Keep the fast path fast: single lookups stay with SQL Agent, and a single "
        "aggregated visual stays SQL + Chart through a reusable `data_table_id`; "
        "neither becomes a notebook."
    )


def ambiguous_routing_line() -> str:
    """Shared tiebreaker when work could be one query or a notebook workflow."""
    return (
        "If a request could be one query or multi-step analysis, prefer Notebook Agent: "
        "assembling scattered one-shot executions into a report afterwards is not "
        "possible, while trimming an over-scoped notebook is easy."
    )


def _format_section(title: str, lines: list[str]) -> str:
    body = "\n".join(f"- {line}" for line in dedupe_lines(lines))
    return f"**{title}**:\n{body}"


def build_role_instructions(
    *,
    intro: str,
    context_summary: str,
    attached_data_summary: str | None = None,
    owned_actions: list[str],
    workflow: list[str],
    hard_stops: list[str],
    response_contract: list[str] | None = None,
) -> str:
    """Build a compact instruction set with consistent sections."""

    sections = [
        intro.strip(),
        f"**Context**:\n{context_summary}",
    ]
    if attached_data_summary:
        sections.append(f"**Attached Data**:\n{attached_data_summary}")
    sections.extend(
        [
            _format_section("Owned Actions", dedupe_lines(owned_actions)),
            _format_section("Required Workflow", dedupe_lines(workflow)),
            _format_section("Hard Stops", dedupe_lines(hard_stops)),
        ]
    )
    if response_contract:
        sections.append(_format_section("Response Contract", dedupe_lines(response_contract)))
    return dedent("\n\n".join(sections)).strip()
