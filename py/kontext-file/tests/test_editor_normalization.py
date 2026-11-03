import uuid
from unittest.mock import AsyncMock

import pytest

from kontext.file.notebook.editor import NotebookEditor
from kontext.schema import (
    CodeLanguage,
    DataColumn,
    DataRef,
    DataTable,
    InlineData,
    NotebookBlock,
    SqlBlock,
    SqlBlockData,
)


@pytest.mark.asyncio
async def test_validate_chart_fields_case_insensitive():
    # Setup mock data table with mixed case columns
    columns = [
        DataColumn(name="Sales", type="NUMBER"),
        DataColumn(name="DATE", type="DATE"),
        DataColumn(name="category", type="STRING"),
    ]
    table = DataTable(columns=columns, rows=[])
    data_source = InlineData(title="Test DS", table=table)

    # Setup editor with the mock data table
    editor = NotebookEditor()
    editor.create_notebook("Test")

    # Add a mock SQL block that "provides" this data table
    ds_id = str(uuid.uuid4())
    sql_block = SqlBlock(
        id=str(uuid.uuid4()),
        type="sql",
        data=SqlBlockData(
            code="SELECT *",
            data_ref=DataRef(data_id=ds_id, code="SELECT *", language=CodeLanguage.SQL),
        ),
    )
    editor.add_block(NotebookBlock(sql_block))

    # Mock fetch_data_table to return our mock data table
    editor.fetch_data_table = AsyncMock(return_value=data_source)

    # Test case 1: Lowercase input for Uppercase/Mixed case columns
    required_fields: dict[str, str] = {
        "x_field": "date",  # should match DATE
        "y_field": "sales",  # should match Sales
        "color_field": "CATEGORY",  # should match category
    }

    errors = await editor.validate_chart_fields(ds_id, required_fields)

    assert len(errors) == 0
    assert required_fields["x_field"] == "DATE"
    assert required_fields["y_field"] == "Sales"
    assert required_fields["color_field"] == "category"

    # Test case 2: Valid exact match remains same
    required_fields_2: dict[str, str] = {"x_field": "Sales"}
    errors_2 = await editor.validate_chart_fields(ds_id, required_fields_2)
    assert len(errors_2) == 0
    assert required_fields_2["x_field"] == "Sales"

    # Test case 3: Invalid column still returns error
    required_fields_3: dict[str, str] = {"x_field": "nonexistent"}
    errors_3 = await editor.validate_chart_fields(ds_id, required_fields_3)
    assert len(errors_3) == 1
    assert "not found" in errors_3[0]
