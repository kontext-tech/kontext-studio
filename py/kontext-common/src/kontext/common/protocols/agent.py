"""Agent runtime storage and language-model contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from kontext.schema import FoundationModel, ModelReasoningEffort

    from ..contracts import AgentConfig


@dataclass(frozen=True)
class AgentRuntimeStorageConfig:
    scratchboard_dir: str
    semantic_index_dir: str


class AgentRuntimeStorageProtocol(Protocol):
    """Protocol defining the interface for agent runtime storage."""

    def get_storage_config(self, project_id: str) -> AgentRuntimeStorageConfig: ...


class ILanguageModelProtocol(Protocol):
    """Protocol defining the interface for model resolution."""

    def get_model_definition(
        self, model_id: str, provider: str | None = None
    ) -> FoundationModel | None: ...

    def list_model_definitions(self, provider: str | None = None) -> list[FoundationModel]: ...

    def get_agent_config(self) -> AgentConfig: ...

    def get_reasoning_effort(self, task_profile: str | None = None) -> ModelReasoningEffort: ...
