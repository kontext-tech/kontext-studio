from kontext.agent.tools import (
    ToolAction,
    ToolResultParser,
    create_tool_registry,
    get_declared_tool_meta,
    register_tools_from_callables,
    tool_meta,
)
from kontext.schema import ArtifactType, NotebookMutationResult


def test_explicit_registry_builds_from_declared_callables() -> None:
    @tool_meta(
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Create Notebook",
    )
    def create_notebook():
        return None

    registry = register_tools_from_callables([create_notebook], create_tool_registry())

    meta = registry.get_tool_meta("create_notebook")
    assert meta is not None
    assert meta.action is ToolAction.CREATE
    assert meta.get_display_name() == "Create Notebook"


def test_declared_tool_meta_is_attached_to_function() -> None:
    @tool_meta(
        result_class=NotebookMutationResult,
        action=ToolAction.UPDATE,
        artifact_type=ArtifactType.NOTEBOOK,
    )
    def update_notebook():
        return None

    meta = get_declared_tool_meta(update_notebook)
    assert meta is not None
    assert meta.name == "update_notebook"
    assert meta.action is ToolAction.UPDATE


def test_explicit_registry_is_used_by_tool_result_parser() -> None:
    registry = create_tool_registry()

    @tool_meta(
        result_class=NotebookMutationResult,
        action=ToolAction.CREATE,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Create Notebook",
        registry=registry,
    )
    def create_notebook():
        return None

    parser = ToolResultParser(registry=registry)
    assert parser.get_display_name("create_notebook") == "Create Notebook"
