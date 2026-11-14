"""Tests for the shared data-id payload hydration used by managed Python jobs."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from kontext.jobs.python_data_hydration import hydrate_data_payloads
from kontext.schema import DataColumn, DataTable, InlineData


def _inline_data() -> InlineData:
    return InlineData(
        title="SQL Result",
        table=DataTable(
            columns=[DataColumn(name="amount", type="Int32")],
            rows=[["10"], ["20"], ["30"]],
            row_count=3,
        ),
    )


@pytest.mark.asyncio
async def test_hydrates_every_data_source_with_full_rows() -> None:
    file_service = MagicMock()
    file_service.get_inline_data_rows = AsyncMock(return_value=_inline_data())

    payloads, skipped = await hydrate_data_payloads(
        project_id="11111111-1111-1111-1111-111111111111",
        data_sources={"sales": "22222222-2222-2222-2222-222222222222"},
        file_service=file_service,
    )

    assert skipped == []
    assert "sales" in payloads
    assert '"rowCount"' in payloads["sales"]
    call = file_service.get_inline_data_rows.await_args
    assert call.kwargs["offset"] == 0
    assert call.kwargs["limit"] is None


@pytest.mark.asyncio
async def test_skips_unresolvable_data_sources() -> None:
    file_service = MagicMock()
    file_service.get_inline_data_rows = AsyncMock(side_effect=FileNotFoundError("gone"))

    payloads, skipped = await hydrate_data_payloads(
        project_id="11111111-1111-1111-1111-111111111111",
        data_sources={"broken": "33333333-3333-3333-3333-333333333333"},
        file_service=file_service,
    )

    assert payloads == {}
    assert skipped == ["broken"]


@pytest.mark.asyncio
async def test_hydrates_shared_file_once_for_multiple_names() -> None:
    """Alias and durable id pointing at one file share a single hydration."""
    file_service = MagicMock()
    file_service.get_inline_data_rows = AsyncMock(return_value=_inline_data())

    payloads, skipped = await hydrate_data_payloads(
        project_id="11111111-1111-1111-1111-111111111111",
        data_sources={
            "55555555-5555-5555-5555-555555555555": "22222222-2222-2222-2222-222222222222",
            "df_1": "22222222-2222-2222-2222-222222222222",
        },
        file_service=file_service,
    )

    assert skipped == []
    assert payloads["55555555-5555-5555-5555-555555555555"] == payloads["df_1"]
    assert file_service.get_inline_data_rows.await_count == 1
