"""
Base classes for project-scoped services.
"""

from __future__ import annotations

from uuid import UUID


class ProjectIdMismatchError(ValueError):
    """
    Raised when a method is called with a project_id that does not match
    the service's project scope.
    """

    def __init__(self, service_project_id: str, method_project_id: str):
        super().__init__(
            f"Project ID mismatch: service initialized with '{service_project_id}' "
            f"but method called with '{method_project_id}'. "
            f"This may indicate potential unauthorized cross-project access "
            f"or a programming error."
        )
        self.service_project_id = service_project_id
        self.method_project_id = method_project_id


class ProjectScopedService:
    """Base class for services that are scoped to a specific project."""

    def __init__(self, project_id: UUID | str):
        self._project_id = str(project_id)

    def _validate_project_id(self, project_id: UUID | str | None) -> None:
        if project_id is None:
            return

        provided_id = str(project_id)
        if provided_id != self._project_id:
            raise ProjectIdMismatchError(
                service_project_id=self._project_id,
                method_project_id=provided_id,
            )

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def project_uuid(self) -> UUID:
        return UUID(self._project_id)
