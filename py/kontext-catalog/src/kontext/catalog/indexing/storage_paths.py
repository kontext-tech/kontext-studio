"""Shared project storage path resolution for semantic index services."""

from __future__ import annotations

from dataclasses import dataclass

from kontext.common.protocols import AgentRuntimeStorageProviderProtocol
from kontext.common.utils.file_storage import get_project_vector_db_path


@dataclass(frozen=True)
class ProjectKnowledgeStoragePaths:
    """Resolved project paths for semantic index storage."""

    semantic_index_dir: str


def resolve_project_knowledge_storage_paths(
    project_id: str,
    runtime_provider: AgentRuntimeStorageProviderProtocol | None = None,
) -> ProjectKnowledgeStoragePaths:
    """Resolve project-scoped semantic index paths."""
    if runtime_provider is not None:
        try:
            storage_service = runtime_provider.get_agent_runtime_storage_service()
        except NotImplementedError:
            storage_service = None
        if storage_service is not None:
            storage_config = storage_service.get_storage_config(str(project_id))
            return ProjectKnowledgeStoragePaths(
                semantic_index_dir=storage_config.semantic_index_dir,
            )

    project_key = str(project_id)
    return ProjectKnowledgeStoragePaths(
        semantic_index_dir=get_project_vector_db_path(project_key),
    )
