"""AI chat orchestration facade shared outside the API transport layer.

The concerns live in sibling modules; this class composes them:

- `kontext.agentic.chat_context` — context assembly + token-usage accounting
- `kontext.agentic.adapters` — blueprint resolution and agent-system composition
- `kontext.agentic.artifact_stream_events` — artifact event interception during streams
"""

import logging
from collections.abc import AsyncGenerator

from kontext.agent import BaseAgenticSystem, StreamOptions, get_tool_call_client_policy
from kontext.common.protocols import IChatSessionProtocol, RuntimeProviderProtocol
from kontext.data import ChatSessionTokenUsageDataService
from kontext.schema import (
    ChatMessage,
    ChatMessageType,
    ChatRequest,
    ChatSessionModel,
    ProjectModel,
    RunEvent,
    SimpleRunEvent,
    ToolCall,
)

from .adapters import create_agentic_system
from .artifact_stream_events import build_artifact_stream_events
from .chat_context import (
    build_agent_creation_context,
    build_run_state_store,
    record_session_token_usage,
)

logger = logging.getLogger(__name__)


class ChatHandler:
    """Create agents and stream chat responses for AI chat flows."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def stream_agent_response(
        self,
        agent: BaseAgenticSystem,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        *,
        emit_tool_call_events: bool = True,
        tool_outputs: list[ToolCall] | None = None,
        run_id: str | None = None,
        current_execution_run_id: str | None = None,
        chat_session_service: IChatSessionProtocol | None = None,
        token_usage_service: ChatSessionTokenUsageDataService | None = None,
    ) -> AsyncGenerator[str, None]:
        self._bind_current_execution_run_id(
            agent=agent,
            current_execution_run_id=current_execution_run_id,
        )
        known_artifact_ids: set[str] = set()
        if session_id and chat_session_service is not None:
            try:
                session_artifacts = await chat_session_service.list_artifacts(session_id)
                known_artifact_ids = {str(artifact.artifact_id) for artifact in session_artifacts}
            except Exception as exc:
                self.logger.warning(
                    "Failed to load initial artifact state for chat stream: %s",
                    exc,
                )

        try:
            async for event in agent.stream_response(
                message,
                session_id=session_id,
                user_id=user_id,
                options=StreamOptions(
                    tool_outputs=tool_outputs,
                    run_id=run_id,
                    emit_tool_call_events=emit_tool_call_events,
                ),
            ):
                yield (
                    event.model_dump_json(by_alias=True, exclude_none=True, ensure_ascii=True)
                    + "\n"
                )

                if event.event_type != RunEvent.TOOLCALLCOMPLETED:
                    continue

                event_data = getattr(event, "event_data", None)
                tool_call = getattr(getattr(event_data, "root", event_data), "tool", None)
                if tool_call is None:
                    continue

                if chat_session_service is None or session_id is None:
                    continue

                # Artifact enrichment must never take the chat response down:
                # an exception here would truncate the chunked HTTP response
                # (the browser surfaces it as ERR_INCOMPLETE_CHUNKED_ENCODING)
                # while the agent work continues server-side.
                try:
                    artifact_events = await build_artifact_stream_events(
                        session_id=session_id,
                        tool_call=tool_call,
                        chat_session_service=chat_session_service,
                        known_artifact_ids=known_artifact_ids,
                    )
                except Exception:
                    self.logger.exception(
                        "Failed to build artifact stream events for tool call %s; "
                        "continuing without artifact enrichment",
                        getattr(tool_call, "tool_call_id", None),
                    )
                    continue

                for artifact_event in artifact_events:
                    yield (
                        artifact_event.model_dump_json(
                            by_alias=True,
                            exclude_none=True,
                            ensure_ascii=True,
                        )
                        + "\n"
                    )
        except Exception:
            # Same contract as above: the agent itself reports failures through
            # the stream (RunErrorEvent), so anything escaping here is a bug in
            # the stream plumbing — surface it as a terminal run error event
            # instead of an abruptly aborted HTTP response.
            self.logger.exception("Chat stream pipeline error; emitting terminal run error")
            yield (
                SimpleRunEvent(
                    event_type=RunEvent.RUNERROR,
                    error_details="Chat stream interrupted; see server logs for details",
                ).model_dump_json(by_alias=True, exclude_none=True, ensure_ascii=True)
                + "\n"
            )

        if session_id and project_id:
            try:
                token_counts = agent.get_token_usage(session_id=session_id)
                if token_counts:
                    await record_session_token_usage(
                        agent_tokens=token_counts,
                        session_id=session_id,
                        project_id=project_id,
                        run_id=run_id,
                        chat_session_service=chat_session_service,
                        token_usage_service=token_usage_service,
                        logger_=self.logger,
                    )
            except Exception as exc:
                self.logger.error("Failed to update token usage: %s", exc)

    def _bind_current_execution_run_id(
        self,
        *,
        agent: BaseAgenticSystem,
        current_execution_run_id: str | None,
    ) -> None:
        """Expose the current execution run ID to tool calls."""
        agent.bind_current_execution_run_id(current_execution_run_id)

    def resolve_emit_tool_call_events(
        self,
        runtime_provider: RuntimeProviderProtocol,
        session: ChatSessionModel | None,
    ) -> bool:
        """Whether streamed runs should emit tool-call events at all.

        This is the client-visibility policy, not a model/agent config: the
        policy already maps ``off`` to "emit nothing" and every other mode to
        "emit, filtered per tool".
        """
        _ = (runtime_provider, session)
        return get_tool_call_client_policy() != "off"

    async def create_agent(
        self,
        chat_request: ChatRequest,
        runtime_provider: RuntimeProviderProtocol,
        project: ProjectModel,
        user_id: str | None = None,
        session: ChatSessionModel | None = None,
    ) -> BaseAgenticSystem:
        context = await self._build_agent_creation_context(
            chat_request, runtime_provider, project, user_id, session
        )
        return await create_agentic_system(
            context=context,
            agent_type=None,
        )

    async def load_session_messages(
        self,
        chat_request: ChatRequest,
        runtime_provider: RuntimeProviderProtocol,
        project: ProjectModel,
        user_id: str | None = None,
        session: ChatSessionModel | None = None,
    ) -> list[ChatMessage]:
        """Read persisted chat messages from the neutral run-state store.

        History is platform-owned (wire `ChatMessage` snapshots), so loading it
        requires no agent/harness materialization and no model-runtime
        resolution.
        """
        session_id = str(chat_request.session_id) if chat_request.session_id else None
        if not session_id:
            return []
        _ = (runtime_provider, user_id, session)
        records = await build_run_state_store(project.id).list_messages(session_id)
        messages = [ChatMessage.model_validate_json(record.message_json) for record in records]
        if messages and messages[0].type == ChatMessageType.SYSTEM:
            messages = messages[1:]
        return messages

    async def _build_agent_creation_context(
        self,
        chat_request: ChatRequest,
        runtime_provider: RuntimeProviderProtocol,
        project: ProjectModel,
        user_id: str | None = None,
        session: ChatSessionModel | None = None,
    ):
        return await build_agent_creation_context(
            chat_request,
            runtime_provider,
            project,
            user_id,
            session,
            logger_=self.logger,
        )


chat_handler = ChatHandler()

# Default workflow instance exposed through the package surface (formerly
# re-exported via `chat_streaming`, retired once the runtime-provider factory
# moved to the composition root).
DEFAULT_CHAT_AGENT_WORKFLOW = chat_handler
