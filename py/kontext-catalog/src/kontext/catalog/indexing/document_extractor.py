"""Document extraction helpers for uploaded project files."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from kontext.schema import FileFormatType

_DATA_FILE_TYPES = frozenset(
    {
        FileFormatType.CSV,
        FileFormatType.TSV,
        FileFormatType.PARQUET,
        FileFormatType.JSON,
        FileFormatType.JSONL,
        FileFormatType.EXCEL,
    }
)
_INDEXABLE_FILE_TYPES = frozenset(
    {
        FileFormatType.MARKDOWN,
        FileFormatType.TEXT,
        FileFormatType.PDF,
    }
)
_NON_INDEXABLE_FILE_TYPES = frozenset(
    {
        FileFormatType.IMAGE,
        FileFormatType.DRAWIO,
        FileFormatType.NOTEBOOK,
        FileFormatType.CHART,
        FileFormatType.DATATABLE,
    }
)
_DATA_EXTENSIONS = frozenset(
    {
        ".csv",
        ".tsv",
        ".parquet",
        ".json",
        ".jsonl",
        ".xlsx",
        ".xls",
    }
)
_TEXT_EXTENSIONS = frozenset(
    {
        ".md",
        ".markdown",
        ".txt",
        ".sql",
        ".yaml",
        ".yml",
    }
)
_PDF_EXTENSIONS = frozenset({".pdf"})
_DATA_CONTENT_TYPE_HINTS = (
    "csv",
    "tab-separated",
    "parquet",
    "json",
    "spreadsheet",
    "excel",
)


def _normalize_file_type(
    file_type: FileFormatType | str | None,
) -> FileFormatType | None:
    if file_type is None:
        return None
    if isinstance(file_type, FileFormatType):
        return file_type
    try:
        return FileFormatType(str(file_type))
    except ValueError:
        return None


def is_indexable_document_upload(
    *,
    filename: str | None,
    content_type: str | None,
    file_type: FileFormatType | str | None = None,
) -> bool:
    """Return True when the upload should be indexed into `scope=document`."""

    normalized_file_type = _normalize_file_type(file_type)
    extension = Path(filename or "").suffix.lower()
    content_type_lower = (content_type or "").lower()

    if normalized_file_type in _DATA_FILE_TYPES:
        return False
    if normalized_file_type in _NON_INDEXABLE_FILE_TYPES:
        return False
    if extension in _DATA_EXTENSIONS:
        return False
    if any(hint in content_type_lower for hint in _DATA_CONTENT_TYPE_HINTS):
        return False

    if normalized_file_type in _INDEXABLE_FILE_TYPES:
        return True
    if extension in _TEXT_EXTENSIONS or extension in _PDF_EXTENSIONS:
        return True
    if content_type_lower == "application/pdf":
        return True
    return bool(content_type_lower.startswith("text/"))


@dataclass(frozen=True)
class ExtractionResult:
    """Result of a document extraction attempt."""

    text: str | None = None
    parser_name: str | None = None
    skip_reason: str | None = None
    error_message: str | None = None


class DocumentExtractor:
    """Extract searchable text from knowledge-indexable project files."""

    def extract(
        self,
        filename: str | None,
        content_type: str | None,
        content_bytes: bytes,
        *,
        file_type: FileFormatType | str | None = None,
    ) -> ExtractionResult:
        if not content_bytes:
            return ExtractionResult(skip_reason="file is empty")

        if not is_indexable_document_upload(
            filename=filename,
            content_type=content_type,
            file_type=file_type,
        ):
            return ExtractionResult(skip_reason="file type is not supported for document indexing")

        extension = Path(filename or "").suffix.lower()
        normalized_file_type = _normalize_file_type(file_type)
        content_type_lower = (content_type or "").lower()

        if (
            normalized_file_type is FileFormatType.PDF
            or extension in _PDF_EXTENSIONS
            or content_type_lower == "application/pdf"
        ):
            return self._extract_pdf(content_bytes)

        return self._extract_text(content_bytes)

    def _extract_text(self, content_bytes: bytes) -> ExtractionResult:
        try:
            text = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            return ExtractionResult(
                parser_name="direct_utf8",
                skip_reason="text file is not valid UTF-8",
            )

        normalized_text = text.strip()
        if not normalized_text:
            return ExtractionResult(
                parser_name="direct_utf8",
                skip_reason="extracted text is empty",
            )
        return ExtractionResult(text=normalized_text, parser_name="direct_utf8")

    def _extract_pdf(self, content_bytes: bytes) -> ExtractionResult:
        try:
            from markitdown import MarkItDown

            converter = MarkItDown()
            result = converter.convert_stream(
                BytesIO(content_bytes),
                file_extension=".pdf",
            )
        except Exception as exc:  # pragma: no cover - library behavior
            return ExtractionResult(
                parser_name="markitdown",
                error_message=f"markitdown extraction failed: {exc}",
            )

        text = (result.text_content or "").strip()
        if not text:
            return ExtractionResult(
                parser_name="markitdown",
                skip_reason="PDF extraction produced no text",
            )
        return ExtractionResult(text=text, parser_name="markitdown")
