"""Chat agent context assembly and token-usage accounting.

Split out of the ChatHandler so each concern is independently testable and
the handler stays a thin orchestration facade:

- `build_agent_creation_context` — assembles the harness-neutral context
  (model runtime, attached data) used by agent creation.
- `build_run_state_store` — the one composition-owned run-state store factory,
  used by agent creation and history reads.
- `record_session_token_usage` — post-run token delta/cumulative persistence.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from kontext.agent.harness import AgentCreationContext
from kontext.chat import (
    get_chat_session_resource,
)
from kontext.common.constants import AgentTaskProfile
from kontext.common.contracts import ResolvedModelConfig
from kontext.common.utils.datetime_utils import utc_now
from kontext.common.utils.json_compat import model_validate_stored
from kontext.data import AgentRunStateDataService, ChatSessionDataService

from .model_runtime import build_model_runtime
from .utils import AgentConfigBuilder
from .utils.attachment_context import (
    build_attached_data_sources,
    build_attached_data_summary,
)

if TYPE_CHECKING:
    from kontext.common.protocols import IChatSessionProtocol, RuntimeProviderProtocol
    from kontext.data import ChatSessionTokenUsageDataService
    from kontext.schema import ChatRequest, ChatSessionModel, ProjectModel


logger = logging.getLogger(__name__)


def build_run_state_store(project_id: str | uuid.UUID) -> AgentRunStateDataService:
    """Build the platform-owned run-state store for a project.

    Composition owns the storage implementation; both agent creation and
    history reads go through this one factory.
    """
    return AgentRunStateDataService(str(project_id))


async def _load_session(
    chat_request: ChatRequest,
    runtime_provider: RuntimeProviderProtocol,
    log: logging.Logger,
) -> ChatSessionModel | None:
    """Resolve the chat session from the request (service first, resource fallback)."""
    if not chat_request.session_id:
        return None
    try:
        chat_session_service = runtime_provider.get_chat_session_service()
        if chat_session_service:
            return await chat_session_service.get_session(str(chat_request.session_id))
        return await get_chat_session_resource(
            project_id=uuid.UUID(str(chat_request.project_id)),
            chat_session_id=uuid.UUID(str(chat_request.session_id)),
        )
    except Exception as exc:
        log.warning("Failed to fetch session info: %s", exc)
        return None


async def _load_session_model_config(
    project_id: str, session: ChatSessionModel | None, log: logging.Logger
) -> ResolvedModelConfig | None:
    """Load the session's resolved model config."""
    if session is None:
        return None
    if session.model_selection_id:
        log.info(
            "Using model selection %s from session %s",
            session.model_selection_id,
            session.id,
        )
    try:
        raw_resolved_model_config = await ChatSessionDataService(
            project_id
        ).get_session_resolved_model_config_async(session.id)
        if raw_resolved_model_config:
            return model_validate_stored(ResolvedModelConfig, raw_resolved_model_config)
    except Exception as exc:
        log.warning(
            "Failed to load resolved model config for session %s: %s",
            session.id,
            exc,
        )
    return None


async def _load_attached_data(
    project_id: str, session: ChatSessionModel | None, log: logging.Logger
) -> tuple[list | None, str | None]:
    """Build the session's attached data sources and their summary."""
    if session is None:
        return None, None
    try:
        attachment_context = await ChatSessionDataService(project_id).get_attachment_context_async(
            session.id
        )
        attached_data_sources = build_attached_data_sources(attachment_context)
        return (
            attached_data_sources,
            build_attached_data_summary(attached_data_sources),
        )
    except Exception as exc:
        log.warning(
            "Failed to load attachment context for session %s: %s",
            session.id,
            exc,
        )
        return None, None


async def build_agent_creation_context(
    chat_request: ChatRequest,
    runtime_provider: RuntimeProviderProtocol,
    project: ProjectModel,
    user_id: str | None = None,
    session: ChatSessionModel | None = None,
    *,
    logger_: logging.Logger | None = None,
) -> AgentCreationContext:
    """Assemble the neutral context shared by agent creation and history reads."""
    log = logger_ or logger

    if session is None:
        session = await _load_session(chat_request, runtime_provider, log)
    binding = await _load_session_model_config(project.id, session, log)
    model = build_model_runtime(binding)

    # The resolved binding is authoritative for model identity; it is passed
    # through as-is and is never projected into the behaviour config.
    config = AgentConfigBuilder.from_runtime_provider(
        runtime_provider=runtime_provider,
        task_profile=AgentTaskProfile.CHAT_PLANNING,
        reasoning_effort=model.binding.reasoning_effort,
    )

    query_session_id = chat_request.query_session_id
    if not query_session_id and session:
        query_session_id = session.query_session_id

    attached_data_sources, attached_data_summary = await _load_attached_data(
        project.id, session, log
    )

    return AgentCreationContext(
        config=config,
        project=project,
        runtime_provider=runtime_provider,
        model=model,
        session_id=(str(chat_request.session_id) if chat_request.session_id else None),
        user_id=user_id,
        query_session_id=query_session_id,
        catalog_connection_id=(
            str(session.default_catalog_connection_id)
            if session and session.default_catalog_connection_id
            else None
        ),
        default_namespace=session.default_namespace if session else None,
        default_entity_id=(
            str(session.default_entity_id) if session and session.default_entity_id else None
        ),
        engine_type=session.engine_type if session else None,
        attached_data_sources=attached_data_sources,
        attached_data_summary=attached_data_summary,
        session_persistence=build_run_state_store(project.id),
    )


async def record_session_token_usage(
    *,
    agent_tokens: tuple[int, int],
    session_id: str,
    project_id: str,
    run_id: str | None,
    chat_session_service: IChatSessionProtocol | None,
    token_usage_service: ChatSessionTokenUsageDataService | None,
    logger_: logging.Logger | None = None,
) -> None:
    """Record post-run token usage as a delta plus cumulative session totals."""
    log = logger_ or logger
    try:
        tokens_inbound, tokens_outbound = agent_tokens

        # Get previous cumulative totals for delta calculation
        # NOTE: This read-then-write pattern has a theoretical race condition
        # if two requests process the same session concurrently. The validation
        # in record_token_usage_delta_async will detect and skip negative deltas,
        # but one request's delta may be lost. A complete fix would require
        # row-level locking (SELECT FOR UPDATE) or an atomic read-write operation.
        previous_inbound = 0
        previous_outbound = 0
        session_model_selection_id = None
        if chat_session_service is not None:
            try:
                previous_session = await chat_session_service.get_session(session_id)
                if previous_session is not None:
                    previous_inbound = previous_session.tokens_inbound or 0
                    previous_outbound = previous_session.tokens_outbound or 0
                    session_model_selection_id = previous_session.model_selection_id
            except Exception as exc:
                log.warning("Failed to get previous session for delta calculation: %s", exc)

        # Record time-series entry with delta
        if token_usage_service is not None:
            try:
                await token_usage_service.record_token_usage_delta_async(
                    chat_session_id=session_id,
                    project_id=project_id,
                    previous_inbound=previous_inbound,
                    previous_outbound=previous_outbound,
                    current_inbound=tokens_inbound,
                    current_outbound=tokens_outbound,
                    model_selection_id=session_model_selection_id,
                    job_run_id=run_id,
                    consumed_at=utc_now(),
                )
            except Exception as exc:
                log.warning("Failed to record token usage time-series entry: %s", exc)

        # Update cumulative totals on the chat session ("backward compatibility"
        # totals; the time-series entry above is the per-row record).
        if chat_session_service is not None:
            await chat_session_service.update_token_usage(
                session_id=session_id,
                tokens_inbound=tokens_inbound,
                tokens_outbound=tokens_outbound,
            )
    except Exception as exc:
        log.error("Failed to update token usage: %s", exc)
