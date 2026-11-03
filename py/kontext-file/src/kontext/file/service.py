"""File-domain service implementation."""

from __future__ import annotations

import asyncio
import io
import logging
import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from kontext.common.artifacts.provenance import (
    apply_chart_provenance,
    apply_inline_data_provenance,
    provenance_from_document_metadata,
)
from kontext.common.constants import DataLakeConstants, QueryConstants
from kontext.common.jobs.trigger_actor import system_actor as make_system_actor
from kontext.common.jobs.trigger_actor import user_actor
from kontext.common.messaging import IQueueClient
from kontext.common.notebook_aliases import normalize_sql_aliases
from kontext.common.pagination import PaginatedResult
from kontext.common.project_scoped import ProjectScopedService
from kontext.common.utils.enum_utils import safe_enum_conversion
from kontext.common.utils.file_storage import (
    CHART_PROJECT_FILE_PREFIX,
    DATATABLE_PROJECT_FILE_PREFIX,
    NOTEBOOK_PROJECT_FILE_PREFIX,
    RESULT_STORE_PROJECT_FILE_PREFIX,
    build_project_file_path,
    is_system_managed_project_file_prefix,
    normalize_project_file_prefix,
    split_project_file_path,
)
from kontext.data import FileDataService, get_sync_db_session
from kontext.data.models import Project, ProjectFile
from kontext.data.types import FileStats
from kontext.execution.events import EventService
from kontext.schema import (
    ArtifactProvenance,
    ChartDocument,
    DataColumn,
    DataTable,
    FileFormatType,
    FileModel,
    FileSchemaModel,
    FileStatsModel,
    FileUploadResponse,
    InlineData,
    NotebookDocument,
    QueryResponse,
    SimpleFileEventData,
    TriggerActorModel,
)
from kontext.storage.providers.base import BaseStorageProvider

from .data_plane import DataTablePayload, parquet_fingerprint
from .data_plane.preview import build_preview, preview_row_budget
from .helpers import (
    FileData,
    InMemoryUploadFile,
    StorageUploadResult,
    UploadFileProtocol,
    file_to_model,
    file_to_simple_data,
    infer_file_type,
    should_trigger_profiling_job,
)
from .navigation import FileNavigationService
from .processing import FileProcessingPlan, FileProcessingService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileUploadFailure:
    filename: str | None
    error: str
    file_id: UUID | str | None = None

    def to_message(self) -> str:
        if self.filename:
            return f"{self.filename}: {self.error}"
        return self.error


@dataclass
class ValidatedUploadBatch:
    files: list[FileData]
    failures: list[FileUploadFailure]


@dataclass
class PersistedUploadBatch:
    created_files: list[ProjectFile]
    updated_files: list[ProjectFile]
    processing_plans: list[FileProcessingPlan]
    failures: list[FileUploadFailure]

    @property
    def successful_files(self) -> list[ProjectFile]:
        return [*self.created_files, *self.updated_files]


def _json_safe(value: Any) -> Any:
    """Null non-JSON-safe floats so descriptor JSON stays strict.

    Arrow decodes nulls as ``None``, so only NaN/inf sentinels need mapping:
    Python's ``json`` would otherwise emit bare ``NaN``/``Infinity`` tokens
    that strict clients reject.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


class FileService(ProjectScopedService):
    """Business service for file management."""

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

    async def _validate_upload_constraints(
        self,
        *,
        project_id: UUID,
        filename: str,
        file_size: int,
        file_type: FileFormatType,
        project_config,
        allowed_file_format_types: Sequence[FileFormatType] | None = None,
        quota_delta_bytes: int | None = None,
    ) -> None:
        if allowed_file_format_types is not None and file_type not in allowed_file_format_types:
            raise ValueError(
                "Only structured data files that can be ingested into the "
                f"lakehouse are supported. '{filename}' is {file_type.value}."
            )

        extension = self._get_file_extension(filename)
        matching_file_type = self._find_allowed_file_type_configuration(
            filename=filename,
            file_type=file_type,
            project_config=project_config,
        )
        if matching_file_type is None:
            type_label = extension or file_type.value
            raise ValueError(f'File type "{type_label}" is not allowed.')

        if file_size > project_config.max_file_bytes_size:
            raise ValueError(
                "File size exceeds the project limit of "
                f"{project_config.max_file_bytes_size} bytes."
            )

        normalized_quota_delta = file_size if quota_delta_bytes is None else quota_delta_bytes
        if normalized_quota_delta > 0:
            await self._check_storage_quota(project_id, normalized_quota_delta)

    async def _read_and_validate_upload_file(
        self,
        *,
        project_id: UUID,
        upload_file: UploadFileProtocol,
        filename: str,
        prefix: str | None = None,
        infer_type_func,
        project_config,
        allowed_file_format_types: Sequence[FileFormatType] | None = None,
        quota_delta_bytes: int | None = None,
    ) -> FileData:
        file_data = await self._read_upload_file(
            upload_file=upload_file,
            filename=filename,
            prefix=prefix,
            infer_type_func=infer_type_func,
        )

        await self._validate_upload_constraints(
            project_id=project_id,
            filename=filename,
            file_size=len(file_data.content),
            file_type=file_data.file_type,
            project_config=project_config,
            allowed_file_format_types=allowed_file_format_types,
            quota_delta_bytes=quota_delta_bytes,
        )

        return file_data

    async def _read_upload_file(
        self,
        *,
        upload_file: UploadFileProtocol,
        filename: str,
        prefix: str | None = None,
        infer_type_func,
    ) -> FileData:
        content = await upload_file.read()
        content_type = upload_file.content_type or "application/octet-stream"
        normalized_prefix, normalized_name = self._normalize_file_identity(
            name=filename,
            prefix=prefix,
        )
        self._ensure_user_managed_prefix(normalized_prefix)
        file_type = infer_type_func(normalized_name, content_type)

        if len(content) == 0:
            raise ValueError("File is empty")

        return FileData(
            filename=normalized_name,
            content=content,
            content_type=content_type,
            file_type=file_type,
            prefix=normalized_prefix,
        )

    async def _record_created_lakehouse_files(
        self,
        *,
        files: Sequence[ProjectFile],
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> None:
        files_for_event: list[SimpleFileEventData] = []
        for file in files:
            try:
                file_type = FileFormatType(file.file_type)
            except ValueError:
                continue
            if is_system_managed_project_file_prefix(file.prefix):
                continue
            if DataLakeConstants.is_supported_data_file_type(file_type):
                files_for_event.append(file_to_simple_data(file))

        if not files_for_event:
            return

        event_service = EventService(
            project_id=self._project_id,
            queue_client=self._queue_client,
        )
        await event_service.record_files_created(
            files=files_for_event,
            user_id=user_id,
            ip_address=ip_address,
        )

    async def validate_upload_files(
        self,
        *,
        project_id: UUID,
        files: Sequence[UploadFileProtocol],
        infer_type_func,
        allowed_file_format_types: Sequence[FileFormatType] | None = None,
        prefix: str | None = None,
    ) -> ValidatedUploadBatch:
        self._validate_project_id(project_id)
        project_config = await self._data_service.get_project_config_async()
        if project_config is None:
            raise ValueError("Project configuration is required for file uploads.")

        validated_files: list[FileData] = []
        failures: list[FileUploadFailure] = []

        for file in files:
            if not file.filename:
                failures.append(
                    FileUploadFailure(
                        filename=None,
                        error="File must have a filename.",
                    )
                )
                continue

            try:
                validated_files.append(
                    await self._read_and_validate_upload_file(
                        project_id=project_id,
                        upload_file=file,
                        filename=file.filename,
                        prefix=prefix,
                        infer_type_func=infer_type_func,
                        project_config=project_config,
                        allowed_file_format_types=allowed_file_format_types,
                        quota_delta_bytes=None,
                    )
                )
            except Exception as exc:
                logger.error("Failed to validate file '%s': %s", file.filename, exc)
                failures.append(
                    FileUploadFailure(
                        filename=file.filename,
                        error=str(exc),
                    )
                )

        return ValidatedUploadBatch(files=validated_files, failures=failures)

    async def persist_uploaded_files(
        self,
        *,
        project_id: UUID,
        files: Sequence[FileData],
        owner_id: UUID | None = None,
        allow_overwrite: bool = False,
        provenance: ArtifactProvenance | None = None,
    ) -> PersistedUploadBatch:
        self._validate_project_id(project_id)

        failures: list[FileUploadFailure] = []
        existing_files: dict[str, ProjectFile] = {}
        files_to_persist: list[FileData] = []
        seen_filenames: set[str] = set()

        for file_data in files:
            logical_path = build_project_file_path(file_data.filename, file_data.prefix)
            normalized_logical_path = logical_path.lower()
            if normalized_logical_path in seen_filenames:
                failures.append(
                    FileUploadFailure(
                        filename=logical_path,
                        error="Duplicate file name in this upload batch.",
                    )
                )
                continue
            seen_filenames.add(normalized_logical_path)

            existing = await self._data_service.get_file_by_name_and_project_id_async(
                project_id=project_id,
                name=file_data.filename,
                prefix=file_data.prefix,
            )
            if existing:
                if allow_overwrite:
                    existing_files[logical_path] = existing
                else:
                    failures.append(
                        FileUploadFailure(
                            filename=logical_path,
                            error=(
                                "Resource already exists. Enable 'Allow overwrite' to replace it."
                            ),
                        )
                    )
                    continue

            files_to_persist.append(file_data)

        storage_results: list[StorageUploadResult] = []
        for file_data in files_to_persist:
            try:
                logical_path = build_project_file_path(file_data.filename, file_data.prefix)
                existing = existing_files.get(logical_path)
                if existing and existing.uri:
                    try:
                        await self._storage_provider.delete_file(existing.uri)
                    except Exception as delete_err:
                        logger.warning(
                            "Failed to delete old file for '%s': %s",
                            file_data.filename,
                            delete_err,
                        )

                storage_result = await self._storage_provider.upload_file(
                    project_id=str(project_id),
                    filename=file_data.filename,
                    prefix=file_data.prefix,
                    content=file_data.content,
                    content_type=file_data.content_type,
                )
                storage_results.append(
                    StorageUploadResult(
                        filename=file_data.filename,
                        prefix=file_data.prefix,
                        uri=storage_result.uri,
                        size=len(file_data.content),
                        content_type=file_data.content_type,
                        file_type=file_data.file_type,
                    )
                )
            except Exception as exc:
                logger.error(
                    "Failed to upload '%s' to storage: %s",
                    file_data.filename,
                    exc,
                )
                failures.append(
                    FileUploadFailure(
                        filename=file_data.filename,
                        error=f"Failed to upload file: {exc!s}",
                    )
                )

        created_files: list[ProjectFile] = []
        updated_files: list[ProjectFile] = []
        processing_plans: list[FileProcessingPlan] = []
        total_size_delta = 0

        for result in storage_results:
            try:
                logical_path = build_project_file_path(result.filename, result.prefix)
                existing = existing_files.get(logical_path)
                if existing:
                    old_size = existing.size or 0
                    total_size_delta += result.size - old_size
                    project_file = await self._data_service.update_file_async(
                        existing,
                        name=result.filename,
                        prefix=result.prefix,
                        content_type=result.content_type,
                        file_type=result.file_type,
                        size=result.size,
                        uri=result.uri,
                        modified_by_user_id=owner_id,
                    )
                    updated_files.append(project_file)
                    processing_plans.append(
                        self._processing_service.build_file_processing_plan(
                            file_id=project_file.id,
                            old_filename=existing.name,
                            old_prefix=existing.prefix,
                            old_content_type=existing.content_type,
                            old_file_type=existing.file_type,
                            new_filename=project_file.name,
                            new_prefix=project_file.prefix,
                            new_content_type=project_file.content_type,
                            new_file_type=project_file.file_type,
                        )
                    )
                else:
                    total_size_delta += result.size
                    project_file = await self._data_service.create_file_async(
                        project_id=project_id,
                        name=result.filename,
                        prefix=result.prefix,
                        content_type=result.content_type,
                        size=result.size,
                        file_type=result.file_type,
                        owner_id=owner_id,
                        uri=result.uri,
                        provenance=(
                            provenance.model_dump_json(by_alias=True, exclude_none=True)
                            if provenance
                            else None
                        ),
                    )
                    created_files.append(project_file)
                    processing_plans.append(
                        self._processing_service.build_file_processing_plan(
                            file_id=project_file.id,
                            new_filename=project_file.name,
                            new_prefix=project_file.prefix,
                            new_content_type=project_file.content_type,
                            new_file_type=project_file.file_type,
                        )
                    )

                logger.info(
                    "%s file %s for project %s, size: %s",
                    "Updated" if existing else "Created",
                    project_file.id,
                    project_id,
                    result.size,
                )
            except Exception as exc:
                logger.error("Failed to save file record for '%s': %s", result.filename, exc)
                failures.append(
                    FileUploadFailure(
                        filename=result.filename,
                        error=f"Failed to save file record: {exc!s}",
                    )
                )

        if total_size_delta != 0:
            await self._update_used_storage(project_id, total_size_delta)

        return PersistedUploadBatch(
            created_files=created_files,
            updated_files=updated_files,
            processing_plans=processing_plans,
            failures=failures,
        )

    async def dispatch_post_upload_processing(
        self,
        *,
        persisted_batch: PersistedUploadBatch,
        owner_id: UUID | None = None,
        ip_address: str | None = None,
        triggered_by: TriggerActorModel | None = None,
        force_workflow: bool = False,
        workflow_key: str = "file_processing",
        workflow_name: str = "File Processing Workflow",
        workflow_description: str | None = None,
        workflow_parameters: dict[str, object] | None = None,
        system_actor: TriggerActorModel | None = None,
    ) -> UUID | None:
        await self._record_created_lakehouse_files(
            files=persisted_batch.created_files,
            user_id=owner_id,
            ip_address=ip_address,
        )

        effective_triggered_by = self._resolve_trigger_actor(
            triggered_by=triggered_by,
            actor_id=owner_id,
            system_actor=system_actor or make_system_actor("FileUpload"),
        )
        return await self._processing_service.apply_file_processing_plans(
            persisted_batch.processing_plans,
            triggered_by=effective_triggered_by,
            force_workflow=force_workflow,
            workflow_key=workflow_key,
            workflow_name=workflow_name,
            workflow_description=workflow_description,
            workflow_parameters=workflow_parameters,
        )

    async def upload_multiple_files(
        self,
        *,
        project_id: UUID,
        files: Sequence[UploadFileProtocol],
        prefix: str | None = None,
        owner_id: UUID | None = None,
        ip_address: str | None = None,
        allow_overwrite: bool = False,
        infer_type_func,
        triggered_by: TriggerActorModel | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> tuple[list[ProjectFile], list[ProjectFile], list[str]]:
        """Upload multiple files while separating DB and storage phases."""
        validation = await self.validate_upload_files(
            project_id=project_id,
            files=files,
            infer_type_func=infer_type_func,
            prefix=prefix,
        )
        persisted_batch = await self.persist_uploaded_files(
            project_id=project_id,
            files=validation.files,
            owner_id=owner_id,
            allow_overwrite=allow_overwrite,
            provenance=provenance,
        )
        await self.dispatch_post_upload_processing(
            persisted_batch=persisted_batch,
            owner_id=owner_id,
            ip_address=ip_address,
            triggered_by=triggered_by,
        )

        failures = [*validation.failures, *persisted_batch.failures]
        return (
            persisted_batch.created_files,
            persisted_batch.updated_files,
            [failure.to_message() for failure in failures],
        )

    async def upload_single_file(
        self,
        *,
        project_id: UUID,
        upload_file: UploadFileProtocol,
        name: str | None = None,
        prefix: str | None = None,
        owner_id: UUID | None = None,
        ip_address: str | None = None,
        triggered_by: TriggerActorModel | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> ProjectFile:
        """Upload a single file and create its DB record."""
        self._validate_project_id(project_id)
        if not upload_file.filename:
            raise ValueError("File must have a filename")

        file_name = name if name else upload_file.filename
        project_config = await self._data_service.get_project_config_async()
        if project_config is None:
            raise ValueError("Project configuration is required for file uploads.")

        validated_file = await self._read_and_validate_upload_file(
            project_id=project_id,
            upload_file=upload_file,
            filename=file_name,
            prefix=prefix,
            infer_type_func=infer_file_type,
            project_config=project_config,
        )

        persisted_batch = await self.persist_uploaded_files(
            project_id=project_id,
            files=[validated_file],
            owner_id=owner_id,
            provenance=provenance,
        )
        if persisted_batch.failures:
            raise ValueError(persisted_batch.failures[0].to_message())
        if not persisted_batch.successful_files:
            raise ValueError("File upload did not produce a saved file.")

        project_file = persisted_batch.successful_files[0]
        processing_plan = persisted_batch.processing_plans[0]
        has_queue = self._queue_client is not None
        logger.info(
            "File %s created. Type: %s. Should profile: %s. Should index document: %s. Has external queue transport: %s",
            project_file.id,
            validated_file.file_type,
            processing_plan.new_target == "lakehouse",
            processing_plan.new_target == "document",
            has_queue,
        )
        await self.dispatch_post_upload_processing(
            persisted_batch=persisted_batch,
            owner_id=owner_id,
            ip_address=ip_address,
            triggered_by=triggered_by,
        )

        logger.info(
            "Uploaded file %s for project %s, size: %s",
            project_file.id,
            project_id,
            len(validated_file.content),
        )
        return project_file

    async def update_file_content(
        self,
        *,
        file_id: UUID,
        upload_file: UploadFileProtocol,
        owner_id: UUID | None = None,
        triggered_by: TriggerActorModel | None = None,
    ) -> ProjectFile:
        """Replace a file's content while keeping metadata in sync."""
        if not upload_file.filename:
            raise ValueError("File must have a filename")

        project_file = await self._data_service.get_file_by_id_async(file_id)
        if not project_file:
            raise ValueError(f"File {file_id} not found")

        old_uri = project_file.uri
        old_size = project_file.size or 0
        project_id = project_file.project_id
        if not project_id:
            raise ValueError(f"File {file_id} has no associated project")

        old_file_type = project_file.file_type
        old_name = project_file.name
        old_prefix = project_file.prefix
        old_content_type = project_file.content_type
        content_type = upload_file.content_type or "application/octet-stream"
        file_name = upload_file.filename
        normalized_prefix, normalized_name = self._normalize_file_identity(
            name=file_name,
            prefix=old_prefix,
        )
        new_file_type = infer_file_type(normalized_name, content_type)
        file_content = await upload_file.read()
        file_size = len(file_content)
        if file_size == 0:
            raise ValueError("File is empty")

        size_delta = file_size - old_size
        project_config = await self._data_service.get_project_config_async()
        if project_config is None:
            raise ValueError("Project configuration is required for file uploads.")
        await self._validate_upload_constraints(
            project_id=project_id,
            filename=normalized_name,
            file_size=file_size,
            file_type=new_file_type,
            project_config=project_config,
            quota_delta_bytes=max(size_delta, 0),
        )

        if old_uri:
            try:
                await self._storage_provider.delete_file(old_uri)
            except Exception as delete_err:
                logger.warning("Failed to delete old file: %s", delete_err)

        storage_result = await self._storage_provider.upload_file(
            project_id=str(project_id),
            filename=normalized_name,
            prefix=normalized_prefix,
            content=file_content,
            content_type=content_type,
        )

        project_file = await self._data_service.get_file_by_id_async(file_id)
        if not project_file:
            raise ValueError(f"File {file_id} not found after upload")

        project_file = await self._data_service.update_file_async(
            project_file,
            name=normalized_name,
            prefix=normalized_prefix,
            content_type=content_type,
            file_type=new_file_type,
            size=file_size,
            uri=storage_result.uri,
            owner_id=owner_id,
        )

        if size_delta != 0:
            await self._update_used_storage(project_id, size_delta)

        processing_plan = self._processing_service.build_file_processing_plan(
            file_id=project_file.id,
            old_filename=old_name,
            old_prefix=old_prefix,
            old_content_type=old_content_type,
            old_file_type=old_file_type,
            new_filename=project_file.name,
            new_prefix=project_file.prefix,
            new_content_type=project_file.content_type,
            new_file_type=project_file.file_type,
        )
        effective_triggered_by = self._resolve_trigger_actor(
            triggered_by=triggered_by,
            actor_id=owner_id,
            system_actor=make_system_actor("FileUpdate"),
        )
        await self._processing_service.apply_file_processing_plan(
            processing_plan,
            triggered_by=effective_triggered_by,
        )

        logger.info("Updated file %s", file_id)
        return project_file

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

    async def get_file_content(self, project_id: UUID | str, file_id: UUID | str) -> str:
        """Get the content of a UTF-8 file."""
        self._validate_project_id(project_id)
        file = await self.get_file_by_id(UUID(str(file_id)))
        if not file:
            raise ValueError(f"File {file_id} not found")
        if not file.uri:
            raise ValueError(f"File {file_id} has no URI")

        stream = await self._storage_provider.download_file(file.uri)
        return stream.getvalue().decode("utf-8")

    async def get_data_table_file(self, project_id: UUID | str, file_id: UUID | str) -> InlineData:
        """Get an InlineData object from a file (descriptor; may be a preview)."""
        self._validate_project_id(project_id)
        content = await self.get_file_content(project_id, file_id)
        return InlineData.model_validate_json(content)

    async def get_inline_data_rows(
        self,
        project_id: UUID | str,
        file_id: UUID | str,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> InlineData:
        """Return a window of full rows for a data-table file.

        Large results keep only a preview in the descriptor; this resolves the
        full rows from the companion Parquet store. Small results carry their rows
        inline, so the window is sliced in place. The returned ``table.rowCount``
        is always the *total* row count, so callers can paginate.
        """
        self._validate_project_id(project_id)
        descriptor = await self.get_data_table_file(project_id, file_id)
        metadata = descriptor.metadata
        table = descriptor.table
        data_path = getattr(metadata, "data_path", None) if metadata else None
        total = getattr(metadata, "row_count", None) if metadata else None

        start = max(0, offset)
        if data_path:
            rows = await self._read_result_slice(project_id, data_path, offset=start, limit=limit)
        else:
            embedded = table.rows if table else None
            embedded = embedded or []
            end = (start + limit) if limit is not None else None
            rows = embedded[start:end]

        if total is None:
            total = len(rows)

        return InlineData(
            title=descriptor.title,
            table=DataTable(
                columns=table.columns if table else None,
                rows=rows,
                row_count=total,
            ),
            metadata=metadata,
        )

    async def create_notebook(
        self,
        project_id: UUID | str,
        notebook: NotebookDocument,
        name: str | None = None,
    ) -> FileUploadResponse:
        """Create a new notebook file.

        Notebook files carry no record-level provenance: the taxonomy describes
        how *artifacts* were produced, and a notebook is a container rather
        than a produced result. Runs stamp ``notebook_run`` provenance on the
        tables/charts they materialize (with the notebook/block id).
        """
        self._validate_project_id(project_id)
        file_name, content = self._prepare_notebook_for_storage(notebook, name)
        result = await self.upload_single_file(
            project_id=UUID(str(project_id)),
            upload_file=InMemoryUploadFile(file_name, content),
            name=file_name,
            prefix=NOTEBOOK_PROJECT_FILE_PREFIX,
        )
        return FileUploadResponse(file=file_to_model(result))

    async def create_chart(
        self,
        project_id: UUID | str,
        chart: ChartDocument,
        name: str | None = None,
        *,
        notebook_id: UUID | str | None = None,
        query_session_id: UUID | str | None = None,
        chat_session_id: UUID | str | None = None,
    ) -> FileUploadResponse:
        """Create a new chart file with de-duplication."""
        self._validate_project_id(project_id)
        apply_chart_provenance(
            chart,
            notebook_id=notebook_id,
            query_session_id=query_session_id,
            chat_session_id=chat_session_id,
        )
        file_name, content = self._prepare_chart_for_storage(chart, name)

        base_name = file_name
        if await self._data_service.file_exists_async(
            UUID(str(project_id)),
            file_name,
            CHART_PROJECT_FILE_PREFIX,
        ):
            name_part, ext = os.path.splitext(base_name)
            short_id = str(uuid4())[:8]
            file_name = f"{name_part}-{short_id}{ext}"

        result = await self.upload_single_file(
            project_id=UUID(str(project_id)),
            upload_file=InMemoryUploadFile(file_name, content),
            name=file_name,
            prefix=CHART_PROJECT_FILE_PREFIX,
            provenance=provenance_from_document_metadata(chart.metadata),
        )
        return FileUploadResponse(file=file_to_model(result))

    @staticmethod
    def _result_store_path(project_id: UUID | str, fingerprint: str) -> str:
        """Return the project-relative path for a content-addressed row store."""
        return (
            f"projects/{str(project_id).lower()}/resources/"
            f"{RESULT_STORE_PROJECT_FILE_PREFIX}/{fingerprint}.parquet"
        )

    async def store_result_payload(
        self,
        project_id: UUID | str,
        payload: DataTablePayload,
    ) -> str:
        """Persist a materialized result's columnar row store (content-addressed).

        Identical results share one blob because the filename is the content
        fingerprint, so re-materializing the same query does not duplicate data.
        Returns the storage path stored in the ``.dt`` descriptor.
        """
        self._validate_project_id(project_id)
        return await self._store_parquet_bytes(
            project_id, payload.parquet_bytes, payload.fingerprint
        )

    async def _store_parquet_bytes(
        self, project_id: UUID | str, parquet_bytes: bytes, fingerprint: str
    ) -> str:
        """Upload Parquet bytes under their content fingerprint and return the path."""
        relative = self._result_store_path(project_id, fingerprint)
        result = await self._storage_provider.upload_file(
            project_id=str(project_id),
            filename=f"{fingerprint}.parquet",
            prefix=RESULT_STORE_PROJECT_FILE_PREFIX,
            content=parquet_bytes,
            content_type="application/vnd.apache.parquet",
        )
        return result.path or relative

    async def _read_result_slice(
        self,
        project_id: UUID | str,
        data_path: str,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[list[object]]:
        """Read a window of rows from a materialized result's row store."""
        self._validate_project_id(project_id)
        if not await self._storage_provider.file_exists(data_path):
            raise ValueError(f"Result row store not found: {data_path}")
        stream = await self._storage_provider.download_file(data_path)
        from .data_plane.payload import read_parquet_slice

        return read_parquet_slice(stream.getvalue(), offset=offset, limit=limit)

    async def materialize_query_result(
        self,
        project_id: UUID | str,
        query_response: QueryResponse,
        *,
        title: str | None = None,
        session_id: UUID | str | None = None,
        existing_file_id: UUID | str | None = None,
        notebook_id: UUID | str | None = None,
        chat_session_id: UUID | str | None = None,
        sql: str | None = None,
    ) -> str | None:
        """Materialize a query result through the single canonical path.

        Used by the query job, so every execution-recorded result carries
        provenance and a columnar row store.
        """
        table = query_response.result
        if table is None:
            return None
        return await self._materialize_table(
            project_id,
            title=title or "query-result",
            table=table,
            session_id=session_id,
            existing_file_id=existing_file_id,
            notebook_id=notebook_id,
            chat_session_id=chat_session_id,
            sql=sql if sql is not None else query_response.sql,
            provenance=query_response.provenance,
        )

    async def materialize_inline_data(
        self,
        project_id: UUID | str,
        inline_data: InlineData,
        *,
        name: str | None = None,
        session_id: UUID | str | None = None,
        notebook_id: UUID | str | None = None,
        chat_session_id: UUID | str | None = None,
        sql: str | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> str | None:
        """Materialize an in-memory ``InlineData`` through the same path.

        Used by the AI toolkit when it promotes a transient result. Routing
        both writers here is what prevents provenance/envelope drift between
        the server and worker processes.
        """
        if inline_data.table is None:
            return None
        return await self._materialize_table(
            project_id,
            title=name or inline_data.title or "query-result",
            table=inline_data.table,
            session_id=session_id,
            existing_file_id=None,
            notebook_id=notebook_id,
            chat_session_id=chat_session_id,
            sql=sql,
            provenance=provenance,
        )

    async def materialize_parquet_inline_data(
        self,
        project_id: UUID | str,
        parquet_bytes: bytes,
        *,
        name: str | None = None,
        session_id: UUID | str | None = None,
        notebook_id: UUID | str | None = None,
        chat_session_id: UUID | str | None = None,
        sql: str | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> str | None:
        """Materialize Parquet bytes as a ``.dt`` without decoding the full table.

        ``kontext.save_table`` serializes the frame in the kernel, so the
        descriptor is built from the Parquet footer (schema + total row count)
        plus a bounded first-row-group preview, while the original bytes become
        the content-addressed row store. Memory stays bounded by the preview
        instead of the full result.
        """
        self._validate_project_id(project_id)
        if not parquet_bytes:
            return None

        import pyarrow.parquet as parquet

        reader = parquet.ParquetFile(io.BytesIO(parquet_bytes))
        row_count = int(reader.metadata.num_rows)
        columns = [
            DataColumn(name=field.name, type=str(field.type)) for field in reader.schema_arrow
        ]

        preview_rows: list[list[object]] = []
        if row_count > 0:
            limit = preview_row_budget(len(columns))
            first_group = reader.read_row_group(0).slice(0, limit)
            column_values = [column.to_pylist() for column in first_group.columns]
            preview_rows = [
                [_json_safe(value) for value in row] for row in zip(*column_values, strict=True)
            ]

        descriptor_title = self._descriptor_title(name or "saved-table")
        descriptor = InlineData(
            title=descriptor_title,
            table=DataTable(columns=columns, rows=preview_rows, row_count=row_count),
        )
        fingerprint = parquet_fingerprint(parquet_bytes)
        data_path = await self._store_parquet_bytes(project_id, parquet_bytes, fingerprint)
        apply_inline_data_provenance(
            descriptor,
            notebook_id=notebook_id,
            query_session_id=session_id,
            chat_session_id=chat_session_id,
            sql=sql,
            data_path=data_path,
            row_count=row_count,
            provenance=provenance,
        )
        return await self._create_descriptor_file(
            project_id=project_id,
            descriptor=descriptor,
            file_name=self._descriptor_file_name(descriptor_title),
            provenance=provenance,
        )

    async def _materialize_table(
        self,
        project_id: UUID | str,
        *,
        title: str,
        table: DataTable,
        session_id: UUID | str | None,
        existing_file_id: UUID | str | None,
        notebook_id: UUID | str | None,
        chat_session_id: UUID | str | None,
        sql: str | None,
        provenance: ArtifactProvenance | None = None,
    ) -> str:
        """Write the Parquet row store and ``.dt`` descriptor for a result table."""
        self._validate_project_id(project_id)

        descriptor_title = self._descriptor_title(title)
        row_count = table.row_count
        if row_count is None:
            row_count = len(table.rows or [])

        # Small results are embedded in full; large results keep only a bounded
        # preview in the descriptor and move the full rows into a companion
        # content-addressed Parquet store (``dataPath``). This keeps ``.dt`` files
        # small and avoids duplicating every row in both JSON and Parquet.
        if row_count > QueryConstants.DOCUMENT_EMBEDDING_THRESHOLD:
            payload = DataTablePayload.from_table(table)
            data_path: str | None = await self.store_result_payload(project_id, payload)
            descriptor_table = build_preview(table)
        else:
            data_path = None
            descriptor_table = table

        descriptor = InlineData(title=descriptor_title, table=descriptor_table)
        apply_inline_data_provenance(
            descriptor,
            notebook_id=notebook_id,
            query_session_id=session_id,
            chat_session_id=chat_session_id,
            sql=sql,
            data_path=data_path,
            row_count=row_count,
            provenance=provenance,
        )

        if existing_file_id:
            existing_file = await self.get_file_details(project_id, existing_file_id)
            content = descriptor.model_dump_json(exclude_none=True, by_alias=True).encode("utf-8")
            await self.update_file_content(
                file_id=UUID(str(existing_file_id)),
                upload_file=InMemoryUploadFile(existing_file.name, content),
            )
            if provenance is not None:
                # Keep the record's provenance in step with the rewritten
                # document so Files-list badges do not go stale.
                existing_record = await self.get_file_by_id(UUID(str(existing_file_id)))
                if existing_record is not None:
                    await self._data_service.update_file_async(
                        existing_record,
                        provenance=provenance.model_dump_json(by_alias=True, exclude_none=True),
                    )
            return str(existing_file_id)

        return await self._create_descriptor_file(
            project_id=project_id,
            descriptor=descriptor,
            file_name=self._descriptor_file_name(descriptor_title),
            provenance=provenance,
        )

    async def _create_descriptor_file(
        self,
        *,
        project_id: UUID | str,
        descriptor: InlineData,
        file_name: str,
        provenance: ArtifactProvenance | None = None,
    ) -> str:
        # Distinct results may share a title; de-duplicate the leaf name so a
        # second artifact is created with a short suffix rather than failing.
        if await self._data_service.file_exists_async(
            UUID(str(project_id)),
            file_name,
            DATATABLE_PROJECT_FILE_PREFIX,
        ):
            name_part, ext = os.path.splitext(file_name)
            file_name = f"{name_part}-{str(uuid4())[:8]}{ext}"

        content = descriptor.model_dump_json(exclude_none=True, by_alias=True).encode("utf-8")
        result = await self.upload_single_file(
            project_id=UUID(str(project_id)),
            upload_file=InMemoryUploadFile(file_name, content),
            name=file_name,
            prefix=DATATABLE_PROJECT_FILE_PREFIX,
            provenance=provenance,
        )
        return str(result.id)

    @staticmethod
    def _descriptor_title(title: str) -> str:
        return os.path.splitext(os.path.basename(title))[0] or "query-result"

    @staticmethod
    def _descriptor_file_name(title: str) -> str:
        base = os.path.splitext(os.path.basename(title))[0] or "query-result"
        return f"{base}.dt"

    async def create_inline_data_file(
        self,
        project_id: UUID | str,
        inline_data: InlineData,
        name: str | None = None,
        *,
        notebook_id: UUID | str | None = None,
        query_session_id: UUID | str | None = None,
        chat_session_id: UUID | str | None = None,
        sql: str | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> FileUploadResponse:
        """Create a `.dt` inline-data file with de-duplication."""
        self._validate_project_id(project_id)
        apply_inline_data_provenance(
            inline_data,
            notebook_id=notebook_id,
            query_session_id=query_session_id,
            chat_session_id=chat_session_id,
            sql=sql,
            provenance=provenance,
        )
        file_name = name or inline_data.title or "unnamed_result"
        if not file_name.endswith(".dt"):
            file_name = f"{file_name}.dt"

        base_name = file_name
        if await self._data_service.file_exists_async(
            UUID(str(project_id)),
            file_name,
            DATATABLE_PROJECT_FILE_PREFIX,
        ):
            name_part, ext = os.path.splitext(base_name)
            short_id = str(uuid4())[:8]
            file_name = f"{name_part}-{short_id}{ext}"

        content = inline_data.model_dump_json(exclude_none=True, by_alias=True).encode("utf-8")
        result = await self.upload_single_file(
            project_id=UUID(str(project_id)),
            upload_file=InMemoryUploadFile(file_name, content),
            name=file_name,
            prefix=DATATABLE_PROJECT_FILE_PREFIX,
            provenance=provenance,
        )
        return FileUploadResponse(file=file_to_model(result))

    async def store_query_results_as_file(
        self,
        project_id: UUID | str,
        query_response: QueryResponse,
        session_id: UUID | str | None = None,
        existing_file_id: UUID | str | None = None,
        name: str | None = None,
        *,
        notebook_id: UUID | str | None = None,
        chat_session_id: UUID | str | None = None,
        sql: str | None = None,
    ) -> str | None:
        """Store query results as a `.dt` descriptor backed by a Parquet row store."""
        return await self.materialize_query_result(
            project_id,
            query_response,
            title=name,
            session_id=session_id,
            existing_file_id=existing_file_id,
            notebook_id=notebook_id,
            chat_session_id=chat_session_id,
            sql=sql,
        )

    async def update_notebook(
        self,
        project_id: UUID | str,
        file_id: UUID | str,
        notebook: NotebookDocument,
        name: str | None = None,
    ) -> FileModel:
        """Update an existing notebook file."""
        self._validate_project_id(project_id)
        # Normalize aliases before serialization: bind df_N to result-bearing
        # SQL blocks and reject invalid/duplicate renames at the save seam.
        normalize_sql_aliases(notebook)
        file_name = name
        if not file_name:
            existing = await self.get_file_by_id(UUID(str(file_id)))
            if not existing:
                raise ValueError(f"Notebook {file_id} not found")
            file_name = existing.name

        _, content = self._prepare_notebook_for_storage(notebook, file_name)
        result = await self.update_file_content(
            file_id=UUID(str(file_id)),
            upload_file=InMemoryUploadFile(file_name, content),
        )
        return file_to_model(result)

    async def update_chart(
        self,
        project_id: UUID | str,
        file_id: UUID | str,
        chart: ChartDocument,
        name: str | None = None,
        *,
        notebook_id: UUID | str | None = None,
        query_session_id: UUID | str | None = None,
        chat_session_id: UUID | str | None = None,
    ) -> FileModel:
        """Update an existing chart file."""
        self._validate_project_id(project_id)
        apply_chart_provenance(
            chart,
            notebook_id=notebook_id,
            query_session_id=query_session_id,
            chat_session_id=chat_session_id,
        )
        file_name = name
        if not file_name:
            existing = await self.get_file_by_id(UUID(str(file_id)))
            if not existing:
                raise ValueError(f"Chart {file_id} not found")
            file_name = existing.name

        _, content = self._prepare_chart_for_storage(chart, file_name)
        result = await self.update_file_content(
            file_id=UUID(str(file_id)),
            upload_file=InMemoryUploadFile(file_name, content),
        )
        return file_to_model(result)

    def _prepare_notebook_for_storage(
        self, notebook: NotebookDocument, name: str | None = None
    ) -> tuple[str, bytes]:
        """Serialize notebook for storage."""
        notebook_json = notebook.model_dump_json(exclude_none=True, by_alias=True)
        if name is not None:
            file_name = name if name.endswith(".kontext") else f"{name}.kontext"
        else:
            file_name = f"{notebook.title}.kontext"
        return file_name, notebook_json.encode("utf-8")

    def _prepare_chart_for_storage(
        self, chart: ChartDocument, name: str | None = None
    ) -> tuple[str, bytes]:
        """Serialize chart for storage."""
        chart_json = chart.model_dump_json(exclude_none=True, by_alias=True)
        if name is not None:
            file_name = name if name.endswith(".chart") else f"{name}.chart"
        else:
            file_name = f"{chart.name}.chart"
        return file_name, chart_json.encode("utf-8")

    async def get_files_by_ids(
        self, project_id: UUID | str, file_ids: Sequence[UUID | str]
    ) -> list[FileModel]:
        """Get multiple files by ID."""
        self._validate_project_id(project_id)
        uuid_ids = [UUID(str(fid)) for fid in file_ids]
        result = await self._data_service.get_files_by_ids_async(uuid_ids)
        return [file_to_model(file) for file in result]

    async def get_notebooks(
        self,
        project_id: UUID | str,
        page_index: int = 1,
        page_size: int = 20,
        filter_string: str | None = None,
    ) -> PaginatedResult[FileModel]:
        """Get paginated notebook files for a project."""
        self._validate_project_id(project_id)
        return await self.list_files(
            project_id=UUID(str(project_id)),
            page_index=page_index,
            page_size=page_size,
            filter_string=filter_string,
            file_types=[FileFormatType.NOTEBOOK],
        )

    async def list_files(
        self,
        project_id: UUID | str,
        my_files_only: bool = False,
        page_index: int = 1,
        page_size: int = 20,
        file_types: list[FileFormatType] | None = None,
        filter_string: str | None = None,
        prefix: str | None = None,
        owner_id: UUID | None = None,
        include_system_prefixes: bool = True,
    ) -> PaginatedResult[FileModel]:
        """List files for a project with pagination."""
        project_uuid = UUID(str(project_id))
        effective_owner_id = owner_id

        if my_files_only and owner_id is None:
            logger.debug("list_files called with my_files_only=True but no owner_id provided")

        if prefix is not None:
            normalized_prefix = normalize_project_file_prefix(prefix)
            if self._navigation_service.is_system_prefix(normalized_prefix):
                return await self._navigation_service.list_virtual_system_prefix(
                    project_id=project_uuid,
                    prefix=normalized_prefix,
                    page_index=page_index,
                    page_size=page_size,
                    filter_string=filter_string,
                )

            return await self._navigation_service.list_prefix_navigation(
                project_id=project_uuid,
                prefix=normalized_prefix,
                page_index=page_index,
                page_size=page_size,
                owner_id=effective_owner_id,
                file_types=file_types,
                filter_string=filter_string,
                include_system_prefixes=include_system_prefixes,
            )

        result = await self._data_service.get_paginated_files_by_project_id_async(
            project_id=project_uuid,
            page_index=page_index,
            page_size=page_size,
            filter_string=filter_string,
            prefix=prefix,
            file_types=file_types,
            owner_id=effective_owner_id,
        )
        return PaginatedResult(
            items=[file_to_model(file) for file in result.items],
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
        )

    async def create_file_metadata(
        self,
        *,
        project_id: UUID,
        name: str,
        prefix: str | None = None,
        content_type: str | None = None,
        file_type: FileFormatType | None = None,
        owner_id: UUID | None = None,
    ) -> ProjectFile:
        """Create a metadata-only file record."""
        normalized_prefix, normalized_name = self._normalize_file_identity(
            name=name,
            prefix=prefix,
        )
        if file_type is not None and not normalized_prefix:
            normalized_prefix = self._get_default_artifact_prefix(file_type)
            normalized_prefix, normalized_name = self._normalize_file_identity(
                name=normalized_name,
                prefix=normalized_prefix,
            )

        self._ensure_user_managed_prefix(normalized_prefix)

        exists = await self._data_service.file_exists_async(
            project_id,
            normalized_name,
            normalized_prefix,
        )
        if exists:
            logical_path = build_project_file_path(normalized_name, normalized_prefix)
            raise ValueError(f"File with name '{logical_path}' already exists")

        project_file = await self._data_service.create_file_async(
            project_id=project_id,
            name=normalized_name,
            prefix=normalized_prefix,
            content_type=content_type,
            size=0,
            file_type=file_type or FileFormatType.DEFAULT,
            owner_id=owner_id,
        )
        logger.info("Created file %s for project %s", project_file.id, project_id)
        return project_file

    async def update_file_metadata(
        self,
        *,
        file_id: UUID,
        name: str | None = None,
        prefix: str | None = None,
        content_type: str | None = None,
    ) -> ProjectFile:
        """Update file metadata."""
        project_file = await self._data_service.get_file_by_id_async(file_id)
        if not project_file:
            raise ValueError(f"File {file_id} not found")

        normalized_name = name
        normalized_prefix = prefix
        if name is not None or prefix is not None:
            normalized_prefix, normalized_name = self._normalize_file_identity(
                name=name or project_file.name,
                prefix=project_file.prefix if prefix is None else prefix,
            )
            self._ensure_user_managed_prefix(normalized_prefix)
            if await self._data_service.file_exists_async(
                UUID(str(project_file.project_id)),
                normalized_name,
                normalized_prefix,
                exclude_id=file_id,
            ):
                logical_path = build_project_file_path(normalized_name, normalized_prefix)
                raise ValueError(f"File with name '{logical_path}' already exists")

        project_file = await self._data_service.update_file_async(
            project_file,
            name=normalized_name,
            prefix=normalized_prefix,
            content_type=content_type,
        )
        logger.info("Updated file %s", file_id)
        return project_file

    async def update_file_schema(
        self,
        *,
        file_id: UUID,
        project_id: UUID,
        schema_json: str | None = None,
        stats_json: str | None = None,
        column_count: int | None = None,
        row_count: int | None = None,
        size: int | None = None,
        user_id: UUID | None = None,
        ip_address: str | None = None,
    ) -> ProjectFile:
        """Update a file's schema and statistics."""
        project_file = await self._data_service.get_file_by_id_async(file_id)
        if not project_file:
            raise ValueError(f"File {file_id} not found")

        project_file = await self._data_service.update_file_schema_and_stats_async(
            project_file,
            schema_definition=schema_json,
            statistics_data=stats_json,
            column_count=column_count,
            row_count=row_count,
            size=size,
        )

        f_type = safe_enum_conversion(
            FileFormatType, project_file.file_type, FileFormatType.DEFAULT
        )
        if should_trigger_profiling_job(f_type):
            event_service = EventService(project_id=project_id, queue_client=self._queue_client)
            await event_service.record_file_schema_updated(
                file_id=file_id,
                file_type=project_file.file_type,
                user_id=user_id,
                ip_address=ip_address,
            )

        logger.info("Updated schema for file %s", file_id)
        return project_file

    async def update_file_schema_and_stats(
        self,
        project_id: UUID | str,
        file_id: UUID | str,
        schema: FileSchemaModel | None = None,
        statistics: FileStatsModel | None = None,
    ) -> FileModel:
        """Protocol-friendly wrapper around schema/stat updates."""
        self._validate_project_id(project_id)
        column_count = None
        row_count = None

        if schema and schema.sub_schemas:
            column_count = sum(len(sub_schema.columns or []) for sub_schema in schema.sub_schemas)

        if statistics and statistics.sub_schemas:
            row_count = sum(
                sub_stats.estimated_row_count or 0 for sub_stats in statistics.sub_schemas
            )

        result = await self.update_file_schema(
            file_id=UUID(str(file_id)),
            project_id=UUID(str(project_id)),
            schema_json=schema.model_dump_json() if schema else None,
            stats_json=statistics.model_dump_json() if statistics else None,
            column_count=column_count,
            row_count=row_count,
        )
        return file_to_model(result)

    async def delete_file(
        self,
        *,
        file_id: UUID,
        project_id: UUID,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        triggered_by: TriggerActorModel | None = None,
    ) -> None:
        """Soft delete a file."""
        project_file = await self._data_service.get_file_by_id_async(file_id)
        if not project_file:
            raise ValueError(f"File {file_id} not found")

        file_type = project_file.file_type
        processing_target = self._processing_service.get_file_processing_target(
            filename=project_file.name,
            prefix=project_file.prefix,
            content_type=project_file.content_type,
            file_type=file_type,
        )
        file_size = project_file.size or 0
        await self._data_service.mark_file_as_deleted_async(project_file)

        if file_size > 0:
            await self._update_used_storage(project_id, -file_size)

        if processing_target == "lakehouse":
            event_service = EventService(project_id=project_id, queue_client=self._queue_client)
            await event_service.record_resource_deleted(
                file_id=file_id,
                file_type=file_type,
                user_id=user_id,
                ip_address=ip_address,
            )
        elif processing_target == "document":
            effective_triggered_by = self._resolve_trigger_actor(
                triggered_by=triggered_by,
                actor_id=user_id,
                system_actor=make_system_actor("FileDelete"),
            )
            await self._processing_service.queue_document_indexing(
                delete_file_id=file_id,
                triggered_by=effective_triggered_by,
            )

        logger.info("Soft deleted file %s", file_id)

    async def get_file_for_download(self, file_id: UUID) -> ProjectFile:
        """Get a file for download, validating it exists and has content."""
        project_file = await self._data_service.get_file_by_id_async(file_id)
        if not project_file:
            raise ValueError(f"File {file_id} not found")
        if not project_file.uri:
            raise ValueError("File has no content")
        return project_file

    async def download_file_stream(self, uri: str):
        """Download a file stream from storage."""
        try:
            return await self._storage_provider.download_file(uri)
        except Exception as exc:
            logger.error("Failed to retrieve file from storage: %s", exc)
            raise ValueError("Failed to retrieve file from storage") from exc

    async def download_file_range(self, uri: str, offset: int, length: int):
        """Download a byte range from storage."""
        try:
            return await self._storage_provider.download_range(uri, offset, length)
        except Exception as exc:
            logger.error("Failed to retrieve file range from storage: %s", exc)
            raise ValueError("Failed to retrieve file range from storage") from exc

    async def get_project_file_stats(self, project_id: UUID) -> FileStats:
        """Get file count and total size for a project."""
        self._validate_project_id(project_id)
        return await self._data_service.get_project_stats_async(project_id)
