"""Tests for the query-execution alias binding adapter."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from kontext.api.services.query_execution import bind_notebook_sql_block_alias
from kontext.common.notebook_aliases import normalize_sql_aliases
from kontext.schema import (
    CodeBlock,
    CodeBlockData,
    NotebookBlock,
    NotebookDocument,
    SqlBlock,
    SqlBlockData,
)

DATA_ID = "12345678-1234-5678-9012-123456789012"
pytestmark = pytest.mark.asyncio


def _notebook(*blocks) -> NotebookDocument:
    return NotebookDocument(
        title="Manual Test",
        created=1700000000000,
        modified=1700000000000,
        blocks=[NotebookBlock(block) for block in blocks],
    )


def _sql_block(alias: str | None = None) -> SqlBlock:
    return SqlBlock(
        id=str(uuid4()),
        type="sql",
        data=SqlBlockData(code="SELECT 1", alias=alias),
    )


def _mock_file_service(stored: NotebookDocument) -> MagicMock:
    service = MagicMock()
    service.get_file_content = AsyncMock(
        return_value=stored.model_dump_json(by_alias=True, exclude_none=True)
    )
    # Mirror the real update_notebook contract: normalizes aliases in place.
    service.update_notebook = AsyncMock(
        side_effect=lambda **kwargs: (normalize_sql_aliases(kwargs["notebook"]), None)[1]
    )
    return service


async def _bind(
    monkeypatch, stored: NotebookDocument, block_id: str, service: MagicMock
) -> str | None:
    monkeypatch.setattr(
        "kontext.api.services.query_execution.create_file_service",
        lambda project_id: service,
    )
    return await bind_notebook_sql_block_alias(
        project_id=str(uuid4()),
        notebook_id=str(uuid4()),
        block_id=block_id,
        data_id=DATA_ID,
    )


async def test_bind_assigns_auto_alias_and_persists(monkeypatch) -> None:
    sql = _sql_block(alias=None)
    block_id = str(sql.id)
    stored = _notebook(sql)
    service = _mock_file_service(stored)

    alias = await _bind(monkeypatch, stored, block_id, service)

    assert alias == "df_1"
    # Binding persists the block's data ref so the document is authoritative.
    assert service.update_notebook.await_count == 1


async def test_bind_keeps_declared_alias(monkeypatch) -> None:
    sql = _sql_block(alias="sales_summary")
    block_id = str(sql.id)
    stored = _notebook(sql)

    alias = await _bind(monkeypatch, stored, block_id, _mock_file_service(stored))

    assert alias == "sales_summary"


async def test_bind_skips_non_sql_block(monkeypatch) -> None:
    code_block = CodeBlock(
        id=str(uuid4()),
        type="code",
        data=CodeBlockData(code="print('hi')", language="python"),
    )
    block_id = str(code_block.id)
    stored = _notebook(code_block)

    alias = await _bind(monkeypatch, stored, block_id, _mock_file_service(stored))

    assert alias is None


async def test_bind_survives_storage_failure(monkeypatch) -> None:
    sql = _sql_block()
    block_id = str(sql.id)
    stored = _notebook(sql)
    service = _mock_file_service(stored)
    service.get_file_content = AsyncMock(side_effect=RuntimeError("storage down"))

    alias = await _bind(monkeypatch, stored, block_id, service)

    assert alias is None
