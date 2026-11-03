"""Agent tool-name contracts shared across packages.

These names are part of the agent wire contract: the frontend matches on them
(see `ts/schema/src/ai/tool-names.ts`, which must stay in sync), stream events
key tool-call rendering on them, and external-execution (HITL) routing treats
them specially. Harness adapters must emit/normalize delegation tool calls to
these canonical names.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentToolNames:
    """Canonical tool names crossing the harness boundary."""

    # Agno-style member delegation (coordinator -> specialist)
    DELEGATE_TASK_TO_MEMBER: str = "delegate_task_to_member"
    DELEGATE_TASK_TO_MEMBERS: str = "delegate_task_to_members"

    # Python tools requiring external execution (HITL pause/resume)
    EXECUTE_PYTHON_CODE: str = "execute_python_code"
    EXECUTE_PYTHON_SCRIPT: str = "execute_python_script"

    @property
    def delegation_tools(self) -> frozenset[str]:
        return frozenset({self.DELEGATE_TASK_TO_MEMBER, self.DELEGATE_TASK_TO_MEMBERS})

    @property
    def external_execution_tools(self) -> frozenset[str]:
        return frozenset({self.EXECUTE_PYTHON_CODE, self.EXECUTE_PYTHON_SCRIPT})


AGENT_TOOL_NAMES = AgentToolNames()

DELEGATE_TASK_TO_MEMBER_TOOL_NAME = AGENT_TOOL_NAMES.DELEGATE_TASK_TO_MEMBER
DELEGATE_TASK_TO_MEMBERS_TOOL_NAME = AGENT_TOOL_NAMES.DELEGATE_TASK_TO_MEMBERS
EXECUTE_PYTHON_CODE_TOOL_NAME = AGENT_TOOL_NAMES.EXECUTE_PYTHON_CODE
EXECUTE_PYTHON_SCRIPT_TOOL_NAME = AGENT_TOOL_NAMES.EXECUTE_PYTHON_SCRIPT
DELEGATION_TOOL_NAMES = AGENT_TOOL_NAMES.delegation_tools
EXTERNAL_EXECUTION_TOOL_NAMES = AGENT_TOOL_NAMES.external_execution_tools

__all__ = [
    "AGENT_TOOL_NAMES",
    "DELEGATE_TASK_TO_MEMBERS_TOOL_NAME",
    "DELEGATE_TASK_TO_MEMBER_TOOL_NAME",
    "DELEGATION_TOOL_NAMES",
    "EXECUTE_PYTHON_CODE_TOOL_NAME",
    "EXECUTE_PYTHON_SCRIPT_TOOL_NAME",
    "EXTERNAL_EXECUTION_TOOL_NAMES",
    "AgentToolNames",
]
