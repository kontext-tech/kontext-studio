"""Shared agent task-profile names.

Task profiles are application policy, but the names are a shared vocabulary:
the model service picks reasoning defaults by profile, and the blueprints select
one. Keeping the literals here prevents a typo in one package from silently
falling back to the wrong default.
"""

from enum import StrEnum


class AgentTaskProfile(StrEnum):
    CHAT_PLANNING = "chat_planning"
    PYTHON_PLANNING = "python_planning"


__all__ = ["AgentTaskProfile"]
