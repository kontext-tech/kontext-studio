"""AI orchestration, tools, and framework adapters for Kontext."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kontext.agent.harness import (
        AgentCreationContext,
        AgentFrameworkAdapter,
        get_framework_adapter,
    )
    from kontext.common.contracts import AgentConfig

    from .adapters import (
        create_agentic_system,
        get_agent_blueprint,
        register_agent_blueprint,
    )
    from .chat_handler import (
        DEFAULT_CHAT_AGENT_WORKFLOW,
    )
    from .tools import ProjectTools
    from .utils import AgentConfigBuilder


_EXPORTS = {
    "AgentConfig": "kontext.common.contracts",
    "AgentCreationContext": "kontext.agent.harness",
    "AgentFrameworkAdapter": "kontext.agent.harness",
    "AgentConfigBuilder": "kontext.agentic.utils",
    "DEFAULT_CHAT_AGENT_WORKFLOW": "kontext.agentic.chat_handler",
    "create_agentic_system": "kontext.agentic.adapters",
    "get_agent_blueprint": "kontext.agentic.adapters",
    "get_framework_adapter": "kontext.agent.harness",
    "register_agent_blueprint": "kontext.agentic.adapters",
    "ProjectTools": "kontext.agentic.tools",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'kontext.agentic' has no attribute {name!r}")

    module = import_module(module_name)
    return getattr(module, name)


__all__ = [
    "DEFAULT_CHAT_AGENT_WORKFLOW",
    "AgentConfig",
    "AgentConfigBuilder",
    "AgentCreationContext",
    "AgentFrameworkAdapter",
    "ProjectTools",
    "create_agentic_system",
    "get_agent_blueprint",
    "get_framework_adapter",
    "register_agent_blueprint",
]
