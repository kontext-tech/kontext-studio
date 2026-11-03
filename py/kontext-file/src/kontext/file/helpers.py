"""File-domain helper types and model conversion utilities."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from kontext.common.constants import DataLakeConstants
from kontext.common.utils.datetime_utils import normalize_datetime_utc, utc_now
from kontext.common.utils.file_storage import (
    build_project_file_path,
    normalize_project_file_prefix,
)
from kontext.data.models import ProjectFile
from kontext.schema import (
    ArtifactProvenance,
    FileFormatType,
    FileModel,
    FileSchemaModel,
    FileStatsModel,
    SimpleFileEventData,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class UploadFileProtocol(Protocol):
    """Protocol for uploadable files (compatible with FastAPI UploadFile)."""

    filename: str | None
    content_type: str | None

    async def read(self) -> bytes: ...


class InMemoryUploadFile:
    """UploadFile backed by in-memory bytes (notebooks, charts, inline data)."""

    def __init__(self, filename: str, content: bytes, content_type: str = "application/json"):
        self.filename: str | None = filename
        self.content = content
        self.content_type: str | None = content_type

    async def read(self) -> bytes:
        return self.content


EXTENSION_TO_FILE_TYPE: dict[str, FileFormatType] = {
    "csv": FileFormatType.CSV,
    "tsv": FileFormatType.TSV,
    "parquet": FileFormatType.PARQUET,
    "json": FileFormatType.JSON,
    "jsonl": FileFormatType.JSONL,
    "md": FileFormatType.MARKDOWN,
    "markdown": FileFormatType.MARKDOWN,
    "pdf": FileFormatType.PDF,
    "png": FileFormatType.IMAGE,
    "jpg": FileFormatType.IMAGE,
    "jpeg": FileFormatType.IMAGE,
    "gif": FileFormatType.IMAGE,
    "webp": FileFormatType.IMAGE,
    "svg": FileFormatType.IMAGE,
    "txt": FileFormatType.TEXT,
    "sql": FileFormatType.TEXT,
    "yaml": FileFormatType.TEXT,
    "yml": FileFormatType.TEXT,
    "kontext": FileFormatType.NOTEBOOK,
    "drawio": FileFormatType.DRAWIO,
    "dt": FileFormatType.DATATABLE,
    "chart": FileFormatType.CHART,
    "xlsx": FileFormatType.EXCEL,
    "xls": FileFormatType.EXCEL,
}


def infer_file_type(filename: str, content_type: str) -> FileFormatType:
    """Infer file format from filename extension and content type."""
    if filename:
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext in EXTENSION_TO_FILE_TYPE:
            return EXTENSION_TO_FILE_TYPE[ext]

    content_type_lower = content_type.lower()

    if "csv" in content_type_lower:
        return FileFormatType.CSV
    if "json" in content_type_lower:
        if "jsonl" in content_type_lower or "lines" in content_type_lower:
            return FileFormatType.JSONL
        return FileFormatType.JSON
    if "parquet" in content_type_lower:
        return FileFormatType.PARQUET
    if "tab-separated" in content_type_lower or "tsv" in content_type_lower:
        return FileFormatType.TSV
    if "markdown" in content_type_lower:
        return FileFormatType.MARKDOWN
    if "pdf" in content_type_lower:
        return FileFormatType.PDF
    if content_type_lower.startswith("image/"):
        return FileFormatType.IMAGE
    if content_type_lower.startswith("text/"):
        return FileFormatType.TEXT
    if "excel" in content_type_lower or "spreadsheet" in content_type_lower:
        return FileFormatType.EXCEL

    return FileFormatType.DEFAULT


def should_trigger_profiling_job(file_type: FileFormatType) -> bool:
    """Check if this file type should trigger a schema profiling job."""
    return DataLakeConstants.is_supported_data_file_type(file_type)


def file_to_model(file: ProjectFile) -> FileModel:
    """Convert a ProjectFile entity to a FileModel."""
    if not file.project_id:
        raise ValueError(f"File {file.id} has no project_id")

    try:
        file_type = FileFormatType(file.file_type)
    except ValueError as exc:
        raise ValueError(f"File {file.id} has unknown file_type: {file.file_type}") from exc

    if not file.date_created:
        raise ValueError(f"File {file.id} has no date_created")

    schema_definition = None
    if file.schema_definition:
        schema_definition = FileSchemaModel.model_validate_json(file.schema_definition)

    statistics_data = None
    if file.statistics_data:
        try:
            statistics_data = FileStatsModel.model_validate_json(file.statistics_data)
        except Exception as exc:
            logger.warning(
                "Failed to parse statistics for file %s: %s. "
                "This likely means the Alembic migration hasn't run yet. "
                "Statistics will be skipped for now.",
                file.id,
                exc,
            )
            statistics_data = None

    provenance = None
    if file.provenance:
        try:
            provenance = ArtifactProvenance.model_validate_json(file.provenance)
        except Exception as exc:
            logger.warning(
                "Failed to parse provenance for file %s: %s. The record "
                "predates provenance stamping or the migration hasn't run; "
                "the badge will be omitted.",
                file.id,
                exc,
            )
            provenance = None

    return FileModel(
        id=str(file.id),
        name=file.name,
        prefix=normalize_project_file_prefix(file.prefix),
        path=build_project_file_path(file.name, file.prefix),
        uri=file.uri,
        project_id=str(file.project_id),
        file_type=file_type,
        content_type=file.content_type,
        size=file.size,
        schema_definition=schema_definition,
        statistics_data=statistics_data,
        column_count=file.column_count,
        row_count=file.row_count,
        last_schema_update=normalize_datetime_utc(file.last_schema_update),
        last_stats_update=normalize_datetime_utc(file.last_stats_update),
        owner_id=str(file.owner_id) if file.owner_id else None,
        date_created=normalize_datetime_utc(file.date_created) or utc_now(),
        modified_by_user_id=(str(file.modified_by_user_id) if file.modified_by_user_id else None),
        date_modified=normalize_datetime_utc(file.date_modified),
        is_deleted=file.is_deleted,
        date_deleted=normalize_datetime_utc(file.date_deleted),
        provenance=provenance,
    )


def file_to_simple_data(file: ProjectFile) -> SimpleFileEventData:
    """Convert a ProjectFile entity to SimpleFileEventData for event recording."""
    try:
        file_type = FileFormatType(file.file_type)
    except ValueError:
        file_type = FileFormatType.DEFAULT

    return SimpleFileEventData(id=str(file.id), name=file.name, file_type=file_type)


@dataclass
class FileData:
    """Pre-read file data for upload."""

    filename: str
    content: bytes
    content_type: str
    file_type: FileFormatType
    prefix: str = ""


@dataclass
class StorageUploadResult:
    """Result of uploading a file to storage."""

    filename: str
    uri: str
    size: int
    content_type: str
    file_type: FileFormatType
    prefix: str = ""
