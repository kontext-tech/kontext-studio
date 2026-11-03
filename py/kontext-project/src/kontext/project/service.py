"""Project-domain service implementation."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from kontext.common.project_scoped import ProjectScopedService
from kontext.data import JobRunDataService, get_sync_db_session
from kontext.data.models import Project
from kontext.data.project_configuration import normalize_project_configuration
from kontext.file import FileService
from kontext.schema import (
    ProjectConfiguration,
    ProjectModel,
    ProjectStatsModel,
)
from kontext.storage import get_storage_provider
from kontext.storage.providers.base import BaseStorageProvider

from .local import to_project_model

logger = logging.getLogger(__name__)


class ProjectService(ProjectScopedService):
    """Business service for project-level operations and statistics."""

    def __init__(self, project_id: UUID):
        super().__init__(project_id)
        self._storage_provider: BaseStorageProvider | None = None
        self._file_service = None
        self._job_run_service = None

    @property
    def storage_provider(self) -> BaseStorageProvider:
        if self._storage_provider is None:
            self._storage_provider = get_storage_provider()
        return self._storage_provider

    @property
    def file_service(self) -> FileService:
        if self._file_service is None:
            self._file_service = FileService(
                project_id=self.project_id, storage_provider=self.storage_provider
            )
        return self._file_service

    @property
    def job_run_service(self) -> JobRunDataService:
        if self._job_run_service is None:
            self._job_run_service = JobRunDataService(project_id=self.project_id)
        return self._job_run_service

    async def get_project_stats_async(self) -> ProjectStatsModel:
        try:
            file_stats = await self.file_service.get_project_file_stats(UUID(self.project_id))
            total_duration_ms = await self.job_run_service.get_total_completed_duration_ms_async()
            return ProjectStatsModel(
                project_id=str(self.project_id),
                file_count=file_stats.file_count,
                total_size_in_bytes=file_stats.total_size_in_bytes,
                total_job_run_duration_ms=int(total_duration_ms or 0),
            )
        except Exception as exc:
            logger.error(
                "Failed to get project stats for project %s: %s",
                self.project_id,
                exc,
            )
            raise

    async def _get_used_storage_bytes(self) -> int:
        def _get():
            with get_sync_db_session() as session:
                project = session.get(Project, self.project_uuid)
                if project:
                    return project.used_storage_bytes
                return 0

        try:
            return await asyncio.to_thread(_get)
        except Exception as exc:
            logger.error(
                "Failed to get used storage bytes for %s: %s",
                self.project_id,
                exc,
            )
            return 0

    async def sync_project_async(self, model: ProjectModel) -> None:
        def _sync():
            with get_sync_db_session() as session:
                project = session.get(Project, self.project_uuid)
                created_at = model.date_created
                modified_at = model.date_modified
                deleted_at = model.date_deleted

                owner_uuid = None
                if model.owner_id:
                    try:
                        owner_uuid = UUID(model.owner_id)
                    except Exception:
                        logger.warning("Invalid owner_id format: %s", model.owner_id)

                modified_by_uuid = None
                if model.modified_by_user_id:
                    try:
                        modified_by_uuid = UUID(model.modified_by_user_id)
                    except Exception:
                        logger.warning(
                            "Invalid modified_by_user_id format: %s",
                            model.modified_by_user_id,
                        )

                if project:
                    configuration = (
                        normalize_project_configuration(model.configuration) or model.configuration
                    )
                    project.project_name = model.project_name
                    project.project_code = model.project_code
                    project.configuration = configuration.model_dump(by_alias=True)
                    project.project_description = model.project_description
                    project.owner_id = owner_uuid
                    project.access_level = model.access_level.value if model.access_level else None
                    project.date_created = created_at
                    project.modified_by_user_id = modified_by_uuid
                    project.date_modified = modified_at
                    project.is_deleted = model.is_deleted or False
                    project.date_deleted = deleted_at
                    logger.info("Updated project %s", self.project_id)
                else:
                    configuration = (
                        normalize_project_configuration(model.configuration) or model.configuration
                    )
                    project = Project(
                        id=self.project_id,
                        project_name=model.project_name,
                        project_code=model.project_code,
                        configuration=configuration.model_dump(by_alias=True),
                        project_description=model.project_description,
                        owner_id=owner_uuid,
                        access_level=model.access_level.value if model.access_level else None,
                        date_created=created_at,
                        modified_by_user_id=modified_by_uuid,
                        date_modified=modified_at,
                        is_deleted=model.is_deleted or False,
                        date_deleted=deleted_at,
                    )
                    session.add(project)
                    logger.info("Created new project record for %s", self.project_id)

                session.commit()

        try:
            await asyncio.to_thread(_sync)
        except Exception as exc:
            logger.error("Failed to sync project %s: %s", self.project_id, exc)
            raise

    async def get_project_configuration_async(self) -> ProjectConfiguration | None:
        def _get():
            with get_sync_db_session() as session:
                project = session.get(Project, self.project_uuid)
                if project and project.configuration:
                    return normalize_project_configuration(
                        ProjectConfiguration.from_dict(project.configuration)
                    )
                return None

        try:
            return await asyncio.to_thread(_get)
        except Exception as exc:
            logger.error(
                "Failed to get configuration for project %s: %s",
                self.project_id,
                exc,
            )
            return None

    async def get_project_async(self, project_id: str | None = None) -> ProjectModel | None:
        self._validate_project_id(project_id)

        def _get_project():
            with get_sync_db_session() as session:
                project = session.get(Project, self.project_uuid)
                if not project:
                    return None

                config = None
                if project.configuration:
                    try:
                        config = normalize_project_configuration(
                            ProjectConfiguration.from_dict(project.configuration)
                        )
                    except Exception as exc:
                        logger.warning(
                            "Failed to parse configuration for project %s: %s",
                            self.project_id,
                            exc,
                        )
                        config = None

                if not config:
                    return None

                return to_project_model(project)

        try:
            return await asyncio.to_thread(_get_project)
        except Exception as exc:
            logger.error("Failed to get project %s: %s", self.project_id, exc)
            return None
