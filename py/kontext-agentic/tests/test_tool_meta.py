import pytest
from pydantic import BaseModel

from kontext.agent.tools import (
    ToolAction,
    ToolRegistry,
    ToolResultParser,
    _convert_method_name_to_display_name,
    create_tool_registry,
    creates_artifact,
    deletes_artifact,
    get_tool_meta,
    reads_artifact,
    register_tool,
    reset_default_tool_registry_for_tests,
    tool_meta,
    updates_artifact,
)
from kontext.schema import ArtifactType, NotebookBlockResult, NotebookMutationResult


@pytest.fixture(autouse=True)
def clear_tool_registry():
    # Ensure a clean registry for each test
    reset_default_tool_registry_for_tests()
    yield
    reset_default_tool_registry_for_tests()


def test_register_tool_and_get_meta():
    register_tool(
        name="unit_test_tool",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        emit_tool_call=True,
    )

    meta = get_tool_meta("unit_test_tool")
    assert meta is not None
    assert meta.name == "unit_test_tool"
    assert meta.result_class is NotebookMutationResult
    assert meta.action is ToolAction.CREATE
    assert meta.artifact_type is ArtifactType.NOTEBOOK
    assert meta.emit_tool_call is True


def test_get_tool_meta_returns_none_for_unknown():
    assert get_tool_meta("does_not_exist") is None


def test_tool_meta_decorator_registers_with_function_name():
    @tool_meta(
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
    )
    def decorated_tool():  # pragma: no cover - body not relevant
        pass

    meta = get_tool_meta("decorated_tool")
    assert meta is not None
    assert meta.result_class is NotebookMutationResult
    assert meta.action is ToolAction.CREATE
    assert meta.artifact_type is ArtifactType.NOTEBOOK


def test_tool_meta_decorator_with_custom_name():
    @tool_meta(
        result_class=NotebookMutationResult,
        action=ToolAction.UPDATE,
        name="custom_tool",
        artifact_type=ArtifactType.NOTEBOOK,
    )
    def some_func():  # pragma: no cover - body not relevant
        pass

    meta = get_tool_meta("custom_tool")
    assert meta is not None
    assert meta.result_class is NotebookMutationResult
    assert meta.action is ToolAction.UPDATE
    assert meta.artifact_type is ArtifactType.NOTEBOOK


def test_convenience_decorators_create_update_delete_read_with_artifact_type():
    @creates_artifact(NotebookMutationResult, artifact_type=ArtifactType.NOTEBOOK)
    def create_fn():  # pragma: no cover
        pass

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK)
    def update_fn():  # pragma: no cover
        pass

    @deletes_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK)
    def delete_fn():  # pragma: no cover
        pass

    @reads_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK)
    def read_fn():  # pragma: no cover
        pass

    m_create = get_tool_meta("create_fn")
    m_update = get_tool_meta("update_fn")
    m_delete = get_tool_meta("delete_fn")
    m_read = get_tool_meta("read_fn")

    assert (
        m_create
        and m_create.action is ToolAction.CREATE
        and m_create.artifact_type is ArtifactType.NOTEBOOK
    )
    assert (
        m_update
        and m_update.action is ToolAction.UPDATE
        and m_update.artifact_type is ArtifactType.NOTEBOOK
    )
    assert (
        m_delete
        and m_delete.action is ToolAction.DELETE
        and m_delete.artifact_type is ArtifactType.NOTEBOOK
    )
    assert (
        m_read
        and m_read.action is ToolAction.READ
        and m_read.artifact_type is ArtifactType.NOTEBOOK
    )


def test_reads_artifact_allows_missing_artifact_type():
    @reads_artifact(NotebookBlockResult)  # artifact_type optional for reads
    def read_without_type():  # pragma: no cover
        pass

    meta = get_tool_meta("read_without_type")
    assert meta is not None
    assert meta.action is ToolAction.READ
    assert meta.artifact_type is None


def test_register_tool_overwrites_existing():
    register_tool("dup", NotebookMutationResult, ToolAction.CREATE, ArtifactType.NOTEBOOK)
    # Overwrite with a different action/result
    register_tool("dup", NotebookMutationResult, ToolAction.UPDATE, ArtifactType.NOTEBOOK)

    meta = get_tool_meta("dup")
    assert meta is not None
    assert meta.result_class is NotebookMutationResult
    assert meta.action is ToolAction.UPDATE


# Display Name Tests
def test_convert_method_name_to_display_name():
    """Test the method name to display name conversion function."""
    test_cases = [
        ("add_data_table", "Add Data Table"),
        ("create_notebook", "Create Notebook"),
        ("edit_block", "Edit Block"),
        ("delete_block", "Delete Block"),
        ("get_project", "Get Project"),
        ("list_catalog_entities", "List Catalog Entities"),
        ("add_paragraph", "Add Paragraph"),
        ("update_api_key", "Update API Key"),
        ("generate_html_report", "Generate HTML Report"),
        ("process_csv_file", "Process CSV File"),
        ("export_pdf_document", "Export PDF Document"),
        ("validate_json_schema", "Validate JSON Schema"),
        ("simple_function", "Simple Function"),
    ]

    for method_name, expected in test_cases:
        result = _convert_method_name_to_display_name(method_name)
        assert result == expected, f"Expected '{expected}' but got '{result}' for '{method_name}'"


def test_tool_meta_get_display_name_with_custom_name():
    """Test ToolMeta.get_display_name() returns custom display name when provided."""
    register_tool(
        name="test_function",
        display_name="Custom Tool Name",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
    )

    meta = get_tool_meta("test_function")
    assert meta is not None
    assert meta.display_name == "Custom Tool Name"
    assert meta.get_display_name() == "Custom Tool Name"


def test_tool_meta_get_display_name_fallback_to_conversion():
    """Test ToolMeta.get_display_name() falls back to method name conversion when no custom name."""
    register_tool(
        name="add_data_table_block",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
    )

    meta = get_tool_meta("add_data_table_block")
    assert meta is not None
    assert meta.display_name is None
    assert meta.get_display_name() == "Add Data Table Block"


def test_tool_meta_decorator_with_display_name():
    """Test @tool_meta decorator accepts and stores display_name parameter."""

    @tool_meta(
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Create Data Table",
    )
    def add_data_table_function():  # pragma: no cover
        pass

    meta = get_tool_meta("add_data_table_function")
    assert meta is not None
    assert meta.display_name == "Create Data Table"
    assert meta.get_display_name() == "Create Data Table"


def test_convenience_decorators_with_display_names():
    """Test convenience decorators accept display_name parameter."""

    @creates_artifact(
        NotebookMutationResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Create Text Block",
    )
    def add_text():  # pragma: no cover
        pass

    @updates_artifact(
        NotebookMutationResult, artifact_type=ArtifactType.NOTEBOOK, display_name="Edit Block"
    )
    def edit_block():  # pragma: no cover
        pass

    @deletes_artifact(
        NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, display_name="Delete Block"
    )
    def delete_block():  # pragma: no cover
        pass

    @reads_artifact(
        NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, display_name="Read Block"
    )
    def get_block():  # pragma: no cover
        pass

    # Test each decorator
    add_meta = get_tool_meta("add_text")
    edit_meta = get_tool_meta("edit_block")
    delete_meta = get_tool_meta("delete_block")
    read_meta = get_tool_meta("get_block")

    assert add_meta and add_meta.get_display_name() == "Create Text Block"
    assert edit_meta and edit_meta.get_display_name() == "Edit Block"
    assert delete_meta and delete_meta.get_display_name() == "Delete Block"
    assert read_meta and read_meta.get_display_name() == "Read Block"


def test_convenience_decorators_without_display_names_use_fallback():
    """Test convenience decorators fall back to method name conversion when no display_name provided."""

    @creates_artifact(NotebookMutationResult, artifact_type=ArtifactType.NOTEBOOK)
    def create_chart_block():  # pragma: no cover
        pass

    @updates_artifact(NotebookMutationResult, artifact_type=ArtifactType.NOTEBOOK)
    def update_sql_query():  # pragma: no cover
        pass

    create_meta = get_tool_meta("create_chart_block")
    update_meta = get_tool_meta("update_sql_query")

    assert create_meta and create_meta.get_display_name() == "Create Chart Block"
    assert update_meta and update_meta.get_display_name() == "Update SQL Query"


def test_register_tool_with_display_name():
    """Test register_tool function accepts display_name parameter."""
    register_tool(
        name="complex_function_name",
        display_name="User Friendly Name",
        result_class=NotebookBlockResult,
        action=ToolAction.READ,
        artifact_type=ArtifactType.NOTEBOOK,
    )

    meta = get_tool_meta("complex_function_name")
    assert meta is not None
    assert meta.name == "complex_function_name"
    assert meta.display_name == "User Friendly Name"
    assert meta.get_display_name() == "User Friendly Name"


def test_create_tool_registry_produces_isolated_namespace():
    first = create_tool_registry(namespace="first")
    second = create_tool_registry(namespace="second")

    first.register_tool(
        "shared_name",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Shared Display",
    )
    second.register_tool(
        "shared_name",
        result_class=NotebookBlockResult,
        action=ToolAction.READ,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Shared Display",
    )

    first_meta = first.get_tool_meta("shared_name")
    second_meta = second.get_tool_meta("shared_name")

    assert isinstance(first, ToolRegistry)
    assert isinstance(second, ToolRegistry)
    assert first_meta and first_meta.result_class is NotebookMutationResult
    assert second_meta and second_meta.result_class is NotebookBlockResult


def test_registry_conflict_overwrites_display_name_mapping_deterministically():
    registry = create_tool_registry(namespace="conflict")
    registry.register_tool(
        "first_tool",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Same Display",
    )
    registry.register_tool(
        "second_tool",
        result_class=NotebookBlockResult,
        action=ToolAction.READ,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Same Display",
    )

    resolved = registry.get_tool_meta("Same Display")
    assert resolved is not None
    assert resolved.name == "second_tool"


class _CustomToolResult(BaseModel):
    success: bool
    value: str


def test_tool_result_parser_uses_custom_registry_for_display_name() -> None:
    register_tool(
        name="shared_tool",
        display_name="Default Display",
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
    )
    registry = create_tool_registry(namespace="parser")
    registry.register_tool(
        name="shared_tool",
        display_name="Custom Display",
        result_class=_CustomToolResult,
        action=ToolAction.READ,
    )

    parser = ToolResultParser(registry=registry)

    assert parser.get_display_name("shared_tool") == "Custom Display"


def test_tool_result_parser_uses_custom_registry_result_class() -> None:
    registry = create_tool_registry(namespace="parser")
    registry.register_tool(
        name="custom_tool",
        display_name="Custom Tool",
        result_class=_CustomToolResult,
        action=ToolAction.READ,
    )

    parser = ToolResultParser(registry=registry)
    parsed = parser.parse_tool_result(
        "custom_tool",
        '{"success": true, "value": "ok"}',
    )

    assert isinstance(parsed, _CustomToolResult)
    assert parsed.value == "ok"
