"""Result-store and inline-data materialization for ``FileService``."""

from __future__ import annotations

import io
import logging
import math
import os
from typing import Any
from uuid import UUID, uuid4

from kontext.common.artifacts.provenance import (
    apply_inline_data_provenance,
)
from kontext.common.constants import QueryConstants
from kontext.common.utils.file_storage import (
    DATATABLE_PROJECT_FILE_PREFIX,
    RESULT_STORE_PROJECT_FILE_PREFIX,
)
from kontext.schema import (
    ArtifactProvenance,
    DataColumn,
    DataTable,
    FileUploadResponse,
    InlineData,
    QueryResponse,
)

from .data_plane import DataTablePayload, parquet_fingerprint
from .data_plane.preview import build_preview, preview_row_budget
from .helpers import (
    InMemoryUploadFile,
    file_to_model,
)
from .upload_validation import FileUploadsMixin

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    """Null non-JSON-safe floats so descriptor JSON stays strict.

    Arrow decodes nulls as ``None``, so only NaN/inf sentinels need mapping:
    Python's ``json`` would otherwise emit bare ``NaN``/``Infinity`` tokens
    that strict clients reject.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


class FileResultMaterializationMixin(FileUploadsMixin):
    """Content-addressed result storage and inline-data materialization."""

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
