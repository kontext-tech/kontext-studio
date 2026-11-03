"""Agno-backed agentic system facade.

`AgnoAgenticSystem` composes the split adapter modules:

- :mod:`.materialize` — neutral `AgentSpec` -> Agno `Agent`/`Team`
- :mod:`.run` — thread-offloaded run execution and event streaming
- :mod:`.pauses` — paused-run recovery for external execution (HITL)
- :mod:`.history` — persisted Agno sessions -> neutral `ChatMessage`

Materialization and conversion entry points live in their modules; this class
keeps the streaming runtime surface (`stream_response`, snapshot
materialization, token usage) and is what the harness adapter returns to
callers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from contextlib import suppress
from typing import Any

from agno.team import Team
from agno.utils.log import logger as agno_logger
from kontext.agent import (
    AgentContext,
    AgentDescriptor,
    BaseAgenticSystem,
    MessageRecord,
    SessionPersistence,
    SharedSessionStore,
    StreamOptions,
    create_kontext_session_state,
    unregister_session_context,
)
from kontext.agent import (
    link_artifact_to_session as helper_link_artifact_to_session,
)
from kontext.agent.streaming import EventBuffer
from kontext.agent.tools import ToolRegistry, create_tool_registry
from kontext.common.protocols import AgentRuntimeProviderProtocol
from kontext.schema import (
    ArtifactProvenance,
    ArtifactType,
    ChatMessage,
    CodeImageRefOutput,
    PythonExecutionResult,
    RunEvent,
    SimpleRunEvent,
    ToolCall,
)

from .agent_types import AgnoAgentOrTeam
from .history import agno_messages_to_chat_messages
from .pauses import AgnoResumeState
from .run import stream_agno_events
from .storage import NeutralBackedDb

__all__ = [
    "AgnoAgenticSystem",
    "AgnoResumeState",
]


class AgnoAgenticSystem(BaseAgenticSystem):
    """Agno-backed agentic system materialized from a neutral :class:`AgentSpec`."""

    def __init__(
        self,
        agent: AgnoAgentOrTeam,
        runtime_provider: AgentRuntimeProviderProtocol,
        project_id: str | None = None,
        tool_registry: ToolRegistry | None = None,
        descriptor: AgentDescriptor | None = None,
        persistence: SessionPersistence | None = None,
        session_db: NeutralBackedDb | None = None,
    ):
        definition = descriptor or type(self).agent_definition
        self.agent_definition = definition
        self.name = definition.name
        self.description = definition.description
        self.icon = definition.icon
        self.resume_state = AgnoResumeState()
        self.agent = agent
        self.project_id = project_id
        self.runtime_provider = runtime_provider
        self.tool_registry = tool_registry or create_tool_registry(namespace="agno")
        self.persistence = persistence
        self.session_db = session_db
        self.logger = agno_logger

    def bind_current_execution_run_id(self, current_execution_run_id: str | None) -> None:
        """Expose the active execution-run ID through shared Agno session state."""
        session_state = self.agent.session_state
        if not isinstance(session_state, dict):
            session_state = create_kontext_session_state()
            self.agent.session_state = session_state

        store = SharedSessionStore(session_state)
        store.bind_current_execution_run_id(current_execution_run_id)

    # ------------------------------------------------------------------
    # Neutral run-state persistence
    # ------------------------------------------------------------------

    async def _persist_pause_blob(self, *, session_id: str) -> None:
        """Flush the harness blob at the RUNPAUSED seam, before yielding.

        The blob carries everything pause recovery needs (paused run id,
        active requirements). Persisting it before the pause surfaces means a
        crash can never orphan a paused run. A persistence failure must never
        break the run: log and continue.
        """
        if self.session_db is None:
            return
        try:
            await self.session_db.persist_now(session_id)
        except Exception:
            self.logger.warning(
                "Failed to persist harness state for session %s", session_id, exc_info=True
            )

    async def _persist_message_snapshot(
        self, session_id: str, *, include_paused: bool = False
    ) -> None:
        """Replace the persisted conversation snapshot (full-snapshot write).

        Called once per turn after the stream's terminal event: completion,
        error, and pause streams all land here. `include_paused` opts into
        agno's otherwise-skipped paused runs so a paused turn still snapshots
        its partial conversation (mid-pause history reloads stay intact).
        """
        if self.persistence is None:
            return
        try:
            if not self.agent.get_session(session_id=session_id):
                return
        except Exception:
            return
        messages = self._read_harness_messages(session_id, include_paused=include_paused)
        records = [
            MessageRecord(
                session_id=session_id,
                message_json=message.model_dump_json(),
                seq=index,
            )
            for index, message in enumerate(messages)
        ]
        await self.persistence.replace_session_messages(session_id, records)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def stream_response(
        self,
        message: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        options: StreamOptions | None = None,
    ) -> AsyncGenerator[SimpleRunEvent, None]:
        """Stream the agent response; supports both fresh runs and pause resumes."""
        opts = options or StreamOptions()
        action_ctx = None
        try:
            action_ctx = AgentContext(
                project_id=self.project_id or "",
                session_id=session_id or getattr(self.agent, "session_id", "") or "",
            )
            persisted_session_id = action_ctx.session_id
            had_paused = False
            # Neutral-backed store: hydrate the working set for this turn so
            # agno's sync db reads on the event loop never block and history
            # serving is complete (A2 authority switch).
            if self.session_db is not None:
                await self.session_db.preload(persisted_session_id)

            async for event in stream_agno_events(
                agent=self.agent,
                message=message,
                session_id=session_id,
                user_id=user_id,
                context=action_ctx,
                resume_state=self.resume_state,
                tool_outputs=opts.tool_outputs,
                run_id=opts.run_id,
                emit_tool_call_events=opts.emit_tool_call_events,
                # Fixed buffering policy for all Agno-backed systems (small
                # content chunks are merged; disabled systems pass through).
                event_buffer=EventBuffer(max_buffer_size=128),
                process_tool_outputs=self._process_tool_output_artifacts,
                logger=self.logger,
            ):
                # Persist-before-surface: the harness blob (paused run +
                # requirements) must be durable before the client can observe
                # the pause.
                if event.event_type == RunEvent.RUNPAUSED:
                    had_paused = True
                    await self._persist_pause_blob(session_id=persisted_session_id)
                yield event

            # Post-stream snapshot: agno persists its session at run end, so
            # the authoritative conversation read happens after the loop.
            # Resume and completion runs snapshot the same way. A paused turn
            # snapshots its partial conversation too (agno's history read skips
            # paused runs by default, so opt in here), which keeps store-only
            # history intact for a reload while paused.
            await self._persist_message_snapshot(persisted_session_id, include_paused=had_paused)

        except Exception as e:
            self.logger.error(f"Streaming setup error: {e}")
            yield SimpleRunEvent(event_type=RunEvent.RUNERROR, error_details=str(e))
        finally:
            # Clean up the action context from the global registry to avoid memory leaks
            if action_ctx:
                unregister_session_context(action_ctx.session_id)

    # ------------------------------------------------------------------
    # Harness message materialization (snapshot writes)
    # ------------------------------------------------------------------

    def _read_harness_messages(
        self, session_id: str | None = None, *, include_paused: bool = False
    ) -> list[ChatMessage]:
        """Read messages from the harness session store (agno)."""
        if not self.agent:
            return []

        skip_statuses: list = [] if include_paused else None  # type: ignore[assignment]
        try:
            if isinstance(self.agent, Team):
                # Team history is read at team level. Agno filters member runs
                # out of this read (they are keyed by member id), so the
                # platform snapshot carries coordinator messages plus the
                # member's output as the delegation tool result — not
                # member-internal tool messages.
                agno_messages = self.agent.get_session_messages(
                    session_id=session_id,
                    skip_member_messages=False,
                    skip_statuses=skip_statuses,
                )
            else:
                agno_messages = self.agent.get_session_messages(
                    session_id=session_id, skip_statuses=skip_statuses
                )
            return agno_messages_to_chat_messages(
                agno_messages, registry=self.tool_registry, session_id=session_id
            )
        except Exception as e:
            self.logger.warning(f"Failed to get session messages: {e}", exc_info=True)
            return []

    def get_token_usage(self, session_id: str | None = None) -> tuple[int, int] | None:
        """Get token usage statistics for a specific session using Agno metrics."""
        if not self.agent or not session_id:
            return None

        try:
            metrics = self.agent.get_session_metrics(session_id=session_id)
            if not metrics:
                return None

            inbound = int(getattr(metrics, "input_tokens", 0) or 0)
            outbound = int(getattr(metrics, "output_tokens", 0) or 0)

            if inbound == 0 and outbound == 0:
                return None

            return (inbound, outbound)

        except Exception as e:
            self.logger.error(f"Failed to get token usage for session {session_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # Resume-time artifact linking
    # ------------------------------------------------------------------

    async def _process_tool_output_artifacts(
        self, session_id: str | None, tool_outputs: Sequence[ToolCall]
    ) -> None:
        """Extract and link artifacts (e.g. generated images) from tool outputs."""
        if not session_id:
            return

        for output in tool_outputs:
            if not output.result or not output.result.root:
                continue

            # ToolCallResult is a RootModel, .root is the actual result (e.g., PythonExecutionResult)
            result = output.result.root
            if not isinstance(result, PythonExecutionResult):
                continue

            # ``kontext.save_table`` outputs are already linked to the chat
            # artifact panel by the execution bridge, but only the harness owns
            # the agent session state that lets other team members resolve them.
            # HITL runs resume with client-provided results, so this is the only
            # server-side place the registration can happen.
            for saved in result.saved_tables or []:
                try:
                    await self._link_saved_table_artifact(
                        session_id=session_id,
                        artifact_id=saved.data_table_id,
                        title=saved.title or "Python Result",
                        row_count=saved.row_count,
                        provenance=result.provenance,
                    )
                except Exception:
                    self.logger.warning(
                        "Failed to register saved table %s in shared session state",
                        saved.data_table_id,
                        exc_info=True,
                    )

            for exec_output in result.outputs:
                # CodeExecutionOutput is also a RootModel; unwrap .root for ergonomics
                instance = exec_output.root if hasattr(exec_output, "root") else exec_output
                if not isinstance(instance, CodeImageRefOutput):
                    continue

                await self._link_image_artifact(
                    session_id=session_id,
                    artifact_id=instance.file_id,
                    title=instance.name or "Generated Image",
                    meta={
                        "mime_type": instance.mime_type,
                        "image_url": instance.image_url,
                        "tool_call_id": output.tool_call_id,
                        "name": instance.name,
                    },
                )

    async def _link_image_artifact(
        self,
        session_id: str | None,
        artifact_id: str,
        title: str,
        meta: dict[str, Any] | None = None,
    ) -> bool:
        """Link an image artifact to the chat session."""
        if not self.project_id:
            return False

        chat_session_service = (
            self.runtime_provider.get_chat_session_service() if self.runtime_provider else None
        )
        return await helper_link_artifact_to_session(
            project_id=self.project_id,
            session_id=session_id,
            artifact_id=artifact_id,
            artifact_type=ArtifactType.IMAGE,
            title=title,
            meta=meta,
            session_state=self.agent.session_state,
            chat_session_service=chat_session_service,
        )

    async def _link_saved_table_artifact(
        self,
        *,
        session_id: str | None,
        artifact_id: str,
        title: str,
        row_count: int | None,
        provenance: ArtifactProvenance | None,
    ) -> bool:
        """Register a ``kontext.save_table`` output for the whole team.

        Mirrors what the Python tools do when they run server-side: a shared
        artifact descriptor (title/row count) plus a chat-session artifact link
        carrying provenance. Both writes are idempotent, so re-registering a
        table the bridge already linked is safe.
        """
        if not self.project_id:
            return False

        session_state = getattr(self.agent, "session_state", None)
        store = SharedSessionStore.from_session_state(session_state)
        if store is not None:
            with suppress(Exception):
                store.upsert_artifact_descriptor(
                    artifact_id=artifact_id,
                    artifact_type=ArtifactType.DATATABLE,
                    title=title,
                    row_count=row_count,
                )

        chat_session_service = (
            self.runtime_provider.get_chat_session_service() if self.runtime_provider else None
        )
        return await helper_link_artifact_to_session(
            project_id=self.project_id,
            session_id=session_id,
            artifact_id=artifact_id,
            artifact_type=ArtifactType.DATATABLE,
            title=title,
            meta={"row_count": row_count} if row_count is not None else None,
            session_state=session_state,
            chat_session_service=chat_session_service,
            provenance=provenance,
        )
