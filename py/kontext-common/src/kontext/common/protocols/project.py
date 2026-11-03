"""Project contracts."""

from __future__ import annotations

from typing import Protocol

from kontext.schema import ProjectModel


class IProjectServiceProtocol(Protocol):
    """Protocol defining the interface for project operations."""

    async def get_project_async(self, project_id: str | None = None) -> ProjectModel | None: ...
