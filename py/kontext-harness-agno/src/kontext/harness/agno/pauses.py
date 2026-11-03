"""Paused-run recovery for Agno external-execution (HITL) flows.

A paused run's `run_id` and `active_requirements` are persisted with the Agno
session so a later HTTP request can resume it after executing the required
tools externally.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from agno.agent import AgentSession, RunOutput
from agno.run.requirement import RunRequirement
from agno.run.team import TeamRunOutput
from agno.session.team import TeamSession
from kontext.schema import ToolCall

from .agent_types import AgnoAgentOrTeam


@dataclass
class AgnoResumeState:
    """Last known paused run for the in-process agent instance."""

    run_id: str | None = None
    requirements: list[RunRequirement] | None = None


def build_results_map(tool_outputs: Sequence[ToolCall]) -> dict[str, str]:
    """Map tool call IDs to the serialized external-execution results."""
    results_map: dict[str, str] = {}
    for output in tool_outputs or []:
        if not output.tool_call_id:
            continue
        if output.tool_call_error:
            results_map[output.tool_call_id] = _error_payload(output.tool_call_error)
        elif output.result is not None:
            if isinstance(output.result.root, str):
                results_map[output.tool_call_id] = output.result.root
            else:
                results_map[output.tool_call_id] = output.result.model_dump_json(
                    by_alias=True, exclude_unset=True
                )
        else:
            results_map[output.tool_call_id] = ""
    return results_map


def _error_payload(error: str) -> str:
    return json.dumps({"success": False, "error": error}, ensure_ascii=False)


def apply_tool_outputs(
    requirements: list[RunRequirement], tool_outputs: Sequence[ToolCall]
) -> None:
    """Attach external-execution results to matching Agno run requirements."""
    results_map = build_results_map(tool_outputs)
    for req in requirements:
        if (
            req.needs_external_execution
            and req.tool_execution
            and req.tool_execution.tool_call_id in results_map
        ):
            req.set_external_execution_result(results_map[req.tool_execution.tool_call_id])


def _resume_state_from_run(
    run: RunOutput | TeamRunOutput,
) -> AgnoResumeState | None:
    """Build the resume state for a run that is paused with active requirements."""
    if not run.is_paused or not run.active_requirements:
        return None
    return AgnoResumeState(run_id=run.run_id, requirements=list(run.active_requirements))


async def recover_paused_run(
    agent: AgnoAgentOrTeam,
    *,
    session_id: str | None,
    tool_outputs: Sequence[ToolCall] | None,
    run_id: str | None = None,
    logger: Any,
) -> AgnoResumeState | None:
    """Find the paused run (run_id + active_requirements) from Agno's persisted session.

    Relies on Agno's built-in external-execution persistence: a paused run's
    active requirements are stored on the RunOutput and persisted in the session.
    """
    log = logger
    if not session_id:
        log.debug("recover_paused_run: no session_id provided")
        return None

    # Use synchronous get_session to bypass broken aget_session in Agno
    try:
        if agent.db:
            # Run sync DB operation in thread pool to avoid blocking event loop
            session = await asyncio.to_thread(agent.get_session, session_id=session_id)
        else:
            session = None

        if session:
            log.debug(f"recover_paused_run: loaded session {session_id}")
        else:
            log.warning(f"recover_paused_run: session {session_id} not found")
            return None
    except Exception as e:
        log.warning(f"Failed to load Agno session {session_id}: {e}", exc_info=True)
        return None

    if not isinstance(session, AgentSession | TeamSession):
        log.warning(f"recover_paused_run: unexpected session type: {type(session)}")
        return None

    is_team_session = isinstance(session, TeamSession)

    # AgentSession stores RunOutput; TeamSession stores TeamRunOutput plus member entries.
    raw_runs = session.runs or []
    runs: list[RunOutput | TeamRunOutput] = (
        [r for r in raw_runs if isinstance(r, TeamRunOutput)]
        if is_team_session
        else [r for r in raw_runs if isinstance(r, RunOutput)]
    )
    log.debug(f"recover_paused_run: session has {len(runs)} runs")
    if not runs:
        return None

    tool_call_ids = {tc.tool_call_id for tc in (tool_outputs or []) if tc.tool_call_id}
    log.debug(f"recover_paused_run: looking for tool_call_ids {tool_call_ids}")

    # If client provided run_id, find that specific run and return its requirements
    if run_id:
        fallback_run_found = False
        for run in reversed(runs):
            if run.run_id == run_id:
                fallback_run_found = True
                state = _resume_state_from_run(run)
                if state is not None:
                    log.info(
                        f"recover_paused_run: found client-specified run {run_id} "
                        f"with {len(state.requirements or [])} requirements"
                    )
                    return state
                log.warning(
                    f"recover_paused_run: run {run_id} found but not paused or has no requirements; "
                    "falling back to paused-run discovery"
                )
                break

        if not fallback_run_found:
            log.warning(
                "recover_paused_run: client-specified run %s not found in session; "
                "falling back to paused-run discovery",
                run_id,
            )

    for run in reversed(runs):
        state = _resume_state_from_run(run)
        if state is None:
            continue

        if tool_call_ids:
            matches = False
            for req in run.active_requirements or []:
                tool_exec = req.tool_execution
                if tool_exec is None:
                    continue
                if not req.needs_external_execution:
                    continue
                if tool_exec.tool_call_id in tool_call_ids:
                    log.debug(f"recover_paused_run: matched tool_call_id {tool_exec.tool_call_id}")
                    matches = True
                    break
            if not matches:
                log.debug(f"recover_paused_run: run {run.run_id} has no matching tool_call_ids")
                continue

        log.info(
            f"recover_paused_run: found paused run {run.run_id} "
            f"with {len(state.requirements or [])} requirements"
        )
        return state

    # Fallback: most recent paused run, even if we can't match tool_call_ids
    for run in reversed(runs):
        state = _resume_state_from_run(run)
        if state is not None:
            log.info(
                f"recover_paused_run: fallback to paused run {run.run_id} "
                f"with {len(state.requirements or [])} requirements"
            )
            return state

    log.warning(f"recover_paused_run: no paused runs found in session {session_id}")
    return None
