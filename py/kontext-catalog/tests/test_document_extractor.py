"""Tests for document extraction helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from kontext.catalog.indexing.document_extractor import (
    DocumentExtractor,
    is_indexable_document_upload,
)


def test_text_uploads_use_direct_utf8_extraction() -> None:
    extractor = DocumentExtractor()

    result = extractor.extract(
        "notes.md",
        "text/markdown",
        b"# Heading\nUseful lakehouse note.\n",
        file_type="Markdown",
    )

    assert result.error_message is None
    assert result.skip_reason is None
    assert result.parser_name == "direct_utf8"
    assert "Useful lakehouse note." in (result.text or "")


def test_pdf_uploads_use_markitdown() -> None:
    extractor = DocumentExtractor()
    fake_result = MagicMock()
    fake_result.text_content = "PDF extracted text"

    with patch("markitdown.MarkItDown") as mock_markitdown:
        mock_markitdown.return_value.convert_stream.return_value = fake_result
        result = extractor.extract(
            "report.pdf",
            "application/pdf",
            b"%PDF-1.7 fake",
            file_type="PDF",
        )

    assert result.error_message is None
    assert result.skip_reason is None
    assert result.parser_name == "markitdown"
    assert result.text == "PDF extracted text"


def test_data_file_uploads_are_not_indexable_documents() -> None:
    assert not is_indexable_document_upload(
        filename="orders.csv",
        content_type="text/csv",
        file_type="CSV",
    )


def test_invalid_utf8_text_is_skipped() -> None:
    extractor = DocumentExtractor()

    result = extractor.extract(
        "notes.txt",
        "text/plain",
        b"\xff\xfe\x00",
        file_type="Text",
    )

    assert result.text is None
    assert result.skip_reason == "text file is not valid UTF-8"
