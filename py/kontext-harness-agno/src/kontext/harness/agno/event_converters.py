"""
Utilities for converting Agno RunOutputEvent to core SimpleRunEvent.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from kontext.agent.client_policy import (
    should_emit_reasoning_to_client,
    should_emit_tool_call_to_client,
    should_include_tool_call_details_for_client,
)
from kontext.agent.tools import (
    ToolResultParser,
    get_tool_meta,
    get_tool_meta_by_display_name,
)
from kontext.schema import (
    EventData,
    RunCompletedEventData,
    RunContentEventData,
    RunEvent,
    RunPausedEventData,
    RunStartedEventData,
    SimpleRunEvent,
    ToolCall,
    ToolCallCompletedEventData,
    ToolCallResult,
    ToolCallStartedEventData,
)

from .event_adapter import (
    INTERMEDIATE_RUN_CONTENT_EVENTS,
    REASONING_CONTENT_DELTA_EVENTS,
    REASONING_EVENTS,
    REASONING_STEP_EVENTS,
    RUN_CANCELLED_EVENTS,
    RUN_COMPLETED_EVENTS,
    RUN_CONTENT_COMPLETED_EVENTS,
    RUN_CONTENT_EVENTS,
    RUN_ERROR_EVENTS,
    RUN_OUTPUT_EVENTS,
    RUN_PAUSED_EVENTS,
    RUN_STARTED_EVENTS,
    TOOL_CALL_COMPLETED_EVENTS,
    TOOL_CALL_ERROR_EVENTS,
    TOOL_CALL_STARTED_EVENTS,
    AgnoEvent,
)

if TYPE_CHECKING:
    from agno.models.response import ToolExecution


class EventConverter:
    """
    Converts Agno RunOutputEvent to core SimpleRunEvent with proper tool result parsing.

    This converter can be configured to include or suppress ToolCall events
    (ToolCallStarted/ToolCallCompleted) in the output stream.
    """

    def __init__(self, emit_tool_call_events: bool = True, session_id: str | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.emit_tool_call_events = emit_tool_call_events
        self.session_id = session_id
        self.tool_parser = ToolResultParser()
        self._include_tool_call_details_for_client = should_include_tool_call_details_for_client()
        self._should_emit_reasoning = should_emit_reasoning_to_client()

    def _should_emit_tool_call_for_client(self, tool_name: str | None) -> bool:
        """Determine whether a given tool call should be sent to the client.

        Policy:
        - Local dev: emit all tool calls.
        - Non-local: emit only tool calls explicitly marked as user-visible in ToolMeta.
        """
        return should_emit_tool_call_to_client(tool_name)

    def to_simple_event(self, agno_event: AgnoEvent | Any) -> list[SimpleRunEvent]:
        """
        Convert an Agno RunOutputEvent directly to SimpleRunEvent NDJSON payloads.
        """
        return self._convert_event(agno_event)

    def _convert_event(self, agno_event: AgnoEvent | Any) -> list[SimpleRunEvent]:
        """Internal event conversion logic."""
        # Handle strings (e.g. when stream_events=False)
        if isinstance(agno_event, str):
            return [SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content=agno_event)]

        # Handle RunOutput (non-streaming result or final result)
        if isinstance(agno_event, RUN_OUTPUT_EVENTS):
            reasoning_content = (
                agno_event.reasoning_content if self._should_emit_reasoning else None
            )
            return [
                SimpleRunEvent(
                    event_type=RunEvent.RUNCOMPLETED,
                    content=agno_event.content,
                    reasoning=reasoning_content,
                    done=True,
                    event_data=EventData(
                        root=RunCompletedEventData(content_type=agno_event.content_type)
                    ),
                )
            ]

        # Map Agno event types to our simplified events
        if isinstance(agno_event, RUN_STARTED_EVENTS):
            event = SimpleRunEvent(
                event_type=RunEvent.RUNSTARTED,
                content="Agent started processing",
                event_data=EventData(
                    root=RunStartedEventData(
                        model=getattr(agno_event, "model", None),
                        model_selection_id=getattr(agno_event, "model_selection_id", None),
                        canonical_model_id=getattr(agno_event, "canonical_model_id", None),
                        adapter_type=getattr(agno_event, "adapter_type", None),
                        connection_kind=getattr(agno_event, "connection_kind", None),
                        session_id=self.session_id,
                    )
                ),
            )

        # IMPORTANT: RunContentEvent must be checked BEFORE falling back to custom/unknown
        # Agno's inheritance structure makes checking via isinstance(obj, RunContentEvent) reliable
        # provided we have the correct import.
        elif isinstance(agno_event, RUN_CONTENT_EVENTS):
            reasoning_content = (
                agno_event.reasoning_content if self._should_emit_reasoning else None
            )

            # If both content and visible reasoning are empty, suppress the event
            if not agno_event.content and not reasoning_content:
                return []

            event = SimpleRunEvent(
                event_type=RunEvent.RUNCONTENT,
                content=agno_event.content,
                reasoning=reasoning_content,
                event_data=EventData(
                    root=RunContentEventData(content_type=agno_event.content_type)
                ),
            )

        elif isinstance(agno_event, RUN_COMPLETED_EVENTS):
            event = SimpleRunEvent(
                event_type=RunEvent.RUNCOMPLETED,
                content=agno_event.content,
                done=True,
                reasoning=agno_event.reasoning_content if self._should_emit_reasoning else None,
                event_data=EventData(
                    root=RunCompletedEventData(content_type=agno_event.content_type)
                ),
            )

        elif isinstance(agno_event, RUN_ERROR_EVENTS):
            event = SimpleRunEvent(
                event_type=RunEvent.RUNERROR,
                content=agno_event.content,
                error_details=agno_event.content,
                done=True,
            )

        elif isinstance(agno_event, RUN_CANCELLED_EVENTS):
            event = SimpleRunEvent(
                event_type=RunEvent.RUNCANCELLED,
                content="Run was cancelled",
                error_details=agno_event.reason,
                done=True,
            )

        elif isinstance(agno_event, RUN_PAUSED_EVENTS):
            tool_calls = []
            if hasattr(agno_event, "active_requirements") and agno_event.active_requirements:
                for req in agno_event.active_requirements:
                    # Check if this is an external tool execution requirement
                    tool_exec = getattr(req, "tool_execution", None)
                    if tool_exec and getattr(tool_exec, "external_execution_required", False):
                        tool_calls.append(
                            ToolCall(
                                tool_call_id=getattr(tool_exec, "tool_call_id", None),
                                tool_name=getattr(tool_exec, "tool_name", None),
                                tool_args=getattr(tool_exec, "tool_args", None),
                            )
                        )

            event = SimpleRunEvent(
                event_type=RunEvent.RUNPAUSED,
                content="Run paused for external execution",
                done=False,
                event_data=EventData(
                    RunPausedEventData(
                        run_id=getattr(agno_event, "run_id", None), tool_calls=tool_calls
                    )
                ),
            )

        elif isinstance(agno_event, TOOL_CALL_STARTED_EVENTS):
            # Respect configuration: optionally suppress tool-call started events
            if not self.emit_tool_call_events:
                return []

            tool_obj = getattr(agno_event, "tool", None)
            tool_name = getattr(tool_obj, "tool_name", None)

            if not self._should_emit_tool_call_for_client(tool_name):
                return []

            event = SimpleRunEvent(
                event_type=RunEvent.TOOLCALLSTARTED,
                event_data=EventData(
                    root=ToolCallStartedEventData(
                        tool=(
                            self._convert_tool_execution_to_tool(
                                tool_obj, include_details=self._include_tool_call_details_for_client
                            )
                            if tool_obj
                            else None
                        )
                    )
                ),
            )

        elif isinstance(agno_event, TOOL_CALL_COMPLETED_EVENTS):
            tool_obj = getattr(agno_event, "tool", None)
            tool_name = getattr(tool_obj, "tool_name", None)
            parsed_result = self._parse_tool_execution_result(tool_obj) if tool_obj else None

            # Respect configuration: optionally suppress tool-call events
            if not self.emit_tool_call_events:
                return []

            # Non-local environments only emit tool-call events for tools marked as user-visible.
            if not self._should_emit_tool_call_for_client(tool_name):
                return []

            tool = (
                self._convert_tool_execution_to_tool(
                    tool_obj,
                    include_details=self._include_tool_call_details_for_client,
                    parsed_result=parsed_result,
                )
                if tool_obj
                else None
            )

            event = SimpleRunEvent(
                event_type=RunEvent.TOOLCALLCOMPLETED,
                event_data=EventData(root=ToolCallCompletedEventData(tool=tool)),
            )

            return [event]

        elif isinstance(agno_event, TOOL_CALL_ERROR_EVENTS):
            # Respect configuration: optionally suppress tool-call error events
            if not self.emit_tool_call_events:
                return []

            tool_obj = getattr(agno_event, "tool", None)
            tool_name = getattr(tool_obj, "tool_name", None)
            error_val = getattr(agno_event, "error", None)

            if not self._should_emit_tool_call_for_client(tool_name):
                return []

            tool = (
                self._convert_tool_execution_to_tool(
                    tool_obj, include_details=self._include_tool_call_details_for_client
                )
                if tool_obj
                else None
            )

            # If tool execution is missing but we have error info, create a minimal tool call
            if not tool and error_val:
                tool = ToolCall(tool_call_error=error_val, result=ToolCallResult(root=error_val))

            event = SimpleRunEvent(
                event_type=RunEvent.TOOLCALLCOMPLETED,
                error_details=error_val,
                event_data=EventData(root=ToolCallCompletedEventData(tool=tool)),
            )

        elif isinstance(agno_event, REASONING_EVENTS):
            # Respect policy for reasoning events
            if not self._should_emit_reasoning:
                return []

            # Map reasoning events to RunContent events for UI compatibility
            # The UI expects reasoning content to be delivered via RunContent events
            # with reasoning_content populated in the event data.
            reasoning_content = None

            if isinstance(agno_event, REASONING_CONTENT_DELTA_EVENTS):
                reasoning_content = agno_event.reasoning_content
            elif isinstance(agno_event, REASONING_STEP_EVENTS):
                # ReasoningStepEvent might have content
                reasoning_content = getattr(agno_event, "content", None)

            # If we have reasoning content, emit it as a RunContent event
            if reasoning_content:
                event = SimpleRunEvent(
                    event_type=RunEvent.RUNCONTENT,
                    content="",  # Empty main content
                    reasoning=reasoning_content,
                    event_data=EventData(root=RunContentEventData()),
                )
                return [event]

            return []

        elif isinstance(agno_event, RUN_CONTENT_COMPLETED_EVENTS):
            event = SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, done=False)

        elif isinstance(agno_event, INTERMEDIATE_RUN_CONTENT_EVENTS):
            event = SimpleRunEvent(
                event_type=RunEvent.RUNINTERMEDIATECONTENT,
                content=str(agno_event.content) if agno_event.content else None,
            )

        else:
            # Fallback for unknown event types
            event = SimpleRunEvent(
                event_type=RunEvent.CUSTOMEVENT, content=f"Event: {type(agno_event).__name__}"
            )

        return [event]

    def _convert_tool_execution_to_tool(
        self,
        tool_execution: ToolExecution,
        *,
        include_details: bool,
        parsed_result: ToolCallResult | None = None,
    ) -> ToolCall | None:
        """Convert Agno ToolExecution to our ToolCall model."""
        if not tool_execution:
            return None

        # Resolve tool metadata to check for policy overrides (external execution or explicit emit_result)
        is_external = False
        explicit_emit_result = False
        if tool_execution.tool_name:
            meta = get_tool_meta(tool_execution.tool_name) or get_tool_meta_by_display_name(
                tool_execution.tool_name
            )
            if meta:
                is_external = meta.external_execution
                explicit_emit_result = meta.emit_result

        # Determine display name
        display_name = self.tool_parser.get_display_name(tool_execution.tool_name)

        # Parse the result properly using ToolResultParser (handles side-loading)
        if parsed_result is None:
            parsed_result = self._parse_tool_execution_result(tool_execution)

        # Determine if there was an error by checking both the tool call error and the parsed result
        raw_tool_call_error = tool_execution.tool_call_error
        if isinstance(raw_tool_call_error, str) and raw_tool_call_error:
            error_message: str | None = raw_tool_call_error
        elif raw_tool_call_error:
            if isinstance(tool_execution.result, str) and tool_execution.result:
                error_message = tool_execution.result
            else:
                error_message = "Tool call failed"
        else:
            error_message = None

        # If the tool call succeeded but the parsed result indicates failure, mark it as an error
        if not error_message and parsed_result:
            try:
                if getattr(parsed_result.root, "success", True) is False:
                    error_message = (
                        getattr(parsed_result.root, "message", None)
                        or getattr(parsed_result.root, "error", None)
                        or "Tool call failed"
                    )
            except Exception:
                pass

        # Use the parsed result for the ToolCall payload, falling back to raw if parsing failed
        # and we are in a mode that includes details.
        # Note: we suppress results on error in production for security.
        final_result: ToolCallResult | None = None
        if (include_details or is_external or explicit_emit_result) and (
            not error_message or include_details
        ):
            if parsed_result:
                final_result = parsed_result
            elif tool_execution.result is not None:
                final_result = ToolCallResult(root=tool_execution.result)

        return ToolCall(
            tool_call_id=tool_execution.tool_call_id,
            tool_name=display_name,
            tool_args=tool_execution.tool_args
            if (include_details or is_external) and (not error_message or include_details)
            else None,
            tool_call_error=error_message,
            result=final_result,
        )

    def _parse_tool_execution_result(
        self, tool_execution: ToolExecution | None
    ) -> ToolCallResult | None:
        """Parse a raw tool result into the typed ToolCallResult expected by downstream events."""
        if not tool_execution or not tool_execution.tool_name or tool_execution.result is None:
            return None

        try:
            return self.tool_parser.parse_tool_result(
                tool_execution.tool_name,
                tool_execution.result,
                session_id=self.session_id,
            )
        except Exception:
            self.logger.warning("Failed to parse tool result for %s", tool_execution.tool_name)
            return None


def to_simple_event(
    agno_event: AgnoEvent | Any, emit_tool_call_events: bool = True, session_id: str | None = None
) -> list[SimpleRunEvent]:
    """
    Convert an Agno RunOutputEvent directly to SimpleRunEvent.

    Args:
        agno_event: The Agno event to convert
        emit_tool_call_events: When False, ToolCallStarted/Completed events are suppressed.
        session_id: Optional session ID to include in started events.

    Returns:
        A list of SimpleRunEvent items representing the converted event(s).

    Notes:
        - Backward compatible: callers not passing the flag get the previous behavior (emit tool calls).
        - Stateless usage: a fresh EventConverter is used per call to avoid shared mutable state.
    """
    return EventConverter(
        emit_tool_call_events=emit_tool_call_events, session_id=session_id
    ).to_simple_event(agno_event)
