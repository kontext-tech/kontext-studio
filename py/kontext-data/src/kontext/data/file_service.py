"""File data service for CRUD operations on project files.

This service uses sync SQLAlchemy sessions with asyncio.to_thread() wrappers
to avoid greenlet context issues when mixing DB operations with async I/O.

Each operation creates and manages its own session within the to_thread() call
to ensure thread-safe session handling and atomic transactions.
"""

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update

from kontext.common.pagination import PaginatedResult
from kontext.common.utils.file_storage import normalize_project_file_prefix
from kontext.data.models import ProjectFile
from kontext.schema import FileFormatType

from .base_service import ProjectDataService
from .types import FileStats

__all__ = ["FileDataService", "FileStats", "PaginatedResult"]


class FileDataService(ProjectDataService):
    """Service for managing ProjectFile entities in project databases.

    This service uses sync SQLAlchemy operations internally and provides
    async wrappers via asyncio.to_thread() for FastAPI compatibility.

    Each operation creates and manages its own session to ensure thread-safe
    session handling and atomic transactions.
    """

    # =========================================================================
    # Async Interface (for FastAPI compatibility)
    # =========================================================================

    async def create_file_async(
        self,
        *,
        project_id: UUID | None,
        name: str,
        content_type: str | None,
        prefix: str | None = None,
        size: int,
        file_type: FileFormatType,
        uri: str | None = None,
        schema_definition: str | None = None,
        statistics_data: str | None = None,
        column_count: int | None = None,
        row_count: int | None = None,
        owner_id: UUID | None = None,
        provenance: str | None = None,
    ) -> ProjectFile:
        """Create a new file (async wrapper)."""
        return await asyncio.to_thread(
            self._create_file_sync,
            project_id=project_id,
            name=name,
            prefix=prefix,
            content_type=content_type,
            size=size,
            file_type=file_type,
            uri=uri,
            schema_definition=schema_definition,
            statistics_data=statistics_data,
            column_count=column_count,
            row_count=row_count,
            owner_id=owner_id,
            provenance=provenance,
        )

    async def update_file_async(
        self,
        file: ProjectFile,
        *,
        name: str | None = None,
        prefix: str | None = None,
        uri: str | None = None,
        content_type: str | None = None,
        file_type: FileFormatType | None = None,
        size: int | None = None,
        owner_id: UUID | None = None,
        modified_by_user_id: UUID | None = None,
        provenance: str | None = None,
    ) -> ProjectFile:
        """Update a file's basic fields (async wrapper)."""
        return await asyncio.to_thread(
            self._update_file_sync,
            file,
            name=name,
            prefix=prefix,
            uri=uri,
            content_type=content_type,
            file_type=file_type,
            size=size,
            owner_id=owner_id,
            modified_by_user_id=modified_by_user_id,
            provenance=provenance,
        )

    async def get_file_by_id_async(self, file_id: UUID) -> ProjectFile | None:
        """Get a file by ID (async wrapper)."""
        return await asyncio.to_thread(self._get_file_by_id_sync, file_id)

    async def get_paginated_files_by_project_id_async(
        self,
        project_id: UUID,
        page_index: int = 1,
        page_size: int = 20,
        include_deleted: bool = False,
        filter_string: str | None = None,
        prefix: str | None = None,
        file_types: list[FileFormatType] | None = None,
        owner_id: UUID | None = None,
    ) -> PaginatedResult[ProjectFile]:
        """Get paginated files for a project (async wrapper)."""
        return await asyncio.to_thread(
            self._get_paginated_files_by_project_id_sync,
            project_id,
            page_index,
            page_size,
            include_deleted,
            filter_string,
            prefix,
            file_types,
            owner_id=owner_id,
        )

    async def get_project_stats_async(self, project_id: UUID) -> FileStats:
        """Get file statistics for a project (async wrapper).

        Returns a data-layer `FileStats` DTO (file count and total size).
        """
        return await asyncio.to_thread(self._get_project_stats_sync, project_id)

    async def get_non_deleted_file_count_async(self, project_id: UUID) -> int:
        """Get count of non-deleted files for a project (async wrapper)."""
        return await asyncio.to_thread(self._get_non_deleted_file_count_sync, project_id)

    async def get_non_deleted_files_batch_by_cursor_async(
        self, project_id: UUID, cursor: UUID | None = None, batch_size: int = 100
    ) -> Sequence[ProjectFile]:
        """Get non-deleted files in batches (async wrapper)."""
        return await asyncio.to_thread(
            self._get_non_deleted_files_batch_by_cursor_sync,
            project_id,
            cursor,
            batch_size,
        )

    async def mark_file_as_deleted_async(self, file: ProjectFile) -> ProjectFile:
        """Soft delete a file (async wrapper)."""
        return await asyncio.to_thread(self._mark_file_as_deleted_sync, file)

    async def update_file_size_async(self, file: ProjectFile, *, size: int) -> ProjectFile:
        """Update a file's size (async wrapper)."""
        return await asyncio.to_thread(self._update_file_size_sync, file, size=size)

    async def get_files_by_ids_async(self, file_ids: list[UUID]) -> Sequence[ProjectFile]:
        """Get multiple files by their IDs (async wrapper)."""
        return await asyncio.to_thread(self._get_files_by_ids_sync, file_ids)

    async def get_files_for_schema_consolidation_async(
        self, project_id: UUID, file_types: list[FileFormatType] | None = None
    ) -> Sequence[ProjectFile]:
        """Get files that need schema consolidation (async wrapper)."""
        return await asyncio.to_thread(
            self._get_files_for_schema_consolidation_sync, project_id, file_types
        )

    async def update_file_schema_and_stats_async(
        self,
        file: ProjectFile,
        *,
        schema_definition: str | None = None,
        statistics_data: str | None = None,
        column_count: int | None = None,
        row_count: int | None = None,
        size: int | None = None,
    ) -> ProjectFile:
        """Update a file's schema and statistics (async wrapper)."""
        return await asyncio.to_thread(
            self._update_file_schema_and_stats_sync,
            file,
            schema_definition=schema_definition,
            statistics_data=statistics_data,
            column_count=column_count,
            row_count=row_count,
            size=size,
        )

    async def delete_file_async(self, file: ProjectFile) -> None:
        """Hard delete a file (async wrapper)."""
        await asyncio.to_thread(self._delete_file_sync, file)

    async def get_file_by_name_and_project_id_async(
        self, project_id: UUID, name: str, prefix: str | None = None
    ) -> ProjectFile | None:
        """Get a file by name and project ID (async wrapper)."""
        return await asyncio.to_thread(
            self._get_file_by_name_and_project_id_sync, project_id, name, prefix
        )

    async def file_exists_async(
        self,
        project_id: UUID,
        name: str,
        prefix: str | None = None,
        exclude_id: UUID | None = None,
    ) -> bool:
        """Check if a file with the given name exists (async wrapper)."""
        return await asyncio.to_thread(self._file_exists_sync, project_id, name, prefix, exclude_id)

    async def file_exists_by_id_async(self, project_id: UUID, file_id: UUID) -> bool:
        """Check if a file with the given ID exists (async wrapper)."""
        return await asyncio.to_thread(self._file_exists_by_id_sync, project_id, file_id)

    async def bulk_update_schemas_async(self, file_ids: list[UUID], schema_definition: str) -> int:
        """Bulk update schema for multiple files (async wrapper)."""
        return await asyncio.to_thread(self._bulk_update_schemas_sync, file_ids, schema_definition)

    # =========================================================================
    # Sync Implementation
    # =========================================================================

    def _create_file_sync(
        self,
        *,
        project_id: UUID | None,
        name: str,
        content_type: str | None,
        prefix: str | None = None,
        size: int,
        file_type: FileFormatType,
        uri: str | None = None,
        schema_definition: str | None = None,
        statistics_data: str | None = None,
        column_count: int | None = None,
        row_count: int | None = None,
        owner_id: UUID | None = None,
        provenance: str | None = None,
    ) -> ProjectFile:
        """Create a new file.

        Args:
            project_id: The project ID this file belongs to (nullable).
            name: The file name.
            content_type: The MIME content type.
            size: The file size in bytes.
            file_type: The file type.
            uri: Optional storage URI.
            schema_definition: Optional JSON schema string.
            statistics_data: Optional JSON statistics string.
            column_count: Optional column count.
            row_count: Optional row count.
            owner_id: Optional owner user ID.
            provenance: Optional JSON ``ArtifactProvenance`` dump (camelCase).

        Returns:
            The created ProjectFile entity.
        """
        with self._session_scope() as session:
            file = ProjectFile(
                project_id=project_id,
                name=name,
                prefix=normalize_project_file_prefix(prefix),
                content_type=content_type,
                size=size,
                file_type=file_type.value if file_type else None,
                uri=uri,
                schema_definition=schema_definition,
                statistics_data=statistics_data,
                column_count=column_count,
                row_count=row_count,
                owner_id=owner_id,
                provenance=provenance,
            )
            session.add(file)
            session.flush()
            # Need to expunge to detach from session before returning
            session.expunge(file)
            return file

    def _update_file_sync(
        self,
        file: ProjectFile,
        *,
        name: str | None = None,
        prefix: str | None = None,
        uri: str | None = None,
        content_type: str | None = None,
        file_type: FileFormatType | None = None,
        size: int | None = None,
        owner_id: UUID | None = None,
        modified_by_user_id: UUID | None = None,
        provenance: str | None = None,
    ) -> ProjectFile:
        """Update a file's basic fields.

        Args:
            file: The file to update.
            name: Optional new name.
            uri: Optional new URI.
            content_type: Optional new content type.
            size: Optional new size in bytes.
            owner_id: Optional new owner ID.
            modified_by_user_id: Optional user who made the change.
            provenance: Optional replacement JSON ``ArtifactProvenance`` dump.

        Returns:
            The updated ProjectFile entity.
        """
        with self._session_scope() as session:
            # Merge the detached file into this session
            file = session.merge(file)
            if name is not None:
                file.name = name
            if prefix is not None:
                file.prefix = normalize_project_file_prefix(prefix)
            if uri is not None:
                file.uri = uri
            if content_type is not None:
                file.content_type = content_type
            if file_type is not None:
                file.file_type = file_type.value
            if size is not None:
                file.size = size
            if owner_id is not None:
                file.owner_id = owner_id
            if modified_by_user_id is not None:
                file.modified_by_user_id = modified_by_user_id
            if provenance is not None:
                file.provenance = provenance

            # Explicitly set modification timestamp
            file.date_modified = datetime.now(UTC)

            session.flush()
            session.expunge(file)
            return file

    def _get_file_by_id_sync(self, file_id: UUID) -> ProjectFile | None:
        """Get a file by ID.

        Args:
            file_id: The file ID.

        Returns:
            The ProjectFile entity if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            result = session.execute(
                select(ProjectFile)
                .where(
                    ProjectFile.id == file_id,
                    ProjectFile.project_id == self.project_uuid,
                )
                .limit(1)
            )
            file = result.scalar_one_or_none()
            if file:
                return self._make_detached(session, file)
            return None

    def _get_paginated_files_by_project_id_sync(
        self,
        project_id: UUID,
        page_index: int = 1,
        page_size: int = 20,
        include_deleted: bool = False,
        filter_string: str | None = None,
        prefix: str | None = None,
        file_types: list[FileFormatType] | None = None,
        owner_id: UUID | None = None,
    ) -> PaginatedResult[ProjectFile]:
        """Get paginated files for a project.

        Args:
            project_id: The project ID.
            page_index: The page number (1-indexed).
            page_size: The number of items per page.
            include_deleted: Whether to include soft-deleted files.
            filter_string: Optional filter to search by name.
            file_types: Optional list of file types to filter by.
            owner_id: Optional owner user ID filter.

        Returns:
            PaginatedResult containing files and pagination info.
        """
        with self._session_scope(commit=False) as session:
            # Base query
            stmt = select(ProjectFile).where(ProjectFile.project_id == project_id)
            count_stmt = select(func.count(ProjectFile.id)).where(
                ProjectFile.project_id == project_id
            )

            if not include_deleted:
                stmt = stmt.where(ProjectFile.is_deleted == False)  # noqa: E712
                count_stmt = count_stmt.where(ProjectFile.is_deleted == False)  # noqa: E712

            # Apply owner filter
            if owner_id is not None:
                stmt = stmt.where(ProjectFile.owner_id == owner_id)
                count_stmt = count_stmt.where(ProjectFile.owner_id == owner_id)

            # Apply name filter
            if filter_string:
                stmt = stmt.where(ProjectFile.name.ilike(f"%{filter_string}%"))
                count_stmt = count_stmt.where(ProjectFile.name.ilike(f"%{filter_string}%"))

            if prefix is not None:
                normalized_prefix = normalize_project_file_prefix(prefix)
                stmt = stmt.where(ProjectFile.prefix == normalized_prefix)
                count_stmt = count_stmt.where(ProjectFile.prefix == normalized_prefix)

            # Apply file type filter
            if file_types:
                stmt = stmt.where(ProjectFile.file_type.in_(file_types))
                count_stmt = count_stmt.where(ProjectFile.file_type.in_(file_types))

            # Get total count
            total_result = session.execute(count_stmt)
            total_count = total_result.scalar() or 0

            # Get paginated items
            offset = (page_index - 1) * page_size
            stmt = stmt.order_by(ProjectFile.date_created.desc()).offset(offset).limit(page_size)
            result = session.execute(stmt)
            items = list(result.scalars().all())

            # Expunge all items to detach from session
            for item in items:
                session.expunge(item)

            return PaginatedResult(
                items=items,
                total_count=total_count,
                page=page_index,
                page_size=page_size,
            )

    def _get_project_stats_sync(self, project_id: UUID) -> FileStats:
        """Get file statistics for a project.

        Args:
            project_id: The project ID.

        Returns:
            FileStats with file_count and total_size_in_bytes.
        """
        with self._session_scope(commit=False) as session:
            # Query file statistics
            file_result = session.execute(
                select(
                    func.count(ProjectFile.id).label("file_count"),
                    func.coalesce(func.sum(ProjectFile.size), 0).label("total_size"),
                ).where(
                    ProjectFile.project_id == project_id,
                    ProjectFile.is_deleted == False,  # noqa: E712
                )
            )
            file_row = file_result.one()

            # Return file-only statistics as a data-layer DTO
            return FileStats(
                file_count=file_row.file_count or 0,
                total_size_in_bytes=int(file_row.total_size or 0),
            )

    def _get_non_deleted_file_count_sync(self, project_id: UUID) -> int:
        """Get count of non-deleted files for a project.

        Args:
            project_id: The project ID.

        Returns:
            Number of non-deleted files.
        """
        with self._session_scope(commit=False) as session:
            result = session.execute(
                select(func.count(ProjectFile.id)).where(
                    ProjectFile.project_id == project_id,
                    ProjectFile.is_deleted == False,  # noqa: E712
                )
            )
            return result.scalar() or 0

    def _get_non_deleted_files_batch_by_cursor_sync(
        self, project_id: UUID, cursor: UUID | None = None, batch_size: int = 100
    ) -> Sequence[ProjectFile]:
        """Get non-deleted files in batches using cursor pagination.

        Args:
            project_id: The project ID.
            cursor: The last file ID from the previous batch (exclusive).
            batch_size: The number of items per batch.

        Returns:
            List of ProjectFile entities.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(ProjectFile)
                .where(
                    ProjectFile.project_id == project_id,
                    ProjectFile.is_deleted == False,  # noqa: E712
                )
                .order_by(ProjectFile.id)
                .limit(batch_size)
            )

            if cursor is not None:
                stmt = stmt.where(ProjectFile.id > cursor)

            result = session.execute(stmt)
            files = list(result.scalars().all())

            # Expunge all files to detach from session
            for file in files:
                session.expunge(file)

            return files

    def _mark_file_as_deleted_sync(self, file: ProjectFile) -> ProjectFile:
        """Soft delete a file by setting is_deleted and date_deleted.

        Args:
            file: The file to soft delete.

        Returns:
            The updated ProjectFile entity.
        """
        with self._session_scope() as session:
            file = session.merge(file)
            file.is_deleted = True
            file.date_deleted = datetime.now(UTC)
            session.flush()
            session.expunge(file)
            return file

    def _update_file_size_sync(self, file: ProjectFile, *, size: int) -> ProjectFile:
        """Update a file's size.

        Args:
            file: The file to update.
            size: The new size in bytes.

        Returns:
            The updated ProjectFile entity.
        """
        with self._session_scope() as session:
            file = session.merge(file)
            file.size = size
            session.flush()
            session.expunge(file)
            return file

    def _get_files_by_ids_sync(self, file_ids: list[UUID]) -> Sequence[ProjectFile]:
        """Get multiple files by their IDs.

        Args:
            file_ids: List of file IDs.

        Returns:
            List of ProjectFile entities.
        """
        if not file_ids:
            return []

        with self._session_scope(commit=False) as session:
            result = session.execute(
                select(ProjectFile).where(
                    ProjectFile.id.in_(file_ids),
                    ProjectFile.project_id == self.project_uuid,
                )
            )
            files = list(result.scalars().all())

            # Detach all entities
            for file in files:
                self._make_detached(session, file)

            return files

    def _get_files_for_schema_consolidation_sync(
        self, project_id: UUID, file_types: list[FileFormatType] | None = None
    ) -> Sequence[ProjectFile]:
        """Get files that need schema consolidation.

        Gets non-deleted files with schema data.

        Args:
            project_id: The project ID.
            file_types: Optional list of file types to filter.

        Returns:
            List of ProjectFile entities with schemas.
        """
        with self._session_scope(commit=False) as session:
            stmt = select(ProjectFile).where(
                ProjectFile.project_id == project_id,
                ProjectFile.is_deleted == False,  # noqa: E712
                ProjectFile.schema_definition.isnot(None),
            )

            if file_types:
                stmt = stmt.where(ProjectFile.file_type.in_(file_types))

            stmt = stmt.order_by(ProjectFile.name)
            result = session.execute(stmt)
            files = list(result.scalars().all())

            # Detach all entities
            for file in files:
                self._make_detached(session, file)

            return files

    def _update_file_schema_and_stats_sync(
        self,
        file: ProjectFile,
        *,
        schema_definition: str | None = None,
        statistics_data: str | None = None,
        column_count: int | None = None,
        row_count: int | None = None,
        size: int | None = None,
    ) -> ProjectFile:
        """Update a file's schema and statistics.

        Args:
            file: The file to update.
            schema_definition: Optional new JSON schema string.
            statistics_data: Optional new JSON statistics string.
            column_count: Optional new column count.
            row_count: Optional new row count.
            size: Optional new size in bytes.

        Returns:
            The updated ProjectFile entity.
        """
        with self._session_scope() as session:
            file = session.merge(file)
            if schema_definition is not None:
                file.schema_definition = schema_definition
            if statistics_data is not None:
                file.statistics_data = statistics_data
            if column_count is not None:
                file.column_count = column_count
            if row_count is not None:
                file.row_count = row_count
            if size is not None:
                file.size = size
            session.flush()
            session.expunge(file)
            return file

    def _delete_file_sync(self, file: ProjectFile) -> None:
        """Hard delete a file.

        Args:
            file: The file to delete.
        """
        with self._session_scope() as session:
            file = session.merge(file)
            session.delete(file)
            session.flush()

    def _get_file_by_name_and_project_id_sync(
        self, project_id: UUID, name: str, prefix: str | None = None
    ) -> ProjectFile | None:
        """Get a file by name and project ID.

        Args:
            project_id: The project ID.
            name: The file name.

        Returns:
            The ProjectFile entity if found, None otherwise.
        """
        with self._session_scope(commit=False) as session:
            normalized_prefix = normalize_project_file_prefix(prefix)
            result = session.execute(
                select(ProjectFile)
                .where(
                    ProjectFile.project_id == project_id,
                    ProjectFile.prefix == normalized_prefix,
                    ProjectFile.name == name,
                    ProjectFile.is_deleted == False,  # noqa: E712
                )
                .limit(1)
            )
            file = result.scalar_one_or_none()
            if file:
                session.expunge(file)
            return file

    def _file_exists_sync(
        self,
        project_id: UUID,
        name: str,
        prefix: str | None = None,
        exclude_id: UUID | None = None,
    ) -> bool:
        """Check if a file with the given name exists in the project.

        Args:
            project_id: The project ID.
            name: The file name to check.
            exclude_id: Optional ID to exclude from the check (for updates).

        Returns:
            True if a file with the name exists, False otherwise.
        """
        with self._session_scope(commit=False) as session:
            normalized_prefix = normalize_project_file_prefix(prefix)
            stmt = select(ProjectFile.id).where(
                ProjectFile.project_id == project_id,
                ProjectFile.prefix == normalized_prefix,
                ProjectFile.name == name,
                ProjectFile.is_deleted == False,  # noqa: E712
            )
            if exclude_id is not None:
                stmt = stmt.where(ProjectFile.id != exclude_id)
            stmt = stmt.limit(1)
            result = session.execute(stmt)
            return result.scalar_one_or_none() is not None

    def _file_exists_by_id_sync(self, project_id: UUID, file_id: UUID) -> bool:
        """Check if a file with the given ID exists in the project.

        Args:
            project_id: The project ID.
            file_id: The file ID to check.

        Returns:
            True if the file exists and belongs to the project, False otherwise.
        """
        with self._session_scope(commit=False) as session:
            stmt = (
                select(ProjectFile.id)
                .where(
                    ProjectFile.project_id == project_id,
                    ProjectFile.id == file_id,
                    ProjectFile.is_deleted == False,  # noqa: E712
                )
                .limit(1)
            )
            result = session.execute(stmt)
            return result.scalar_one_or_none() is not None

    def _bulk_update_schemas_sync(self, file_ids: list[UUID], schema_definition: str) -> int:
        """Bulk update schema for multiple files.

        Args:
            file_ids: List of file IDs to update.
            schema_definition: The schema JSON string to set.

        Returns:
            Number of updated files.
        """
        if not file_ids:
            return 0

        with self._session_scope() as session:
            result = session.execute(
                update(ProjectFile)
                .where(
                    ProjectFile.id.in_(file_ids),
                    ProjectFile.project_id == self.project_uuid,
                )
                .values(schema_definition=schema_definition)
            )
            session.flush()
            # `rowcount` can be None depending on the DB/driver; coerce to int
            # Use getattr to avoid static type errors with Result vs CursorResult
            rowcount = getattr(result, "rowcount", 0)
            return int(rowcount or 0)
