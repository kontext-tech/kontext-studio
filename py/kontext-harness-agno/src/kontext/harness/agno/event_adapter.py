"""Agno-specific event adapter constants used by the framework-neutral converter."""

from __future__ import annotations

from agno.agent import (
    ReasoningCompletedEvent,
    ReasoningStartedEvent,
    ReasoningStepEvent,
    RunCancelledEvent,
    RunCompletedEvent,
    RunContentEvent,
    RunErrorEvent,
    RunOutputEvent,
    RunPausedEvent,
    RunStartedEvent,
    ToolCallCompletedEvent,
    ToolCallStartedEvent,
)
from agno.run.agent import (
    IntermediateRunContentEvent,
    ReasoningContentDeltaEvent,
    RunContentCompletedEvent,
    RunOutput,
    ToolCallErrorEvent,
)
from agno.run.agent import RunContentEvent as AgentRunContentEvent
from agno.run.team import IntermediateRunContentEvent as TeamIntermediateRunContentEvent
from agno.run.team import RunCancelledEvent as TeamRunCancelledEvent
from agno.run.team import RunCompletedEvent as TeamRunCompletedEvent
from agno.run.team import RunContentCompletedEvent as TeamRunContentCompletedEvent
from agno.run.team import RunContentEvent as TeamRunContentEvent
from agno.run.team import RunErrorEvent as TeamRunErrorEvent
from agno.run.team import RunStartedEvent as TeamRunStartedEvent
from agno.run.team import TeamRunOutput
from agno.run.team import ToolCallCompletedEvent as TeamToolCallCompletedEvent
from agno.run.team import ToolCallErrorEvent as TeamToolCallErrorEvent
from agno.run.team import ToolCallStartedEvent as TeamToolCallStartedEvent

AgnoEvent = (
    RunOutputEvent
    | RunStartedEvent
    | RunContentEvent
    | RunCompletedEvent
    | RunErrorEvent
    | RunPausedEvent
    | ToolCallStartedEvent
    | ToolCallCompletedEvent
    | ToolCallErrorEvent
    | ReasoningStartedEvent
    | ReasoningStepEvent
    | ReasoningCompletedEvent
    | ReasoningContentDeltaEvent
    | RunContentCompletedEvent
    | IntermediateRunContentEvent
    | TeamRunOutput
    | TeamRunStartedEvent
    | TeamRunContentEvent
    | TeamRunCompletedEvent
    | TeamRunErrorEvent
    | TeamRunCancelledEvent
    | TeamToolCallStartedEvent
    | TeamToolCallCompletedEvent
    | TeamToolCallErrorEvent
    | TeamIntermediateRunContentEvent
    | TeamRunContentCompletedEvent
)

RUN_OUTPUT_EVENTS = (RunOutput, TeamRunOutput)
RUN_STARTED_EVENTS = (RunStartedEvent, TeamRunStartedEvent)
RUN_CONTENT_EVENTS = (RunContentEvent, AgentRunContentEvent, TeamRunContentEvent)
RUN_COMPLETED_EVENTS = (RunCompletedEvent, TeamRunCompletedEvent)
RUN_ERROR_EVENTS = (RunErrorEvent, TeamRunErrorEvent)
RUN_CANCELLED_EVENTS = (RunCancelledEvent, TeamRunCancelledEvent)
RUN_PAUSED_EVENTS = (RunPausedEvent,)
TOOL_CALL_STARTED_EVENTS = (ToolCallStartedEvent, TeamToolCallStartedEvent)
TOOL_CALL_COMPLETED_EVENTS = (ToolCallCompletedEvent, TeamToolCallCompletedEvent)
TOOL_CALL_ERROR_EVENTS = (ToolCallErrorEvent, TeamToolCallErrorEvent)
REASONING_EVENTS = (
    ReasoningStartedEvent,
    ReasoningStepEvent,
    ReasoningCompletedEvent,
    ReasoningContentDeltaEvent,
)
REASONING_CONTENT_DELTA_EVENTS = (ReasoningContentDeltaEvent,)
REASONING_STEP_EVENTS = (ReasoningStepEvent,)
RUN_CONTENT_COMPLETED_EVENTS = (RunContentCompletedEvent, TeamRunContentCompletedEvent)
INTERMEDIATE_RUN_CONTENT_EVENTS = (IntermediateRunContentEvent, TeamIntermediateRunContentEvent)
