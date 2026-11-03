"""Filesystem-style navigation for project files.

Owns the virtual folder/prefix listing used by ``FileService.list_files``:
merging database-backed files with virtual (on-disk) system prefixes and
projecting everything into ``FileModel`` trees.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from kontext.common.pagination import PaginatedResult
from kontext.common.utils.datetime_utils import normalize_datetime_utc
from kontext.common.utils.enum_utils import safe_enum_conversion
from kontext.common.utils.file_storage import (
    KNOWLEDGE_PROJECT_FILE_PREFIX,
    LAKEHOUSE_PROJECT_FILE_PREFIX,
    build_project_file_path,
    get_project_storage_path,
    get_project_vector_db_path,
    is_system_managed_project_file_prefix,
    normalize_project_file_prefix,
)
from kontext.data.models import ProjectFile
from kontext.schema import FileFormatType, FileModel

from .helpers import file_to_model


class FilePageSource(Protocol):
    """Minimal data-source capability required for navigation."""

    async def get_non_deleted_files_batch_by_cursor_async(
        self,
        project_id: UUID,
        cursor: UUID | None = None,
        batch_size: int = 100,
    ) -> Sequence[ProjectFile]: ...


class FileNavigationService:
    """Read-only navigation over project files and virtual system prefixes."""

    def __init__(self, project_id: UUID | str, data_service: FilePageSource) -> None:
        self._project_id = project_id
        self._data_service = data_service

    @staticmethod
    def _paginate_items(
        items: list[FileModel], *, page_index: int, page_size: int
    ) -> PaginatedResult[FileModel]:
        total_count = len(items)
        offset = max(page_index - 1, 0) * page_size
        return PaginatedResult(
            items=items[offset : offset + page_size],
            total_count=total_count,
            page=page_index,
            page_size=page_size,
        )

    @staticmethod
    def _file_recency_key(file: FileModel) -> datetime:
        return file.date_modified or file.date_created

    @staticmethod
    def _matches_file_filters(
        file: ProjectFile,
        *,
        owner_id: UUID | None,
        file_types: list[FileFormatType] | None,
        filter_string: str | None,
    ) -> bool:
        if owner_id is not None and file.owner_id != owner_id:
            return False

        if file_types:
            normalized_file_type = safe_enum_conversion(
                FileFormatType, file.file_type, FileFormatType.DEFAULT
            )
            if normalized_file_type not in file_types:
                return False

        return not (
            filter_string
            and filter_string.lower() not in build_project_file_path(file.name, file.prefix).lower()
        )

    @staticmethod
    def _build_folder_model(
        project_id: UUID,
        *,
        parent_prefix: str,
        name: str,
        timestamp: datetime | None = None,
    ) -> FileModel:
        normalized_parent_prefix = normalize_project_file_prefix(parent_prefix)
        path = build_project_file_path(name, normalized_parent_prefix)
        timestamp = timestamp or datetime.now(UTC)
        return FileModel(
            id=str(uuid5(NAMESPACE_URL, f"kontext-folder:{project_id}:{path}")),
            name=name,
            prefix=normalized_parent_prefix,
            path=path,
            uri=None,
            project_id=str(project_id),
            file_type=FileFormatType.DEFAULT,
            content_type="inode/directory",
            size=0,
            access_level=None,
            schema_definition=None,
            statistics_data=None,
            column_count=None,
            row_count=None,
            last_schema_update=None,
            last_stats_update=None,
            owner_id=None,
            date_created=timestamp,
            modified_by_user_id=None,
            date_modified=timestamp,
            is_deleted=False,
            date_deleted=None,
        )

    async def _list_project_files_for_navigation(self, project_id: UUID) -> list[ProjectFile]:
        files: list[ProjectFile] = []
        cursor: UUID | None = None
        while True:
            batch = await self._data_service.get_non_deleted_files_batch_by_cursor_async(
                project_id, cursor=cursor, batch_size=200
            )
            if not batch:
                break
            files.extend(batch)
            if len(batch) < 200:
                break
            cursor = UUID(str(batch[-1].id))
        return files

    async def list_prefix_navigation(
        self,
        *,
        project_id: UUID,
        prefix: str,
        page_index: int,
        page_size: int,
        owner_id: UUID | None,
        file_types: list[FileFormatType] | None,
        filter_string: str | None,
        include_system_prefixes: bool,
    ) -> PaginatedResult[FileModel]:
        normalized_prefix = normalize_project_file_prefix(prefix)
        target_parts = normalized_prefix.split("/") if normalized_prefix else []
        project_files = await self._list_project_files_for_navigation(project_id)

        child_folders: set[str] = set()
        folder_timestamps: dict[str, datetime] = {}
        direct_files: list[ProjectFile] = []
        for project_file in project_files:
            if not self._matches_file_filters(
                project_file,
                owner_id=owner_id,
                file_types=file_types,
                filter_string=filter_string,
            ):
                continue

            file_prefix_parts = (
                normalize_project_file_prefix(project_file.prefix).split("/")
                if project_file.prefix
                else []
            )
            if file_prefix_parts[: len(target_parts)] != target_parts:
                continue

            remaining_parts = file_prefix_parts[len(target_parts) :]
            if remaining_parts:
                folder_name = remaining_parts[0]
                child_folders.add(folder_name)
                file_timestamp = project_file.date_modified or project_file.date_created
                existing_timestamp = folder_timestamps.get(folder_name)
                if file_timestamp and (
                    existing_timestamp is None or file_timestamp > existing_timestamp
                ):
                    folder_timestamps[folder_name] = file_timestamp
                continue

            direct_files.append(project_file)

        folder_models = [
            self._build_folder_model(
                project_id,
                parent_prefix=normalized_prefix,
                name=folder_name,
                timestamp=(
                    normalize_datetime_utc(folder_timestamps.get(folder_name)) or datetime.now(UTC)
                ),
            )
            for folder_name in sorted(child_folders, key=str.lower)
        ]
        if normalized_prefix == "" and include_system_prefixes:
            reserved_root_folders = [
                self._build_folder_model(
                    project_id,
                    parent_prefix="",
                    name=reserved_name,
                )
                for reserved_name in (
                    KNOWLEDGE_PROJECT_FILE_PREFIX,
                    LAKEHOUSE_PROJECT_FILE_PREFIX,
                )
                if not filter_string or filter_string.lower() in reserved_name.lower()
            ]
            existing_paths = {folder.path for folder in folder_models}
            for folder in reserved_root_folders:
                if folder.path not in existing_paths:
                    folder_models.append(folder)

        folder_models.sort(key=lambda folder: folder.name.lower())
        file_models = [file_to_model(project_file) for project_file in direct_files]
        file_models.sort(key=self._file_recency_key, reverse=True)
        return self._paginate_items(
            [*folder_models, *file_models],
            page_index=page_index,
            page_size=page_size,
        )

    @staticmethod
    def _resolve_virtual_system_root(prefix: str, project_id: UUID) -> tuple[str, Path, str]:
        normalized_prefix = normalize_project_file_prefix(prefix)
        if normalized_prefix == LAKEHOUSE_PROJECT_FILE_PREFIX:
            return (
                LAKEHOUSE_PROJECT_FILE_PREFIX,
                Path(get_project_storage_path(str(project_id), "lakehouse")),
                "",
            )

        if normalized_prefix == KNOWLEDGE_PROJECT_FILE_PREFIX:
            return (
                KNOWLEDGE_PROJECT_FILE_PREFIX,
                Path(get_project_storage_path(str(project_id))),
                "",
            )

        if normalized_prefix.startswith(f"{KNOWLEDGE_PROJECT_FILE_PREFIX}/"):
            relative_prefix = normalized_prefix.removeprefix(f"{KNOWLEDGE_PROJECT_FILE_PREFIX}/")
            root_name, _, remainder = relative_prefix.partition("/")
            if root_name == "vector":
                return (
                    KNOWLEDGE_PROJECT_FILE_PREFIX,
                    Path(get_project_vector_db_path(str(project_id))).parent,
                    remainder,
                )

        if normalized_prefix.startswith(f"{LAKEHOUSE_PROJECT_FILE_PREFIX}/"):
            return (
                LAKEHOUSE_PROJECT_FILE_PREFIX,
                Path(get_project_storage_path(str(project_id), "lakehouse")),
                normalized_prefix.removeprefix(f"{LAKEHOUSE_PROJECT_FILE_PREFIX}/"),
            )

        raise ValueError(f"Unsupported system-managed prefix '{normalized_prefix}'")

    async def list_virtual_system_prefix(
        self,
        *,
        project_id: UUID,
        prefix: str,
        page_index: int,
        page_size: int,
        filter_string: str | None,
    ) -> PaginatedResult[FileModel]:
        normalized_prefix = normalize_project_file_prefix(prefix)
        if normalized_prefix == KNOWLEDGE_PROJECT_FILE_PREFIX:
            entries = [
                self._build_folder_model(
                    project_id,
                    parent_prefix=KNOWLEDGE_PROJECT_FILE_PREFIX,
                    name=name,
                )
                for name in ("vector",)
                if not filter_string or filter_string.lower() in name.lower()
            ]
            return self._paginate_items(entries, page_index=page_index, page_size=page_size)

        virtual_root, physical_root, relative_path = self._resolve_virtual_system_root(
            normalized_prefix, project_id
        )
        target_dir = physical_root / relative_path if relative_path else physical_root
        if not target_dir.exists():
            return self._paginate_items([], page_index=page_index, page_size=page_size)

        folder_entries: list[FileModel] = []
        file_entries: list[FileModel] = []
        for child in sorted(target_dir.iterdir(), key=lambda item: item.name.lower()):
            virtual_parent_prefix = normalized_prefix
            if filter_string and filter_string.lower() not in child.name.lower():
                continue
            if child.is_dir():
                folder_entries.append(
                    self._build_folder_model(
                        project_id,
                        parent_prefix=virtual_parent_prefix,
                        name=child.name,
                    )
                )
                continue

            path = build_project_file_path(child.name, virtual_parent_prefix)
            timestamp = datetime.fromtimestamp(child.stat().st_mtime, tz=UTC)
            file_entries.append(
                FileModel(
                    id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"kontext-system-file:{project_id}:{virtual_root}:{path}",
                        )
                    ),
                    name=child.name,
                    prefix=virtual_parent_prefix,
                    path=path,
                    uri=child.as_uri(),
                    project_id=str(project_id),
                    file_type=FileFormatType.DEFAULT,
                    content_type=None,
                    size=child.stat().st_size,
                    access_level=None,
                    schema_definition=None,
                    statistics_data=None,
                    column_count=None,
                    row_count=None,
                    last_schema_update=None,
                    last_stats_update=None,
                    owner_id=None,
                    date_created=timestamp,
                    modified_by_user_id=None,
                    date_modified=timestamp,
                    is_deleted=False,
                    date_deleted=None,
                )
            )

        folder_entries.sort(key=lambda folder: folder.name.lower())
        file_entries.sort(key=self._file_recency_key, reverse=True)
        return self._paginate_items(
            [*folder_entries, *file_entries],
            page_index=page_index,
            page_size=page_size,
        )

    @staticmethod
    def is_system_prefix(prefix: str) -> bool:
        return is_system_managed_project_file_prefix(prefix)
