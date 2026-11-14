"""File upload validation and ingestion pipeline for ``FileService``."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from kontext.common.constants import DataLakeConstants
from kontext.common.jobs.trigger_actor import system_actor as make_system_actor
from kontext.common.utils.file_storage import (
    build_project_file_path,
    is_system_managed_project_file_prefix,
)
from kontext.data.models import ProjectFile
from kontext.jobs.events import EventService
from kontext.schema import (
    ArtifactProvenance,
    FileFormatType,
    SimpleFileEventData,
    TriggerActorModel,
)

from .helpers import (
    FileData,
    StorageUploadResult,
    UploadFileProtocol,
    file_to_simple_data,
    infer_file_type,
)
from .processing import FileProcessingPlan
from .service_base import FileServiceCore

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


class FileUploadsMixin(FileServiceCore):
    """Upload validation, persistence, and post-upload dispatch."""

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
