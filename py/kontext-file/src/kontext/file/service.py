"""File-domain service implementation."""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from uuid import UUID, uuid4

from kontext.common.artifacts.provenance import (
    apply_chart_provenance,
    provenance_from_document_metadata,
)
from kontext.common.jobs.trigger_actor import system_actor as make_system_actor
from kontext.common.notebook_aliases import normalize_sql_aliases
from kontext.common.pagination import PaginatedResult
from kontext.common.utils.enum_utils import safe_enum_conversion
from kontext.common.utils.file_storage import (
    CHART_PROJECT_FILE_PREFIX,
    NOTEBOOK_PROJECT_FILE_PREFIX,
    build_project_file_path,
    normalize_project_file_prefix,
)
from kontext.data.models import ProjectFile
from kontext.data.types import FileStats
from kontext.jobs.events import EventService
from kontext.schema import (
    ChartDocument,
    DataTable,
    FileFormatType,
    FileModel,
    FileSchemaModel,
    FileStatsModel,
    FileUploadResponse,
    InlineData,
    NotebookDocument,
    TriggerActorModel,
)

from .helpers import (
    InMemoryUploadFile,
    file_to_model,
    should_trigger_profiling_job,
)
from .result_materialization import FileResultMaterializationMixin

logger = logging.getLogger(__name__)


class FileService(FileResultMaterializationMixin):
    """Business service for file management."""

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
