"""Agent runtime storage service for AI session persistence."""

from __future__ import annotations

from kontext.common.protocols import (
    AgentRuntimeStorageConfig,
    AgentRuntimeStorageProtocol,
)
from kontext.common.utils.file_storage import (
    get_project_storage_path,
    get_project_vector_db_path,
)


class AgentRuntimeStorageService(AgentRuntimeStorageProtocol):
    """Resolves agent runtime storage configuration for a project."""

    def get_storage_config(self, project_id: str) -> AgentRuntimeStorageConfig:
        scratchboard_dir = get_project_storage_path(project_id, "scratchboard")
        semantic_index_dir = get_project_vector_db_path(project_id)
        return AgentRuntimeStorageConfig(
            scratchboard_dir=scratchboard_dir,
            semantic_index_dir=semantic_index_dir,
        )
