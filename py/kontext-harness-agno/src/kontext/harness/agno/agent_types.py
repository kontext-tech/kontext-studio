"""Shared Agno type aliases for this package.

Kept in a leaf module so consumers that must not import each other's logic
(``run`` cannot import the ``system``-dependent materialize module) can share
one spelling of ``Agent | Team``.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.team import Team

AgnoAgentOrTeam = Agent | Team

__all__ = ["AgnoAgentOrTeam"]
