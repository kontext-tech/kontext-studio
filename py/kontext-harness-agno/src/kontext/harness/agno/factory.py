"""Agno framework harness registration.

The Agno harness materializes a neutral :class:`AgentSpec` into an Agno
``Agent``/``Team``. Modules in this package are the only runtime modules
permitted to import Agno.
"""

from __future__ import annotations

from kontext.agent import (
    AgentSpec,
    BaseAgenticSystem,
)
from kontext.agent.harness import (
    AgentCreationContext,
    AgentFrameworkAdapter,
    register_framework_adapter,
)

from .materialize import materialize_agno_system


class AgnoAgentFrameworkAdapter(AgentFrameworkAdapter):
    """Framework harness that constructs Agno-backed agentic systems."""

    name = "agno"

    def loggers(self) -> tuple[str, ...]:
        return ("agno",)

    async def create_agentic_system(
        self,
        *,
        spec: AgentSpec,
        context: AgentCreationContext,
    ) -> BaseAgenticSystem:
        return materialize_agno_system(spec, context)


register_framework_adapter(AgnoAgentFrameworkAdapter(), make_default=True)
