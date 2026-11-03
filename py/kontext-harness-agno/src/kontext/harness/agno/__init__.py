"""Agno-specific adapters and runtime exports."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    from .event_converters import EventConverter, to_simple_event
    from .factory import AgentCreationContext, AgnoAgentFrameworkAdapter
    from .materialize import build_agno_tool_registry, materialize_agno_system
    from .models import create_model
    from .system import AgnoAgenticSystem
    from .toolkits import AgnoToolkitAdapter, adapt_tools_for_agno


_EXPORTS = {
    "AgnoAgenticSystem": "kontext.harness.agno.system",
    "AgnoEvent": "kontext.harness.agno.event_adapter",
    "RUN_OUTPUT_EVENTS": "kontext.harness.agno.event_adapter",
    "RUN_STARTED_EVENTS": "kontext.harness.agno.event_adapter",
    "RUN_CONTENT_EVENTS": "kontext.harness.agno.event_adapter",
    "RUN_COMPLETED_EVENTS": "kontext.harness.agno.event_adapter",
    "RUN_ERROR_EVENTS": "kontext.harness.agno.event_adapter",
    "RUN_CANCELLED_EVENTS": "kontext.harness.agno.event_adapter",
    "RUN_PAUSED_EVENTS": "kontext.harness.agno.event_adapter",
    "TOOL_CALL_STARTED_EVENTS": "kontext.harness.agno.event_adapter",
    "TOOL_CALL_COMPLETED_EVENTS": "kontext.harness.agno.event_adapter",
    "TOOL_CALL_ERROR_EVENTS": "kontext.harness.agno.event_adapter",
    "REASONING_EVENTS": "kontext.harness.agno.event_adapter",
    "REASONING_CONTENT_DELTA_EVENTS": "kontext.harness.agno.event_adapter",
    "REASONING_STEP_EVENTS": "kontext.harness.agno.event_adapter",
    "RUN_CONTENT_COMPLETED_EVENTS": "kontext.harness.agno.event_adapter",
    "INTERMEDIATE_RUN_CONTENT_EVENTS": "kontext.harness.agno.event_adapter",
    "EventConverter": "kontext.harness.agno.event_converters",
    "to_simple_event": "kontext.harness.agno.event_converters",
    "AgentCreationContext": "kontext.harness.agno.factory",
    "AgnoAgentFrameworkAdapter": "kontext.harness.agno.factory",
    "AgnoToolkitAdapter": "kontext.harness.agno.toolkits",
    "adapt_tools_for_agno": "kontext.harness.agno.toolkits",
    "create_model": "kontext.harness.agno.models",
    "build_agno_tool_registry": "kontext.harness.agno.materialize",
    "materialize_agno_system": "kontext.harness.agno.materialize",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'kontext.harness.agno' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)


__all__ = (
    "INTERMEDIATE_RUN_CONTENT_EVENTS",
    "REASONING_CONTENT_DELTA_EVENTS",
    "REASONING_EVENTS",
    "REASONING_STEP_EVENTS",
    "RUN_CANCELLED_EVENTS",
    "RUN_COMPLETED_EVENTS",
    "RUN_CONTENT_COMPLETED_EVENTS",
    "RUN_CONTENT_EVENTS",
    "RUN_ERROR_EVENTS",
    "RUN_OUTPUT_EVENTS",
    "RUN_PAUSED_EVENTS",
    "RUN_STARTED_EVENTS",
    "TOOL_CALL_COMPLETED_EVENTS",
    "TOOL_CALL_ERROR_EVENTS",
    "TOOL_CALL_STARTED_EVENTS",
    "AgentCreationContext",
    "AgnoAgentFrameworkAdapter",
    "AgnoAgenticSystem",
    "AgnoEvent",
    "AgnoToolkitAdapter",
    "EventConverter",
    "adapt_tools_for_agno",
    "build_agno_tool_registry",
    "create_model",
    "materialize_agno_system",
    "to_simple_event",
)
