"""File service contracts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from kontext.schema import (
    ArtifactProvenance,
    ChartDocument,
    FileFormatType,
    FileModel,
    FileSchemaModel,
    FileStatsModel,
    FileUploadResponse,
    InlineData,
    NotebookDocument,
    QueryResponse,
)

from ..pagination import PaginatedResult


class IFileServiceProtocol(Protocol):
    """Protocol defining the interface for file operations."""

    async def get_data_table_file(
        self, project_id: UUID | str, file_id: UUID | str
    ) -> InlineData: ...

    async def create_notebook(
        self,
        project_id: UUID | str,
        notebook: NotebookDocument,
        name: str | None = None,
    ) -> FileUploadResponse: ...

    async def create_chart(
        self,
        project_id: UUID | str,
        chart: ChartDocument,
        name: str | None = None,
        *,
        notebook_id: UUID | str | None = None,
        query_session_id: UUID | str | None = None,
        chat_session_id: UUID | str | None = None,
    ) -> FileUploadResponse: ...

    async def update_notebook(
        self,
        project_id: UUID | str,
        file_id: UUID | str,
        notebook: NotebookDocument,
        name: str | None = None,
    ) -> FileModel: ...

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
    ) -> FileModel: ...

    async def get_file_content(self, project_id: UUID | str, file_id: UUID | str) -> str: ...

    async def get_file_details(self, project_id: UUID | str, file_id: UUID | str) -> FileModel: ...

    async def get_files_by_ids(
        self, project_id: UUID | str, file_ids: Sequence[UUID | str]
    ) -> list[FileModel]: ...

    async def exists_by_id(self, project_id: UUID | str, file_id: UUID | str) -> bool: ...

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
    ) -> FileUploadResponse: ...

    async def get_notebooks(
        self,
        project_id: UUID | str,
        page_index: int = 1,
        page_size: int = 20,
        filter_string: str | None = None,
    ) -> PaginatedResult[FileModel]: ...

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
    ) -> PaginatedResult[FileModel]: ...

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
    ) -> str | None: ...

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
    ) -> str | None: ...

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

        Implementations build the descriptor from the Parquet footer (schema,
        row count) plus a bounded preview and keep the original bytes as the
        content-addressed row store. Used by ``kontext.save_table`` so large
        frames never round-trip through row objects.
        """
        ...

    async def get_inline_data_rows(
        self,
        project_id: UUID | str,
        file_id: UUID | str,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> InlineData: ...

    async def update_file_schema_and_stats(
        self,
        project_id: UUID | str,
        file_id: UUID | str,
        schema: FileSchemaModel | None = None,
        statistics: FileStatsModel | None = None,
    ) -> FileModel: ...
