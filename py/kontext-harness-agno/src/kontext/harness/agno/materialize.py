"""Agno materialization: neutral `AgentSpec` -> Agno `Agent`/`Team`.

Modules in this package are the only runtime modules allowed to import Agno;
composition is a field, not a type: a spec with members becomes a `Team`, a
leaf spec becomes an `Agent`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agno.agent import Agent
from agno.db.base import BaseDb
from agno.session import SessionSummaryManager
from agno.team import Team
from agno.tools import Toolkit
from kontext.agent import (
    AgentSpec,
    BaseAgenticSystem,
    FrameworkToolkit,
    collect_tools,
    create_kontext_session_state,
)
from kontext.agent.harness import AgentCreationContext
from kontext.agent.tools import (
    ToolRegistry,
    create_tool_registry,
    register_tools_from_callables,
)
from kontext.common.contracts import AgentConfig, ModelRuntime

from .agent_types import AgnoAgentOrTeam
from .models import create_model
from .storage import NeutralBackedDb
from .system import AgnoAgenticSystem
from .toolkits import adapt_tools_for_agno

# Agno's default session-summary prompt names the response keys with
# capitalized words ("Summary (str)", "Topics (Optional[List[str]])"), and
# models without native structured outputs echo those exact keys back, which
# fails pydantic validation (``summary Field required``) and logs
# "Failed to parse session summary response" on every summarized session.
# This prompt pins the exact lowercase keys the parser expects.
SESSION_SUMMARY_PROMPT = """\
Analyze the conversation between the user and the assistant, then return a \
JSON object with exactly these keys:
- "summary" (str): A concise summary of the session. Focus on important \
information that would be helpful for future interactions. Do not make \
anything up.
- "topics" (list of str, optional): The topics discussed in the session.

Keep the summary concise and to the point. Only include relevant information.
Return only the JSON object. The keys must be exactly "summary" and "topics" \
- lowercase, with no additional keys.
"""


def _session_summary_manager(config: AgentConfig) -> SessionSummaryManager | None:
    """Provide a summary manager whose prompt survives lenient JSON models."""
    if not config.summary:
        return None
    return SessionSummaryManager(session_summary_prompt=SESSION_SUMMARY_PROMPT)


def _build_agno_model(
    config: AgentConfig,
    *,
    model: ModelRuntime,
) -> Any:
    """Build the Agno model client from the resolved runtime and behaviour config."""
    return create_model(
        resolved_config=model.binding,
        credentials=model.credentials,
        reasoning_effort=config.reasoning_effort,
    )


def create_agno_agent(
    agent_id: str,
    name: str,
    tools: list[Any],
    instructions: str,
    config: AgentConfig,
    db: BaseDb,
    *,
    model: ModelRuntime,
    session_id: str | None = None,
    user_id: str | None = None,
    description: str | None = None,
    role: str | None = None,
    session_state: dict[str, Any] | None = None,
    add_session_state_to_context: bool = False,
) -> Agent:
    """Create a configured Agno Agent instance."""
    agno_model = _build_agno_model(config, model=model)

    return Agent(
        id=agent_id,
        name=name,
        description=description,
        session_id=session_id,
        user_id=user_id,
        model=agno_model,
        tools=adapt_tools_for_agno(tools),
        instructions=instructions,
        markdown=config.markdown,
        tool_call_limit=config.tool_call_limit,
        db=db,
        add_history_to_context=config.add_history_to_context,
        num_history_runs=config.num_history_runs,
        max_tool_calls_from_history=config.max_tool_calls_from_history,
        enable_session_summaries=config.summary,
        session_summary_manager=_session_summary_manager(config),
        add_session_summary_to_context=config.summary,
        compress_tool_results=True,
        telemetry=config.telemetry,
        debug_mode=config.debug_mode,
        role=role,
        session_state=session_state,
        add_session_state_to_context=add_session_state_to_context,
    )


def create_agno_team(
    team_id: str,
    name: str,
    members: list[AgnoAgentOrTeam],
    instructions: str,
    config: AgentConfig,
    db: BaseDb,
    *,
    model: ModelRuntime,
    session_id: str | None = None,
    user_id: str | None = None,
    description: str | None = None,
    share_member_interactions: bool = True,
    add_team_history_to_members: bool = False,
    persist_member_responses: bool = True,
    add_session_state_to_context: bool = True,
    tools: list[Any] | None = None,
    role: str | None = None,
    session_state: dict[str, Any] | None = None,
) -> Team:
    """Create a configured Agno Team instance."""
    agno_model = _build_agno_model(config, model=model)

    return Team(
        id=team_id,
        name=name,
        members=members,
        model=agno_model,
        instructions=instructions,
        description=description,
        session_id=session_id,
        user_id=user_id,
        db=db,
        tools=adapt_tools_for_agno(tools) if tools else None,
        # Session state configuration
        session_state=(
            session_state if session_state is not None else create_kontext_session_state()
        ),
        add_session_state_to_context=add_session_state_to_context,
        # Team specific configs
        add_history_to_context=config.add_history_to_context,
        add_team_history_to_members=add_team_history_to_members,
        num_history_runs=config.num_history_runs,
        max_tool_calls_from_history=config.max_tool_calls_from_history,
        enable_session_summaries=config.summary,
        session_summary_manager=_session_summary_manager(config),
        add_session_summary_to_context=config.summary,
        compress_tool_results=True,
        share_member_interactions=share_member_interactions,
        # Persisted member responses keep member HITL resumes working after
        # API round-trips: Agno otherwise falls back to member_run_id lookups,
        # which are brittle when the paused event surfaced a member run.
        store_member_responses=persist_member_responses,
        stream_member_events=True,  # Stream all member events for visibility
        debug_mode=config.debug_mode,
        telemetry=config.telemetry,
        role=role,
    )


def build_agno_tool_registry(spec: AgentSpec) -> ToolRegistry:
    """Build a deterministic Agno tool registry from a spec and its members."""
    registry = create_tool_registry(namespace="agno")
    callables: list[Callable[..., Any]] = []
    for tool in collect_tools([spec]):
        if isinstance(tool, FrameworkToolkit):
            callables.extend(tool.get_tool_callables())
        elif isinstance(tool, Toolkit):
            continue
        else:
            callables.append(tool)
    return register_tools_from_callables(callables, registry=registry)


def _materialize_spec(
    spec: AgentSpec,
    *,
    context: AgentCreationContext,
    project_id: str,
    db: BaseDb,
) -> AgnoAgentOrTeam:
    """Materialize a neutral spec (and any members) into Agno Agent/Team objects."""
    effective_config = spec.config or context.config
    if spec.members:
        members = [
            _materialize_spec(member, context=context, project_id=project_id, db=db)
            for member in spec.members
        ]
        return create_agno_team(
            team_id=f"{project_id}-{spec.descriptor.id}",
            name=spec.descriptor.name,
            members=members,
            instructions=spec.instructions,
            config=effective_config,
            db=db,
            model=context.model,
            session_id=context.session_id,
            user_id=context.user_id,
            description=spec.descriptor.description,
            share_member_interactions=spec.share_member_interactions,
            add_team_history_to_members=spec.add_member_history,
            persist_member_responses=spec.persist_member_responses,
            add_session_state_to_context=spec.add_session_state_to_context,
            tools=list(spec.tools) or None,
            role=spec.role,
            session_state=spec.session_state,
        )

    return create_agno_agent(
        agent_id=f"{project_id}-{spec.descriptor.id}",
        name=spec.descriptor.name,
        description=spec.descriptor.description,
        tools=list(spec.tools),
        instructions=spec.instructions,
        config=effective_config,
        db=db,
        model=context.model,
        session_id=context.session_id,
        user_id=context.user_id,
        role=spec.role,
        session_state=spec.session_state,
        add_session_state_to_context=spec.add_session_state_to_context,
    )


def materialize_agno_system(
    spec: AgentSpec,
    context: AgentCreationContext,
) -> BaseAgenticSystem:
    """Materialize a neutral spec into an Agno-backed agentic system.

    The Agno session store is neutral-backed (`NeutralBackedDb` over the
    platform persistence port): no per-project harness-owned file is created.
    """
    runtime_provider = context.runtime_provider
    project_id = context.project.id
    persistence = context.session_persistence
    db = NeutralBackedDb(persistence, label=f"{project_id}-agno")
    agno_agent = _materialize_spec(spec, context=context, project_id=project_id, db=db)
    return AgnoAgenticSystem(
        agno_agent,
        runtime_provider=runtime_provider,
        project_id=project_id,
        tool_registry=build_agno_tool_registry(spec),
        descriptor=spec.descriptor,
        persistence=persistence,
        session_db=db,
    )
