"""Shared file-service state and storage-pricing helpers.

``FileService`` composes the upload and result-materialization mixins on top of
this core: one place for the service attributes every section shares.
"""

from __future__ import annotations

import asyncio
import logging
import os
from uuid import UUID

from kontext.common.jobs.trigger_actor import user_actor
from kontext.common.messaging import IQueueClient
from kontext.common.project_scoped import ProjectScopedService
from kontext.common.utils.enum_utils import safe_enum_conversion
from kontext.common.utils.file_storage import (
    CHART_PROJECT_FILE_PREFIX,
    DATATABLE_PROJECT_FILE_PREFIX,
    NOTEBOOK_PROJECT_FILE_PREFIX,
    is_system_managed_project_file_prefix,
    split_project_file_path,
)
from kontext.data import FileDataService, get_sync_db_session
from kontext.data.models import Project, ProjectFile
from kontext.schema import FileFormatType, FileModel, TriggerActorModel
from kontext.storage.providers.base import BaseStorageProvider

from .helpers import (
    file_to_model,
)
from .navigation import FileNavigationService
from .processing import FileProcessingService

logger = logging.getLogger(__name__)


class FileServiceCore(ProjectScopedService):
    """Constructor and helpers shared by every ``FileService`` section."""

    def __init__(
        self,
        *,
        project_id: UUID | str,
        storage_provider: BaseStorageProvider,
        queue_client: IQueueClient | None = None,
    ):
        super().__init__(project_id)
        self._storage_provider = storage_provider
        self._queue_client = queue_client
        self._data_service = FileDataService(project_id)
        self._navigation_service = FileNavigationService(project_id, self._data_service)
        self._processing_service = FileProcessingService(
            project_id=project_id, queue_client=queue_client
        )

    @staticmethod
    def _resolve_trigger_actor(
        *,
        triggered_by: TriggerActorModel | None,
        actor_id: UUID | None,
        system_actor: TriggerActorModel,
    ) -> TriggerActorModel:
        if triggered_by:
            return triggered_by
        if actor_id:
            return user_actor(str(actor_id))
        return system_actor

    async def _check_storage_quota(self, project_id: UUID, file_size_bytes: int) -> None:
        """Check whether uploading a file would exceed project quota."""
        self._validate_project_id(project_id)

        def _get_quota_info() -> tuple[int | None, int | None]:
            with get_sync_db_session() as session:
                project = session.get(Project, project_id)
                if not project:
                    return None, None
                config = project.configuration or {}
                return project.used_storage_bytes, config.get("totalStorageAllocationBytes")

        try:
            used_bytes, limit_bytes = await asyncio.to_thread(_get_quota_info)
            if used_bytes is None or limit_bytes is None:
                logger.warning("Could not retrieve quota info for project %s", project_id)
                return

            if used_bytes + file_size_bytes > limit_bytes:
                raise ValueError(
                    "Storage quota exceeded. "
                    f"Used: {used_bytes} bytes, "
                    f"Limit: {limit_bytes} bytes, "
                    f"Attempted: {file_size_bytes} bytes"
                )
        except ValueError:
            raise
        except Exception as exc:
            logger.error("Failed to check storage quota for %s: %s", project_id, exc)
            raise ValueError(f"Failed to check storage quota: {exc}") from exc

    async def _update_used_storage(self, project_id: UUID, delta_bytes: int) -> None:
        """Update project's used storage bytes."""
        self._validate_project_id(project_id)

        def _update() -> None:
            with get_sync_db_session() as session:
                project = session.get(Project, project_id)
                if project:
                    project.used_storage_bytes = max(0, project.used_storage_bytes + delta_bytes)
                    session.commit()

        try:
            await asyncio.to_thread(_update)
        except Exception as exc:
            logger.error("Failed to update used storage for %s: %s", project_id, exc)

    @staticmethod
    def _get_file_extension(filename: str) -> str:
        _, extension = os.path.splitext(filename.lower())
        return extension

    @staticmethod
    def _normalize_file_identity(*, name: str, prefix: str | None = None) -> tuple[str, str]:
        return split_project_file_path(name, prefix)

    @staticmethod
    def _ensure_user_managed_prefix(prefix: str) -> None:
        if is_system_managed_project_file_prefix(prefix):
            raise ValueError(f"Prefix '{prefix}' is reserved for system-managed files")

    @staticmethod
    def _get_default_artifact_prefix(file_type: FileFormatType) -> str | None:
        if file_type == FileFormatType.NOTEBOOK:
            return NOTEBOOK_PROJECT_FILE_PREFIX
        if file_type == FileFormatType.CHART:
            return CHART_PROJECT_FILE_PREFIX
        if file_type == FileFormatType.DATATABLE:
            return DATATABLE_PROJECT_FILE_PREFIX
        return None

    def _find_allowed_file_type_configuration(
        self,
        *,
        filename: str,
        file_type: FileFormatType,
        project_config,
    ):
        extension = self._get_file_extension(filename)
        for allowed_file_type in project_config.allowed_file_types or []:
            if allowed_file_type.file_extension.lower() == extension:
                return allowed_file_type

        if not extension:
            for allowed_file_type in project_config.allowed_file_types or []:
                normalized_type = safe_enum_conversion(
                    FileFormatType,
                    allowed_file_type.file_format_type,
                    FileFormatType.DEFAULT,
                )
                if normalized_type == file_type:
                    return allowed_file_type
        return None

    async def get_file_by_id(self, file_id: UUID) -> ProjectFile | None:
        """Get a file by ID."""
        return await self._data_service.get_file_by_id_async(file_id)

    async def exists_by_id(self, project_id: UUID | str, file_id: UUID | str) -> bool:
        """Check whether a file exists by ID."""
        self._validate_project_id(project_id)
        return await self._data_service.file_exists_by_id_async(
            UUID(str(self._project_id)), UUID(str(file_id))
        )

    async def get_file_details(self, project_id: UUID | str, file_id: UUID | str) -> FileModel:
        """Get file details as a schema model."""
        self._validate_project_id(project_id)
        file = await self.get_file_by_id(UUID(str(file_id)))
        if not file:
            raise ValueError(f"File {file_id} not found")
        return file_to_model(file)
