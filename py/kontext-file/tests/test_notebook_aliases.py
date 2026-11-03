"""Tests for notebook-scoped SQL block aliases (df_N binding and validation)."""

from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from kontext.common.notebook_aliases import (
    collect_existing_aliases,
    next_auto_alias,
    normalize_sql_aliases,
)
from kontext.schema import (
    BlockData,
    DataRef,
    NotebookBlock,
    NotebookDocument,
    SqlBlock,
    SqlBlockData,
)


def _sql_block(
    *,
    code: str = "SELECT 1",
    data_id: str | None = None,
    alias: str | None = None,
) -> SqlBlock:
    return SqlBlock(
        id=str(uuid4()),
        type="sql",
        data=SqlBlockData(
            code=code,
            data_ref=DataRef(data_id=data_id) if data_id else None,
            alias=alias,
        ),
    )


def _notebook(*blocks) -> NotebookDocument:
    return NotebookDocument(
        title="Test Notebook",
        created=1700000000000,
        modified=1700000000000,
        blocks=[NotebookBlock(block) for block in blocks],
    )


def _sql_root(notebook: NotebookDocument, index: int = 0) -> SqlBlock:
    """Typed accessor: these fixtures only create SQL blocks."""
    return cast(SqlBlock, notebook.blocks[index].root)


def test_assigns_first_auto_alias_to_result_bearing_block() -> None:
    notebook = _notebook(_sql_block(data_id="12345678-1234-5678-9012-123456789012"))

    assigned = normalize_sql_aliases(notebook)

    assert assigned == ["df_1"]
    assert _sql_root(notebook).data.alias == "df_1"


def test_auto_alias_is_monotonic_and_never_renumbers() -> None:
    notebook = _notebook(
        _sql_block(data_id="12345678-1234-5678-9012-123456789012", alias="df_3"),
        _sql_block(data_id="22345678-1234-5678-9012-123456789012"),
    )

    assigned = normalize_sql_aliases(notebook)

    assert assigned == ["df_4"]
    assert _sql_root(notebook).data.alias == "df_3"
    assert _sql_root(notebook, 1).data.alias == "df_4"
    assert next_auto_alias(notebook) == "df_5"


def test_keeps_declared_free_name_alias() -> None:
    notebook = _notebook(
        _sql_block(data_id="12345678-1234-5678-9012-123456789012", alias="sales_summary")
    )

    assert normalize_sql_aliases(notebook) == []
    assert _sql_root(notebook).data.alias == "sales_summary"


def test_does_not_bind_alias_without_persisted_results() -> None:
    notebook = _notebook(_sql_block(code="SELECT 1"))

    assert normalize_sql_aliases(notebook) == []
    assert _sql_root(notebook).data.alias is None


def test_duplicate_alias_raises_with_block_ids() -> None:
    notebook = _notebook(
        _sql_block(data_id="12345678-1234-5678-9012-123456789012", alias="sales"),
        _sql_block(data_id="22345678-1234-5678-9012-123456789012", alias="sales"),
    )

    with pytest.raises(ValueError, match="Duplicate SQL block alias 'sales'"):
        normalize_sql_aliases(notebook)


def test_editor_edit_rejects_duplicate_alias_without_mutating_document() -> None:
    from kontext.file.notebook.editor import NotebookEditor

    notebook = _notebook(
        _sql_block(data_id="12345678-1234-5678-9012-123456789012", alias="taken"),
        _sql_block(data_id="22345678-1234-5678-9012-123456789012", alias="df_7"),
    )
    editor = NotebookEditor(notebook)
    original_blocks = [b.root.model_dump() for b in notebook.blocks]

    with pytest.raises(ValueError, match="Duplicate SQL block alias 'taken'"):
        editor.edit_block(
            str(_sql_root(notebook, 1).id),
            BlockData(
                SqlBlockData(
                    code="SELECT 1",
                    data_ref=DataRef(data_id="22345678-1234-5678-9012-123456789012"),
                    alias="taken",
                )
            ),
        )

    # The in-memory document is untouched: no wedged editor state.
    assert [b.root.model_dump() for b in notebook.blocks] == original_blocks
    assert next_auto_alias(notebook) == "df_8"


def test_duplicate_sql_block_rejected_by_contract_pattern() -> None:
    # The ts/schema contract pattern is enforced by the generated Pydantic
    # model, so invalid slugs can never enter a validated document.
    with pytest.raises(ValidationError):
        _sql_block(alias="9bad-name")


def test_collect_existing_aliases_ignores_unset() -> None:
    notebook = _notebook(
        _sql_block(alias="df_1"),
        _sql_block(code="SELECT 1"),
    )

    assert collect_existing_aliases(notebook) == {"df_1"}
